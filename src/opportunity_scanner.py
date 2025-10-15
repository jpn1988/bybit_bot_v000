#!/usr/bin/env python3
"""
Scanner d'opportunités pour le bot Bybit.

Cette classe est responsable uniquement de :
- La détection de nouvelles opportunités via scan du marché
- La reconstruction de la watchlist pour identifier les nouveaux symboles

Responsabilité unique : Scanner le marché pour détecter les opportunités.
"""

from typing import Dict, Optional
from logging_setup import setup_logging
from watchlist_manager import WatchlistManager
from volatility_tracker import VolatilityTracker
from interfaces.bybit_client_interface import BybitClientInterface
from bybit_client import BybitPublicClient
from config.timeouts import TimeoutConfig


class OpportunityScanner:
    """
    Scanner d'opportunités pour le bot Bybit.

    Responsabilités :
    - Scan du marché pour détecter de nouvelles opportunités
    - Reconstruction de la watchlist pour identifier les nouveaux symboles
    """

    def __init__(
        self,
        watchlist_manager: WatchlistManager,
        volatility_tracker: VolatilityTracker,
        testnet: bool = True,
        logger=None,
    ):
        """
        Initialise le scanner d'opportunités.

        Args:
            watchlist_manager: Gestionnaire de watchlist
            volatility_tracker: Tracker de volatilité
            testnet: Utiliser le testnet (True) ou le marché réel (False)
            logger: Logger pour les messages (optionnel)
        """
        self.watchlist_manager = watchlist_manager
        self.volatility_tracker = volatility_tracker
        self.testnet = testnet
        self.logger = logger or setup_logging()

        # Référence au WebSocket pour optimisation
        self.ws_manager = None

    def set_ws_manager(self, ws_manager):
        """
        Définit le gestionnaire WebSocket principal pour optimisation.

        Args:
            ws_manager: Gestionnaire WebSocket principal
        """
        self.ws_manager = ws_manager

    def scan_for_opportunities(self, base_url: str, perp_data: Dict) -> Optional[Dict]:
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

            # Vérifier que les composants nécessaires sont disponibles
            if not self.watchlist_manager or not self.volatility_tracker:
                self.logger.warning("⚠️ Scan impossible - composants manquants")
                return None

            # Créer un nouveau client pour éviter les problèmes de futures
            client: BybitClientInterface = BybitPublicClient(
                testnet=self.testnet, timeout=TimeoutConfig.DEFAULT
            )
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

    def _is_websocket_active(self) -> bool:
        """Vérifie si le WebSocket principal est actif."""
        return (
            self.ws_manager
            and hasattr(self.ws_manager, "running")
            and self.ws_manager.running
        )
