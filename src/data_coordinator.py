#!/usr/bin/env python3
"""
Coordinateur de données pour le bot Bybit - Version refactorisée.

Cette classe gère uniquement :
- La coordination entre les composants de données
- L'orchestration des opérations complexes
- La gestion des flux de données
"""

from typing import Dict, List, Optional, Tuple, Any
try:
    from .logging_setup import setup_logging
    from .volatility_tracker import VolatilityTracker
    from .data_fetcher import DataFetcher
    from .data_storage import DataStorage
    from .data_validator import DataValidator
except ImportError:
    from logging_setup import setup_logging
    from volatility_tracker import VolatilityTracker
    from data_fetcher import DataFetcher
    from data_storage import DataStorage
    from data_validator import DataValidator


class DataCoordinator:
    """
    Coordinateur de données pour le bot Bybit.

    Responsabilités :
    - Coordination entre les composants de données
    - Orchestration des opérations complexes
    - Gestion des flux de données
    """

    def __init__(self, testnet: bool, logger=None):
        """
        Initialise le coordinateur de données.

        Args:
            testnet: Utiliser le testnet (True) ou le marché réel (False)
            logger: Logger pour les messages (optionnel)
        """
        self.testnet = testnet
        self.logger = logger or setup_logging()

        # Initialiser les composants spécialisés
        self._fetcher = DataFetcher(logger=self.logger)
        self._storage = DataStorage(logger=self.logger)
        self._validator = DataValidator(logger=self.logger)

    def load_watchlist_data(
        self,
        base_url: str,
        perp_data: Dict,
        watchlist_manager,
        volatility_tracker: VolatilityTracker,
    ) -> bool:
        """
        Interface pour charger les données de la watchlist via WatchlistManager.

        Cette méthode coordonne le chargement des données de la watchlist
        en utilisant les composants spécialisés.

        Args:
            base_url: URL de base de l'API
            perp_data: Données des perpétuels
            watchlist_manager: Gestionnaire de watchlist (WatchlistManager)
            volatility_tracker: Tracker de volatilité

        Returns:
            bool: True si le chargement a réussi
        """
        try:
            self.logger.info("📊 Chargement des données de la watchlist...")

            # 1. Valider les paramètres d'entrée
            if not self._validate_input_parameters(
                base_url, perp_data, watchlist_manager, volatility_tracker
            ):
                return False

            # 2. Construire la watchlist
            watchlist_data = self._build_watchlist(
                base_url, perp_data, watchlist_manager, volatility_tracker
            )
            if not watchlist_data:
                return False

            # 3. Mettre à jour les données
            self._update_data_from_watchlist(watchlist_data, watchlist_manager)

            # 4. Valider l'intégrité des données
            if not self._validate_loaded_data():
                return False

            self.logger.info("✅ Données de la watchlist chargées avec succès")
            return True

        except Exception as e:
            self.logger.error(f"❌ Erreur chargement watchlist: {e}")
            return False

    def _validate_input_parameters(
        self, base_url: str, perp_data: Dict, watchlist_manager, volatility_tracker
    ) -> bool:
        """Valide les paramètres d'entrée pour le chargement."""
        return self._validator.validate_parameters(
            base_url, perp_data, watchlist_manager, volatility_tracker
        )

    def _build_watchlist(
        self, base_url: str, perp_data: Dict, watchlist_manager, volatility_tracker
    ) -> Optional[Tuple[List[str], List[str], Dict]]:
        """Construit la watchlist via le gestionnaire."""
        try:
            linear_symbols, inverse_symbols, funding_data = watchlist_manager.build_watchlist(
                base_url, perp_data, volatility_tracker
            )

            if not linear_symbols and not inverse_symbols:
                self.logger.warning("⚠️ Aucun symbole trouvé pour la watchlist")
                return None

            return linear_symbols, inverse_symbols, funding_data

        except Exception as e:
            self.logger.error(f"❌ Erreur construction watchlist: {e}")
            return None

    def _update_data_from_watchlist(
        self, watchlist_data: Tuple[List[str], List[str], Dict], watchlist_manager
    ):
        """Met à jour les données à partir de la watchlist."""
        linear_symbols, inverse_symbols, funding_data = watchlist_data

        # Mettre à jour les listes de symboles
        self._storage.set_symbol_lists(linear_symbols, inverse_symbols)

        # Mettre à jour les données de funding
        self._update_funding_data(funding_data)

        # Mettre à jour les données originales
        self._update_original_funding_data(watchlist_manager)

    def _update_funding_data(self, funding_data: Dict):
        """Met à jour les données de funding dans le stockage."""
        for symbol, data in funding_data.items():
            if isinstance(data, (list, tuple)) and len(data) >= 4:
                self._update_funding_from_tuple(symbol, data)
            elif isinstance(data, dict):
                self._update_funding_from_dict(symbol, data)

    def _update_funding_from_tuple(self, symbol: str, data: Tuple):
        """Met à jour les données de funding depuis un tuple."""
        funding, volume, funding_time, spread = data[:4]
        volatility = data[4] if len(data) > 4 else None
        self._storage.update_funding_data(
            symbol, funding, volume, funding_time, spread, volatility
        )

    def _update_funding_from_dict(self, symbol: str, data: Dict):
        """Met à jour les données de funding depuis un dictionnaire."""
        funding = data.get("funding", 0.0)
        volume = data.get("volume", 0.0)
        funding_time = data.get("funding_time_remaining", "-")
        spread = data.get("spread_pct", 0.0)
        volatility = data.get("volatility_pct", None)
        self._storage.update_funding_data(
            symbol, funding, volume, funding_time, spread, volatility
        )

    def _update_original_funding_data(self, watchlist_manager):
        """Met à jour les données originales de funding."""
        try:
            original_data = watchlist_manager.get_original_funding_data()
            for symbol, next_funding_time in original_data.items():
                self._storage.update_original_funding_data(symbol, next_funding_time)
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur mise à jour données originales: {e}")

    def _validate_loaded_data(self) -> bool:
        """Valide l'intégrité des données chargées."""
        linear_symbols = self._storage.get_linear_symbols()
        inverse_symbols = self._storage.get_inverse_symbols()
        funding_data = self._storage.get_all_funding_data()

        return self._validator.validate_data_integrity(
            linear_symbols, inverse_symbols, funding_data
        )

    # ===== DÉLÉGATION VERS LES COMPOSANTS SPÉCIALISÉS =====

    def fetch_funding_map(self, base_url: str, category: str, timeout: int = 10) -> Dict[str, Dict]:
        """Délègue vers DataFetcher."""
        return self._fetcher.fetch_funding_map(base_url, category, timeout)

    def fetch_spread_data(self, base_url: str, symbols: List[str], timeout: int = 10, category: str = "linear") -> Dict[str, float]:
        """Délègue vers DataFetcher."""
        return self._fetcher.fetch_spread_data(base_url, symbols, timeout, category)

    def fetch_funding_data_parallel(self, base_url: str, categories: List[str], timeout: int = 10) -> Dict[str, Dict]:
        """Délègue vers DataFetcher."""
        return self._fetcher.fetch_funding_data_parallel(base_url, categories, timeout)

    def set_symbol_categories(self, symbol_categories: Dict[str, str]):
        """Délègue vers DataStorage."""
        self._storage.set_symbol_categories(symbol_categories)

    def update_funding_data(self, symbol: str, funding: float, volume: float, funding_time: str, spread: float, volatility: Optional[float] = None):
        """Délègue vers DataStorage."""
        self._storage.update_funding_data(symbol, funding, volume, funding_time, spread, volatility)

    def get_funding_data(self, symbol: str) -> Optional[Tuple[float, float, str, float, Optional[float]]]:
        """Délègue vers DataStorage."""
        return self._storage.get_funding_data(symbol)

    def get_all_funding_data(self) -> Dict[str, Tuple[float, float, str, float, Optional[float]]]:
        """Délègue vers DataStorage."""
        return self._storage.get_all_funding_data()

    def update_realtime_data(self, symbol: str, ticker_data: Dict[str, Any]):
        """Délègue vers DataStorage."""
        self._storage.update_realtime_data(symbol, ticker_data)

    def update_price_data(self, symbol: str, mark_price: float, last_price: float, timestamp: float):
        """Délègue vers DataStorage."""
        self._storage.update_price_data(symbol, mark_price, last_price, timestamp)

    def get_price_data(self, symbol: str) -> Optional[Dict[str, float]]:
        """Délègue vers DataStorage."""
        return self._storage.get_price_data(symbol)

    def get_realtime_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Délègue vers DataStorage."""
        return self._storage.get_realtime_data(symbol)

    def get_all_realtime_data(self) -> Dict[str, Dict[str, Any]]:
        """Délègue vers DataStorage."""
        return self._storage.get_all_realtime_data()

    def update_original_funding_data(self, symbol: str, next_funding_time: str):
        """Délègue vers DataStorage."""
        self._storage.update_original_funding_data(symbol, next_funding_time)

    def get_original_funding_data(self, symbol: str) -> Optional[str]:
        """Délègue vers DataStorage."""
        return self._storage.get_original_funding_data(symbol)

    def get_all_original_funding_data(self) -> Dict[str, str]:
        """Délègue vers DataStorage."""
        return self._storage.get_all_original_funding_data()

    def set_symbol_lists(self, linear_symbols: List[str], inverse_symbols: List[str]):
        """Délègue vers DataStorage."""
        self._storage.set_symbol_lists(linear_symbols, inverse_symbols)

    def get_linear_symbols(self) -> List[str]:
        """Délègue vers DataStorage."""
        return self._storage.get_linear_symbols()

    def get_inverse_symbols(self) -> List[str]:
        """Délègue vers DataStorage."""
        return self._storage.get_inverse_symbols()

    def get_all_symbols(self) -> List[str]:
        """Délègue vers DataStorage."""
        return self._storage.get_all_symbols()

    def add_symbol_to_category(self, symbol: str, category: str):
        """Délègue vers DataStorage."""
        self._storage.add_symbol_to_category(symbol, category)

    def remove_symbol_from_category(self, symbol: str, category: str):
        """Délègue vers DataStorage."""
        self._storage.remove_symbol_from_category(symbol, category)

    def clear_all_data(self):
        """Délègue vers DataStorage."""
        self._storage.clear_all_data()

    def get_data_stats(self) -> Dict[str, int]:
        """Délègue vers DataStorage."""
        return self._storage.get_data_stats()

    def validate_data_integrity(self) -> bool:
        """Délègue vers DataValidator."""
        linear_symbols = self._storage.get_linear_symbols()
        inverse_symbols = self._storage.get_inverse_symbols()
        funding_data = self._storage.get_all_funding_data()

        return self._validator.validate_data_integrity(
            linear_symbols, inverse_symbols, funding_data
        )

    def get_loading_summary(self) -> Dict[str, Any]:
        """Délègue vers DataValidator."""
        linear_symbols = self._storage.get_linear_symbols()
        inverse_symbols = self._storage.get_inverse_symbols()
        funding_data = self._storage.get_all_funding_data()

        return self._validator.get_loading_summary(
            linear_symbols, inverse_symbols, funding_data
        )

    # ===== PROPRIÉTÉS POUR LA COMPATIBILITÉ =====

    @property
    def symbol_categories(self) -> Dict[str, str]:
        """Retourne les catégories de symboles pour la compatibilité."""
        return self._storage.symbol_categories

    @property
    def linear_symbols(self) -> List[str]:
        """Retourne les symboles linear pour la compatibilité."""
        return self._storage.linear_symbols

    @property
    def inverse_symbols(self) -> List[str]:
        """Retourne les symboles inverse pour la compatibilité."""
        return self._storage.inverse_symbols

    @property
    def funding_data(self) -> Dict:
        """Retourne les données de funding pour la compatibilité."""
        return self._storage.funding_data

    @property
    def realtime_data(self) -> Dict:
        """Retourne les données temps réel pour la compatibilité."""
        return self._storage.realtime_data
