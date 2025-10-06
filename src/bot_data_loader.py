#!/usr/bin/env python3
"""
Chargeur de données du bot Bybit - Version refactorisée.

Cette classe gère uniquement :
- La construction de la watchlist
- Le chargement des données de funding
- La gestion des erreurs de chargement
"""

from typing import Dict, Any
from logging_setup import setup_logging
from data_manager import DataManager
from watchlist_manager import WatchlistManager
from volatility_tracker import VolatilityTracker


class BotDataLoader:
    """
    Chargeur de données du bot Bybit.

    Responsabilités :
    - Construction de la watchlist
    - Chargement des données de funding
    - Gestion des erreurs de chargement
    """

    def __init__(self, logger=None):
        """
        Initialise le chargeur de données.

        Args:
            logger: Logger pour les messages (optionnel)
        """
        self.logger = logger or setup_logging()

    def load_watchlist_data(
        self,
        base_url: str,
        perp_data: Dict,
        watchlist_manager: WatchlistManager,
        volatility_tracker: VolatilityTracker,
        data_manager: DataManager,
    ) -> bool:
        """
        Charge les données de la watchlist.

        Args:
            base_url: URL de base de l'API
            perp_data: Données des perpétuels
            watchlist_manager: Gestionnaire de watchlist
            volatility_tracker: Tracker de volatilité
            data_manager: Gestionnaire de données

        Returns:
            True si le chargement a réussi, False sinon
        """
        self.logger.info("📥 Chargement des données de la watchlist...")

        try:
            # Construire la watchlist
            (
                linear_symbols,
                inverse_symbols,
                funding_data,
            ) = watchlist_manager.build_watchlist(
                base_url, perp_data, volatility_tracker
            )

            # Mettre à jour le DataManager avec les données initiales
            data_manager.set_symbol_lists(linear_symbols, inverse_symbols)

            # Mettre à jour les données de funding
            self._update_funding_data(funding_data, data_manager)

            # Mettre à jour les données originales
            original_funding_data = (
                watchlist_manager.get_original_funding_data()
            )
            for symbol, next_funding_time in original_funding_data.items():
                data_manager.update_original_funding_data(
                    symbol, next_funding_time
                )

            self.logger.info(
                f"✅ Watchlist chargée: {len(linear_symbols)} linear, "
                f"{len(inverse_symbols)} inverse"
            )
            return True

        except Exception as e:
            if "Aucun symbole" in str(e) or "Aucun funding" in str(e):
                # Ne pas lever d'exception, continuer en mode surveillance
                self.logger.info(
                    "ℹ️ Aucune opportunité initiale détectée, mode surveillance activé"
                )
                return True
            else:
                self.logger.error(f"❌ Erreur chargement watchlist: {e}")
                raise

    def _update_funding_data(
        self, funding_data: Dict, data_manager: DataManager
    ):
        """
        Met à jour les données de funding dans le data manager.

        Args:
            funding_data: Données de funding à mettre à jour
            data_manager: Gestionnaire de données
        """
        self.logger.info("💰 Mise à jour des données de funding...")

        for symbol, data in funding_data.items():
            try:
                if isinstance(data, (list, tuple)) and len(data) >= 4:
                    funding, volume, funding_time, spread = data[:4]
                    volatility = data[4] if len(data) > 4 else None
                    data_manager.update_funding_data(
                        symbol,
                        funding,
                        volume,
                        funding_time,
                        spread,
                        volatility,
                    )
                elif isinstance(data, dict):
                    # Si c'est un dictionnaire, extraire les valeurs
                    funding = data.get("funding", 0.0)
                    volume = data.get("volume", 0.0)
                    funding_time = data.get("funding_time_remaining", "-")
                    spread = data.get("spread_pct", 0.0)
                    volatility = data.get("volatility_pct", None)
                    data_manager.update_funding_data(
                        symbol,
                        funding,
                        volume,
                        funding_time,
                        spread,
                        volatility,
                    )
                else:
                    self.logger.warning(
                        f"⚠️ Format de données inattendu pour {symbol}: {type(data)}"
                    )

            except Exception as e:
                self.logger.warning(
                    f"⚠️ Erreur mise à jour données {symbol}: {e}"
                )

        self.logger.info("✅ Données de funding mises à jour")

    def validate_data_integrity(self, data_manager: DataManager) -> bool:
        """
        Valide l'intégrité des données chargées.

        Args:
            data_manager: Gestionnaire de données

        Returns:
            True si les données sont valides
        """
        self.logger.info("🔍 Validation de l'intégrité des données...")

        try:
            # Vérifier que les données de base sont présentes
            linear_symbols = data_manager.get_linear_symbols()
            inverse_symbols = data_manager.get_inverse_symbols()
            funding_data = data_manager.get_all_funding_data()

            if not linear_symbols and not inverse_symbols:
                self.logger.warning("⚠️ Aucun symbole dans la watchlist")
                return False

            if not funding_data:
                self.logger.warning("⚠️ Aucune donnée de funding")
                return False

            # Vérifier la cohérence des données
            total_symbols = len(linear_symbols) + len(inverse_symbols)
            funding_count = len(funding_data)

            if funding_count != total_symbols:
                self.logger.warning(
                    f"⚠️ Incohérence: {total_symbols} symboles mais "
                    f"{funding_count} données de funding"
                )

            self.logger.info(
                f"✅ Intégrité validée: {total_symbols} symboles, "
                f"{funding_count} données de funding"
            )
            return True

        except Exception as e:
            self.logger.error(f"❌ Erreur validation intégrité: {e}")
            return False

    def get_loading_summary(self, data_manager: DataManager) -> Dict[str, Any]:
        """
        Retourne un résumé du chargement des données.

        Args:
            data_manager: Gestionnaire de données

        Returns:
            Dictionnaire contenant le résumé
        """
        linear_symbols = data_manager.get_linear_symbols()
        inverse_symbols = data_manager.get_inverse_symbols()
        funding_data = data_manager.get_all_funding_data()

        return {
            "linear_count": len(linear_symbols),
            "inverse_count": len(inverse_symbols),
            "total_symbols": len(linear_symbols) + len(inverse_symbols),
            "funding_data_count": len(funding_data),
            "linear_symbols": linear_symbols[
                :5
            ],  # Premiers 5 pour l'affichage
            "inverse_symbols": inverse_symbols[
                :5
            ],  # Premiers 5 pour l'affichage
        }
