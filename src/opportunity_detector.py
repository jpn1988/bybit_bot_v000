#!/usr/bin/env python3
"""
Détecteur d'opportunités pour le bot Bybit.

Cette classe est responsable de la détection et de l'intégration
des opportunités de trading.
"""

from typing import List, Dict, Optional, Callable
from logging_setup import setup_logging
from unified_data_manager import UnifiedDataManager
from watchlist_manager import WatchlistManager
from volatility_tracker import VolatilityTracker
from bybit_client import BybitPublicClient
from models.funding_data import FundingData


class OpportunityDetector:
    """
    Détecteur d'opportunités pour identifier et intégrer les opportunités de trading.
    
    Responsabilité unique : Détecter les opportunités et les intégrer dans le système.
    """

    def __init__(
        self,
        data_manager: UnifiedDataManager,
        watchlist_manager: WatchlistManager,
        volatility_tracker: VolatilityTracker,
        testnet: bool = True,
        logger=None,
    ):
        """
        Initialise le détecteur d'opportunités.

        Args:
            data_manager: Gestionnaire de données
            watchlist_manager: Gestionnaire de watchlist
            volatility_tracker: Tracker de volatilité
            testnet: Utiliser le testnet (True) ou le marché réel (False)
            logger: Logger pour les messages (optionnel)
        """
        self.data_manager = data_manager
        self.watchlist_manager = watchlist_manager
        self.volatility_tracker = volatility_tracker
        self.testnet = testnet
        self.logger = logger or setup_logging()
        
        # Callback pour les nouvelles opportunités
        self._on_new_opportunity_callback: Optional[Callable] = None
        
        # Référence au WebSocket pour optimisation
        self.ws_manager = None

    def set_ws_manager(self, ws_manager):
        """
        Définit le gestionnaire WebSocket principal.

        Args:
            ws_manager: Gestionnaire WebSocket principal
        """
        self.ws_manager = ws_manager

    def set_on_new_opportunity_callback(self, callback: Callable):
        """
        Définit le callback pour les nouvelles opportunités.

        Args:
            callback: Fonction à appeler lors de nouvelles opportunités
        """
        self._on_new_opportunity_callback = callback

    def scan_for_opportunities(
        self, base_url: str, perp_data: Dict
    ) -> Optional[Dict]:
        """
        Scanne le marché pour trouver de nouvelles opportunités.

        Args:
            base_url: URL de base de l'API
            perp_data: Données des perpétuels

        Returns:
            Dict avec les opportunités trouvées ou None
        """
        try:
            # Optimisation : éviter le scan si WebSocket déjà actif
            if self._is_websocket_active():
                self.logger.info("🔄 Scan évité - WebSocket déjà actif")
                return None

            # Créer un nouveau client pour éviter les problèmes de futures
            client = BybitPublicClient(testnet=self.testnet, timeout=10)
            fresh_base_url = client.public_base_url()

            # Reconstruire la watchlist (peut prendre du temps)
            (
                linear_symbols,
                inverse_symbols,
                funding_data,
            ) = self.watchlist_manager.build_watchlist(
                fresh_base_url, perp_data, self.volatility_tracker
            )

            if linear_symbols or inverse_symbols:
                return {
                    "linear": linear_symbols,
                    "inverse": inverse_symbols,
                    "funding_data": funding_data,
                }

        except Exception as e:
            self.logger.warning(f"⚠️ Erreur scan opportunités: {e}")

        return None

    def integrate_opportunities(self, opportunities: Dict):
        """
        Intègre les nouvelles opportunités détectées.

        Args:
            opportunities: Dict avec les opportunités à intégrer
        """
        linear_symbols = opportunities.get("linear", [])
        inverse_symbols = opportunities.get("inverse", [])
        funding_data = opportunities.get("funding_data", {})

        # Récupérer les symboles existants
        existing_linear = set(self.data_manager.storage.get_linear_symbols())
        existing_inverse = set(self.data_manager.storage.get_inverse_symbols())

        # Identifier les nouveaux symboles
        new_linear = set(linear_symbols) - existing_linear
        new_inverse = set(inverse_symbols) - existing_inverse

        if new_linear or new_inverse:
            # Mettre à jour les listes de symboles
            self._update_symbol_lists(
                linear_symbols,
                inverse_symbols,
                existing_linear,
                existing_inverse,
            )

            # Mettre à jour les données de funding
            self._update_funding_data(funding_data)

            # Notifier les nouvelles opportunités
            self._notify_new_opportunities(linear_symbols, inverse_symbols)

    def _is_websocket_active(self) -> bool:
        """Vérifie si le WebSocket principal est actif."""
        return (
            self.ws_manager
            and hasattr(self.ws_manager, "running")
            and self.ws_manager.running
        )

    def _update_symbol_lists(
        self,
        linear_symbols: List[str],
        inverse_symbols: List[str],
        existing_linear: set,
        existing_inverse: set,
    ):
        """Met à jour les listes de symboles avec les nouvelles opportunités."""
        # Fusionner les listes
        all_linear = list(existing_linear | set(linear_symbols))
        all_inverse = list(existing_inverse | set(inverse_symbols))

        # Mettre à jour dans le data manager
        self.data_manager.storage.set_symbol_lists(all_linear, all_inverse)

    def _update_funding_data(self, new_funding_data: Dict):
        """Met à jour les données de funding avec les nouvelles opportunités (utilise Value Objects)."""
        # Mettre à jour chaque symbole dans le data manager
        for symbol, data in new_funding_data.items():
            try:
                # Créer un FundingData Value Object
                if isinstance(data, (list, tuple)) and len(data) >= 4:
                    funding, volume, funding_time, spread = data[:4]
                    volatility = data[4] if len(data) > 4 else None
                    
                    funding_obj = FundingData(
                        symbol=symbol,
                        funding_rate=funding,
                        volume_24h=volume,
                        next_funding_time=funding_time,
                        spread_pct=spread,
                        volatility_pct=volatility
                    )
                    
                elif isinstance(data, dict):
                    # Si c'est un dictionnaire, extraire les valeurs
                    funding = data.get("funding", 0.0)
                    volume = data.get("volume", 0.0)
                    funding_time = data.get("funding_time_remaining", "-")
                    spread = data.get("spread_pct", 0.0)
                    volatility = data.get("volatility_pct", None)
                    
                    funding_obj = FundingData(
                        symbol=symbol,
                        funding_rate=funding,
                        volume_24h=volume,
                        next_funding_time=funding_time,
                        spread_pct=spread,
                        volatility_pct=volatility
                    )
                else:
                    continue
                
                # Stocker le Value Object
                self.data_manager.storage.set_funding_data_object(funding_obj)
                
            except (ValueError, TypeError) as e:
                self.logger.warning(f"⚠️ Erreur création FundingData pour {symbol}: {e}")

        # Mettre à jour les données originales si disponible
        self._update_original_funding_data()

    def _update_original_funding_data(self):
        """Met à jour les données de funding originales."""
        try:
            original_data = self.watchlist_manager.get_original_funding_data()
            for symbol, next_funding_time in original_data.items():
                self.data_manager.storage.update_original_funding_data(
                    symbol, next_funding_time
                )
        except Exception as e:
            self.logger.warning(
                f"⚠️ Erreur mise à jour données originales: {e}"
            )

    def _notify_new_opportunities(
        self, linear_symbols: List[str], inverse_symbols: List[str]
    ):
        """Notifie les nouvelles opportunités via callback."""
        if self._on_new_opportunity_callback:
            try:
                self._on_new_opportunity_callback(linear_symbols, inverse_symbols)
            except Exception as e:
                self.logger.warning(
                    f"⚠️ Erreur callback nouvelles opportunités: {e}"
                )

