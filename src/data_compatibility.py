#!/usr/bin/env python3
"""
Gestionnaire de compatibilité pour le bot Bybit - Version refactorisée.

Cette classe gère uniquement :
- La compatibilité avec l'ancien code
- Les fonctions globales de compatibilité
- L'interface de transition
"""

from typing import Dict, List, Optional, Tuple, Any
try:
    from .logging_setup import setup_logging
    from .data_coordinator import DataCoordinator
except ImportError:
    from logging_setup import setup_logging
    from data_coordinator import DataCoordinator


class DataCompatibility:
    """
    Gestionnaire de compatibilité pour le bot Bybit.

    Responsabilités :
    - Compatibilité avec l'ancien code
    - Fonctions globales de compatibilité
    - Interface de transition
    """

    def __init__(self, testnet: bool, logger=None):
        """
        Initialise le gestionnaire de compatibilité.

        Args:
            testnet: Utiliser le testnet (True) ou le marché réel (False)
            logger: Logger pour les messages (optionnel)
        """
        self.testnet = testnet
        self.logger = logger or setup_logging()
        self._coordinator = DataCoordinator(testnet, logger)

    # ===== MÉTHODES DE COMPATIBILITÉ =====

    def load_watchlist_data(
        self,
        base_url: str,
        perp_data: Dict,
        watchlist_manager,
        volatility_tracker,
    ) -> bool:
        """
        Interface de compatibilité pour charger les données de la watchlist.

        Args:
            base_url: URL de base de l'API
            perp_data: Données des perpétuels
            watchlist_manager: Gestionnaire de watchlist
            volatility_tracker: Tracker de volatilité

        Returns:
            bool: True si le chargement a réussi
        """
        return self._coordinator.load_watchlist_data(
            base_url, perp_data, watchlist_manager, volatility_tracker
        )

    # ===== DÉLÉGATION VERS LE COORDINATEUR =====

    def fetch_funding_map(self, base_url: str, category: str, timeout: int = 10) -> Dict[str, Dict]:
        """Délègue vers DataCoordinator."""
        return self._coordinator.fetch_funding_map(base_url, category, timeout)

    def fetch_spread_data(self, base_url: str, symbols: List[str], timeout: int = 10, category: str = "linear") -> Dict[str, float]:
        """Délègue vers DataCoordinator."""
        return self._coordinator.fetch_spread_data(base_url, symbols, timeout, category)

    def fetch_funding_data_parallel(self, base_url: str, categories: List[str], timeout: int = 10) -> Dict[str, Dict]:
        """Délègue vers DataCoordinator."""
        return self._coordinator.fetch_funding_data_parallel(base_url, categories, timeout)

    def set_symbol_categories(self, symbol_categories: Dict[str, str]):
        """Délègue vers DataCoordinator."""
        self._coordinator.set_symbol_categories(symbol_categories)

    def update_funding_data(self, symbol: str, funding: float, volume: float, funding_time: str, spread: float, volatility: Optional[float] = None):
        """Délègue vers DataCoordinator."""
        self._coordinator.update_funding_data(symbol, funding, volume, funding_time, spread, volatility)

    def get_funding_data(self, symbol: str) -> Optional[Tuple[float, float, str, float, Optional[float]]]:
        """Délègue vers DataCoordinator."""
        return self._coordinator.get_funding_data(symbol)

    def get_all_funding_data(self) -> Dict[str, Tuple[float, float, str, float, Optional[float]]]:
        """Délègue vers DataCoordinator."""
        return self._coordinator.get_all_funding_data()

    def update_realtime_data(self, symbol: str, ticker_data: Dict[str, Any]):
        """Délègue vers DataCoordinator."""
        self._coordinator.update_realtime_data(symbol, ticker_data)

    def update_price_data(self, symbol: str, mark_price: float, last_price: float, timestamp: float):
        """Délègue vers DataCoordinator."""
        self._coordinator.update_price_data(symbol, mark_price, last_price, timestamp)

    def get_price_data(self, symbol: str) -> Optional[Dict[str, float]]:
        """Délègue vers DataCoordinator."""
        return self._coordinator.get_price_data(symbol)

    def get_realtime_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Délègue vers DataCoordinator."""
        return self._coordinator.get_realtime_data(symbol)

    def get_all_realtime_data(self) -> Dict[str, Dict[str, Any]]:
        """Délègue vers DataCoordinator."""
        return self._coordinator.get_all_realtime_data()

    def update_original_funding_data(self, symbol: str, next_funding_time: str):
        """Délègue vers DataCoordinator."""
        self._coordinator.update_original_funding_data(symbol, next_funding_time)

    def get_original_funding_data(self, symbol: str) -> Optional[str]:
        """Délègue vers DataCoordinator."""
        return self._coordinator.get_original_funding_data(symbol)

    def get_all_original_funding_data(self) -> Dict[str, str]:
        """Délègue vers DataCoordinator."""
        return self._coordinator.get_all_original_funding_data()

    def set_symbol_lists(self, linear_symbols: List[str], inverse_symbols: List[str]):
        """Délègue vers DataCoordinator."""
        self._coordinator.set_symbol_lists(linear_symbols, inverse_symbols)

    def get_linear_symbols(self) -> List[str]:
        """Délègue vers DataCoordinator."""
        return self._coordinator.get_linear_symbols()

    def get_inverse_symbols(self) -> List[str]:
        """Délègue vers DataCoordinator."""
        return self._coordinator.get_inverse_symbols()

    def get_all_symbols(self) -> List[str]:
        """Délègue vers DataCoordinator."""
        return self._coordinator.get_all_symbols()

    def add_symbol_to_category(self, symbol: str, category: str):
        """Délègue vers DataCoordinator."""
        self._coordinator.add_symbol_to_category(symbol, category)

    def remove_symbol_from_category(self, symbol: str, category: str):
        """Délègue vers DataCoordinator."""
        self._coordinator.remove_symbol_from_category(symbol, category)

    def clear_all_data(self):
        """Délègue vers DataCoordinator."""
        self._coordinator.clear_all_data()

    def get_data_stats(self) -> Dict[str, int]:
        """Délègue vers DataCoordinator."""
        return self._coordinator.get_data_stats()

    def validate_data_integrity(self) -> bool:
        """Délègue vers DataCoordinator."""
        return self._coordinator.validate_data_integrity()

    def get_loading_summary(self) -> Dict[str, Any]:
        """Délègue vers DataCoordinator."""
        return self._coordinator.get_loading_summary()

    # ===== PROPRIÉTÉS POUR LA COMPATIBILITÉ =====

    @property
    def symbol_categories(self) -> Dict[str, str]:
        """Retourne les catégories de symboles pour la compatibilité."""
        return self._coordinator.symbol_categories

    @property
    def linear_symbols(self) -> List[str]:
        """Retourne les symboles linear pour la compatibilité."""
        return self._coordinator.linear_symbols

    @property
    def inverse_symbols(self) -> List[str]:
        """Retourne les symboles inverse pour la compatibilité."""
        return self._coordinator.inverse_symbols

    @property
    def funding_data(self) -> Dict:
        """Retourne les données de funding pour la compatibilité."""
        return self._coordinator.funding_data

    @property
    def realtime_data(self) -> Dict:
        """Retourne les données temps réel pour la compatibilité."""
        return self._coordinator.realtime_data


# ===== FONCTIONS GLOBALES POUR LA COMPATIBILITÉ =====

# Instance globale pour la compatibilité avec price_store.py
_global_data_manager: Optional[DataCompatibility] = None


def _get_global_data_manager() -> DataCompatibility:
    """
    Récupère l'instance globale du gestionnaire de données.

    Returns:
        Instance du DataCompatibility
    """
    global _global_data_manager
    if _global_data_manager is None:
        _global_data_manager = DataCompatibility(testnet=True)
    return _global_data_manager


def set_global_data_manager(data_manager: DataCompatibility):
    """
    Définit l'instance globale du gestionnaire de données.

    Args:
        data_manager: Instance du DataCompatibility
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
