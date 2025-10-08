#!/usr/bin/env python3
"""
Gestionnaire de données unifié pour le bot Bybit - Version refactorisée.

Cette classe est une interface unifiée qui coordonne les différents composants spécialisés :
- DataCoordinator : Coordination des opérations complexes
- DataCompatibility : Compatibilité avec l'ancien code
- DataFetcher : Récupération des données
- DataStorage : Stockage thread-safe
- DataValidator : Validation des données

Cette version refactorisée améliore la lisibilité en séparant clairement les responsabilités.
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


class UnifiedDataManager:
    """
    Gestionnaire de données unifié pour le bot Bybit - Version refactorisée.

    Cette classe est une interface unifiée qui coordonne les différents composants spécialisés :
    - DataFetcher : Récupération des données de marché
    - DataStorage : Stockage thread-safe des données
    - DataValidator : Validation de l'intégrité des données

    Cette version simplifiée améliore la performance en supprimant les couches
    d'abstraction redondantes.
    """

    def __init__(self, testnet: bool = True, logger=None):
        """
        Initialise le gestionnaire de données unifié.

        Args:
            testnet: Utiliser le testnet (True) ou le marché réel (False)
            logger: Logger pour les messages (optionnel)
        """
        self.testnet = testnet
        self.logger = logger or setup_logging()

        # Initialiser les composants spécialisés
        self._fetcher = DataFetcher(logger=logger)
        self._storage = DataStorage(logger=logger)
        self._validator = DataValidator(logger=logger)

    # ===== MÉTHODES DE COORDINATION =====

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
        if not base_url or not isinstance(base_url, str):
            self.logger.error("❌ URL de base invalide")
            return False

        if not perp_data or not isinstance(perp_data, dict):
            self.logger.error("❌ Données perpétuels invalides")
            return False

        if not watchlist_manager:
            self.logger.error("❌ Gestionnaire de watchlist manquant")
            return False

        if not volatility_tracker:
            self.logger.error("❌ Tracker de volatilité manquant")
            return False

        return True

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

    # ===== MÉTHODES DE RÉCUPÉRATION =====

    def fetch_funding_map(
        self, base_url: str, category: str, timeout: int = 10
    ) -> Dict[str, Dict]:
        """
        Récupère les taux de funding pour une catégorie donnée.

        Args:
            base_url: URL de base de l'API Bybit
            category: Catégorie (linear ou inverse)
            timeout: Timeout pour les requêtes HTTP

        Returns:
            Dict[str, Dict]: Dictionnaire {symbol: {funding, volume, next_funding_time}}

        Raises:
            RuntimeError: En cas d'erreur HTTP ou API
        """
        return self._fetcher.fetch_funding_map(base_url, category, timeout)

    def fetch_spread_data(
        self,
        base_url: str,
        symbols: List[str],
        timeout: int = 10,
        category: str = "linear",
    ) -> Dict[str, float]:
        """
        Récupère les spreads via /v5/market/tickers paginé, puis filtre localement.

        Args:
            base_url: URL de base de l'API Bybit
            symbols: Liste cible des symboles à retourner
            timeout: Timeout HTTP
            category: "linear" ou "inverse"

        Returns:
            Dict[str, float]: map {symbol: spread_pct}
        """
        return self._fetcher.fetch_spread_data(base_url, symbols, timeout, category)

    def fetch_funding_data_parallel(
        self, base_url: str, categories: List[str], timeout: int = 10
    ) -> Dict[str, Dict]:
        """
        Récupère les données de funding pour plusieurs catégories en parallèle.

        Args:
            base_url: URL de base de l'API Bybit
            categories: Liste des catégories à récupérer
            timeout: Timeout pour les requêtes HTTP

        Returns:
            Dict[str, Dict]: Dictionnaire combiné de toutes les catégories
        """
        return self._fetcher.fetch_funding_data_parallel(base_url, categories, timeout)

    # ===== MÉTHODES DE STOCKAGE (DÉLÉGATION VERS DATA_STORAGE) =====

    def set_symbol_categories(self, symbol_categories: Dict[str, str]):
        """
        Définit le mapping des catégories de symboles.

        Args:
            symbol_categories: Dictionnaire {symbol: category}
        """
        self._storage.set_symbol_categories(symbol_categories)

    def update_funding_data(
        self,
        symbol: str,
        funding: float,
        volume: float,
        funding_time: str,
        spread: float,
        volatility: Optional[float] = None,
    ):
        """
        Met à jour les données de funding pour un symbole.

        Args:
            symbol: Symbole à mettre à jour
            funding: Taux de funding
            volume: Volume 24h
            funding_time: Temps restant avant funding
            spread: Spread en pourcentage
            volatility: Volatilité (optionnel)
        """
        self._storage.update_funding_data(
            symbol, funding, volume, funding_time, spread, volatility
        )

    def get_funding_data(
        self, symbol: str
    ) -> Optional[Tuple[float, float, str, float, Optional[float]]]:
        """
        Récupère les données de funding pour un symbole.

        Args:
            symbol: Symbole à récupérer

        Returns:
            Tuple des données de funding ou None si absent
        """
        return self._storage.get_funding_data(symbol)

    def get_all_funding_data(
        self,
    ) -> Dict[str, Tuple[float, float, str, float, Optional[float]]]:
        """
        Récupère toutes les données de funding.

        Returns:
            Dictionnaire des données de funding
        """
        return self._storage.get_all_funding_data()

    def update_realtime_data(self, symbol: str, ticker_data: Dict[str, Any]):
        """
        Met à jour les données en temps réel pour un symbole.

        Args:
            symbol: Symbole à mettre à jour
            ticker_data: Données du ticker reçues via WebSocket
        """
        self._storage.update_realtime_data(symbol, ticker_data)

    def update_price_data(
        self,
        symbol: str,
        mark_price: float,
        last_price: float,
        timestamp: float,
    ):
        """
        Met à jour les prix pour un symbole donné (compatibilité avec price_store.py).

        Args:
            symbol: Symbole du contrat (ex: BTCUSDT)
            mark_price: Prix de marque
            last_price: Dernier prix de transaction
            timestamp: Timestamp de la mise à jour
        """
        self._storage.update_price_data(symbol, mark_price, last_price, timestamp)

    def get_price_data(self, symbol: str) -> Optional[Dict[str, float]]:
        """
        Récupère les données de prix pour un symbole (compatibilité avec price_store.py).

        Args:
            symbol: Symbole du contrat

        Returns:
            Dictionnaire avec mark_price, last_price, timestamp ou None
        """
        return self._storage.get_price_data(symbol)

    def get_realtime_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les données en temps réel pour un symbole.

        Args:
            symbol: Symbole à récupérer

        Returns:
            Dictionnaire des données temps réel ou None si absent
        """
        return self._storage.get_realtime_data(symbol)

    def get_all_realtime_data(self) -> Dict[str, Dict[str, Any]]:
        """
        Récupère toutes les données en temps réel.

        Returns:
            Dictionnaire des données temps réel
        """
        return self._storage.get_all_realtime_data()

    def update_original_funding_data(self, symbol: str, next_funding_time: str):
        """
        Met à jour les données de funding originales.

        Args:
            symbol: Symbole à mettre à jour
            next_funding_time: Timestamp du prochain funding
        """
        self._storage.update_original_funding_data(symbol, next_funding_time)

    def get_original_funding_data(self, symbol: str) -> Optional[str]:
        """
        Récupère les données de funding originales pour un symbole.

        Args:
            symbol: Symbole à récupérer

        Returns:
            Timestamp du prochain funding ou None si absent
        """
        return self._storage.get_original_funding_data(symbol)

    def get_all_original_funding_data(self) -> Dict[str, str]:
        """
        Récupère toutes les données de funding originales.

        Returns:
            Dictionnaire des données de funding originales
        """
        return self._storage.get_all_original_funding_data()

    def set_symbol_lists(self, linear_symbols: List[str], inverse_symbols: List[str]):
        """
        Définit les listes de symboles par catégorie.

        Args:
            linear_symbols: Liste des symboles linear
            inverse_symbols: Liste des symboles inverse
        """
        self._storage.set_symbol_lists(linear_symbols, inverse_symbols)

    def get_linear_symbols(self) -> List[str]:
        """
        Récupère la liste des symboles linear.

        Returns:
            Liste des symboles linear
        """
        return self._storage.get_linear_symbols()

    def get_inverse_symbols(self) -> List[str]:
        """
        Récupère la liste des symboles inverse.

        Returns:
            Liste des symboles inverse
        """
        return self._storage.get_inverse_symbols()

    def get_all_symbols(self) -> List[str]:
        """
        Récupère tous les symboles (linear + inverse).

        Returns:
            Liste de tous les symboles
        """
        return self._storage.get_all_symbols()

    def add_symbol_to_category(self, symbol: str, category: str):
        """
        Ajoute un symbole à une catégorie.

        Args:
            symbol: Symbole à ajouter
            category: Catégorie ("linear" ou "inverse")
        """
        self._storage.add_symbol_to_category(symbol, category)

    def remove_symbol_from_category(self, symbol: str, category: str):
        """
        Retire un symbole d'une catégorie.

        Args:
            symbol: Symbole à retirer
            category: Catégorie ("linear" ou "inverse")
        """
        self._storage.remove_symbol_from_category(symbol, category)

    def clear_all_data(self):
        """
        Vide toutes les données stockées.
        """
        self._storage.clear_all_data()

    def get_data_stats(self) -> Dict[str, int]:
        """
        Retourne les statistiques des données stockées.

        Returns:
            Dictionnaire avec les statistiques
        """
        return self._storage.get_data_stats()

    # ===== MÉTHODES DE VALIDATION (DÉLÉGATION VERS DATA_VALIDATOR) =====

    def validate_data_integrity(self) -> bool:
        """
        Valide l'intégrité des données chargées.

        Returns:
            bool: True si les données sont valides
        """
        return self._storage.validate_data_integrity()

    def get_loading_summary(self) -> Dict[str, Any]:
        """
        Retourne un résumé du chargement des données.

        Returns:
            Dict[str, Any]: Résumé des données chargées
        """
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


# ===== FONCTIONS GLOBALES POUR LA COMPATIBILITÉ =====

# Instance globale pour la compatibilité avec price_store.py
_global_data_manager: Optional[UnifiedDataManager] = None


def _get_global_data_manager() -> UnifiedDataManager:
    """
    Récupère l'instance globale du gestionnaire de données.

    Returns:
        Instance du UnifiedDataManager
    """
    global _global_data_manager
    if _global_data_manager is None:
        _global_data_manager = UnifiedDataManager()
    return _global_data_manager


def set_global_data_manager(data_manager: UnifiedDataManager):
    """
    Définit l'instance globale du gestionnaire de données.

    Args:
        data_manager: Instance du UnifiedDataManager
    """
    global _global_data_manager
    _global_data_manager = data_manager


def update(symbol: str, mark_price: float, last_price: float, timestamp: float) -> None:
    """
    Met à jour les prix pour un symbole donné (compatibilité avec price_store.py).

    Args:
        symbol (str): Symbole du contrat (ex: BTCUSDT)
        mark_price (float): Prix de marque
        last_price (float): Dernier prix de transaction
        timestamp (float): Timestamp de la mise à jour
    """
    data_manager = _get_global_data_manager()
    data_manager.update_price_data(symbol, mark_price, last_price, timestamp)


def get_price_data(symbol: str) -> Optional[Dict[str, float]]:
    """
    Récupère les données de prix pour un symbole (compatibilité avec price_store.py).

    Args:
        symbol (str): Symbole du contrat

    Returns:
        Dictionnaire avec mark_price, last_price, timestamp ou None
    """
    data_manager = _get_global_data_manager()
    return data_manager.get_price_data(symbol)