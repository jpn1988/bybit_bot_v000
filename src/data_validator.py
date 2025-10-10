#!/usr/bin/env python3
"""
Gestionnaire de validation de données pour le bot Bybit.

Cette classe gère uniquement :
- La validation de l'intégrité des données
- La vérification de la cohérence des données
- La validation des paramètres d'entrée
"""

from typing import Dict, List, Any
from logging_setup import setup_logging


class DataValidator:
    """
    Gestionnaire de validation de données pour le bot Bybit.

    Responsabilités :
    - Validation de l'intégrité des données
    - Vérification de la cohérence des données
    - Validation des paramètres d'entrée
    """

    def __init__(self, logger=None):
        """
        Initialise le gestionnaire de validation de données.

        Args:
            logger: Logger pour les messages (optionnel)
        """
        self.logger = logger or setup_logging()

    def validate_data_integrity(
        self,
        linear_symbols: List[str],
        inverse_symbols: List[str],
        funding_data: Dict
    ) -> bool:
        """
        Valide l'intégrité des données chargées.

        Args:
            linear_symbols: Liste des symboles linear
            inverse_symbols: Liste des symboles inverse
            funding_data: Données de funding

        Returns:
            bool: True si les données sont valides
        """
        try:
            # Vérifier que les listes de symboles ne sont pas vides
            if not linear_symbols and not inverse_symbols:
                self.logger.warning("⚠️ Aucun symbole dans les listes")
                return False

            # Vérifier que les données de funding sont présentes
            if not funding_data:
                self.logger.warning("⚠️ Aucune donnée de funding")
                return False

            self.logger.info(
                f"✅ Intégrité des données validée: {len(linear_symbols)} linear, "
                f"{len(inverse_symbols)} inverse"
            )
            return True

        except Exception as e:
            self.logger.error(f"❌ Erreur validation intégrité: {e}")
            return False

    def validate_funding_data(self, funding_data: Dict) -> bool:
        """
        Valide les données de funding.

        Args:
            funding_data: Données de funding à valider

        Returns:
            bool: True si les données sont valides
        """
        try:
            if not funding_data:
                return False

            for symbol, data in funding_data.items():
                if not self._validate_single_funding_entry(symbol, data):
                    return False

            return True

        except Exception as e:
            self.logger.error(f"❌ Erreur validation funding: {e}")
            return False

    def _validate_single_funding_entry(self, symbol: str, data: Any) -> bool:
        """
        Valide une entrée de funding individuelle.

        Args:
            symbol: Symbole à valider
            data: Données du symbole

        Returns:
            bool: True si l'entrée est valide
        """
        try:
            if not symbol:
                return False

            if isinstance(data, (list, tuple)) and len(data) >= 4:
                # Format: (funding, volume, funding_time, spread, volatility?)
                funding, volume, funding_time, spread = data[:4]

                # Vérifier les types
                if not isinstance(funding, (int, float)):
                    return False
                if not isinstance(volume, (int, float)):
                    return False
                if not isinstance(funding_time, str):
                    return False
                if not isinstance(spread, (int, float)):
                    return False

            elif isinstance(data, dict):
                # Format: {funding, volume, funding_time, spread, volatility}
                required_keys = ["funding", "volume", "funding_time", "spread"]
                for key in required_keys:
                    if key not in data:
                        return False
                    if not isinstance(data[key], (int, float, str)):
                        return False
            else:
                return False

            return True

        except Exception:
            return False

    def validate_realtime_data(self, realtime_data: Dict[str, Dict[str, Any]]) -> bool:
        """
        Valide les données en temps réel.

        Args:
            realtime_data: Données en temps réel à valider

        Returns:
            bool: True si les données sont valides
        """
        try:
            if not realtime_data:
                return True  # Pas de données = pas d'erreur

            for symbol, data in realtime_data.items():
                if not self._validate_single_realtime_entry(symbol, data):
                    return False

            return True

        except Exception as e:
            self.logger.error(f"❌ Erreur validation temps réel: {e}")
            return False

    def _validate_single_realtime_entry(self, symbol: str, data: Dict[str, Any]) -> bool:
        """
        Valide une entrée de données temps réel.

        Args:
            symbol: Symbole à valider
            data: Données temps réel du symbole

        Returns:
            bool: True si l'entrée est valide
        """
        try:
            if not symbol or not isinstance(data, dict):
                return False

            # Vérifier que les clés importantes sont présentes et valides
            important_keys = [
                "funding_rate", "volume24h", "bid1_price", "ask1_price",
                "next_funding_time", "mark_price", "last_price", "timestamp"
            ]

            for key in important_keys:
                if key in data and data[key] is not None:
                    if key == "timestamp" and not isinstance(data[key], (int, float)):
                        return False
                    elif key != "timestamp" and not isinstance(data[key], (int, float, str)):
                        return False

            return True

        except Exception:
            return False

    def validate_symbol_categories(self, symbol_categories: Dict[str, str]) -> bool:
        """
        Valide les catégories de symboles.

        Args:
            symbol_categories: Mapping des catégories

        Returns:
            bool: True si les catégories sont valides
        """
        try:
            if not symbol_categories:
                return True  # Pas de catégories = pas d'erreur

            valid_categories = {"linear", "inverse"}

            for symbol, category in symbol_categories.items():
                if not symbol or not isinstance(symbol, str):
                    return False
                if category not in valid_categories:
                    return False

            return True

        except Exception as e:
            self.logger.error(f"❌ Erreur validation catégories: {e}")
            return False

    def validate_symbol_lists(
        self,
        linear_symbols: List[str],
        inverse_symbols: List[str]
    ) -> bool:
        """
        Valide les listes de symboles.

        Args:
            linear_symbols: Liste des symboles linear
            inverse_symbols: Liste des symboles inverse

        Returns:
            bool: True si les listes sont valides
        """
        try:
            # Vérifier que les listes sont des listes
            if not isinstance(linear_symbols, list) or not isinstance(inverse_symbols, list):
                return False

            # Vérifier que tous les éléments sont des chaînes non vides
            for symbol in linear_symbols + inverse_symbols:
                if not isinstance(symbol, str) or not symbol.strip():
                    return False

            return True

        except Exception as e:
            self.logger.error(f"❌ Erreur validation listes symboles: {e}")
            return False

    def get_loading_summary(
        self,
        linear_symbols: List[str],
        inverse_symbols: List[str],
        funding_data: Dict
    ) -> Dict[str, Any]:
        """
        Retourne un résumé du chargement des données.

        Args:
            linear_symbols: Liste des symboles linear
            inverse_symbols: Liste des symboles inverse
            funding_data: Données de funding

        Returns:
            Dict[str, Any]: Résumé des données chargées
        """
        try:
            return {
                "linear_count": len(linear_symbols),
                "inverse_count": len(inverse_symbols),
                "total_symbols": len(linear_symbols) + len(inverse_symbols),
                "funding_data_count": len(funding_data),
                "linear_symbols": linear_symbols[:5],  # Premiers 5 pour debug
                "inverse_symbols": inverse_symbols[:5],  # Premiers 5 pour debug
            }

        except Exception as e:
            self.logger.error(f"❌ Erreur résumé chargement: {e}")
            return {
                "linear_count": 0,
                "inverse_count": 0,
                "total_symbols": 0,
                "funding_data_count": 0,
                "error": str(e),
            }

    def validate_parameters(
        self,
        base_url: str,
        perp_data: Dict,
        watchlist_manager,
        volatility_tracker
    ) -> bool:
        """
        Valide les paramètres d'entrée pour le chargement des données.

        Args:
            base_url: URL de base de l'API
            perp_data: Données des perpétuels
            watchlist_manager: Gestionnaire de watchlist
            volatility_tracker: Tracker de volatilité

        Returns:
            bool: True si les paramètres sont valides
        """
        try:
            # Vérifier l'URL de base
            if not base_url or not isinstance(base_url, str):
                self.logger.error("❌ URL de base invalide")
                return False

            # Vérifier les données des perpétuels
            if not perp_data or not isinstance(perp_data, dict):
                self.logger.error("❌ Données perpétuels invalides")
                return False

            # Vérifier les managers
            if not watchlist_manager:
                self.logger.error("❌ WatchlistManager manquant")
                return False

            if not volatility_tracker:
                self.logger.error("❌ VolatilityTracker manquant")
                return False

            return True

        except Exception as e:
            self.logger.error(f"❌ Erreur validation paramètres: {e}")
            return False
