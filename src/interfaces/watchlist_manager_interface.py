#!/usr/bin/env python3
"""
Interface pour le gestionnaire de watchlist.

Cette interface définit le contrat pour les gestionnaires de watchlist,
permettant de découpler les dépendances circulaires.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from volatility_tracker import VolatilityTracker


class WatchlistManagerInterface(ABC):
    """
    Interface pour les gestionnaires de watchlist.

    Cette interface permet de découpler les dépendances circulaires
    entre les différents managers du bot.
    """

    @abstractmethod
    def build_watchlist(
        self,
        base_url: str,
        perp_data: Dict,
        volatility_tracker: Any,
    ) -> Tuple[List[str], List[str], Dict]:
        """
        Construit la watchlist complète en appliquant tous les filtres.

        Args:
            base_url: URL de base de l'API Bybit
            perp_data: Données des perpétuels
            volatility_tracker: Tracker de volatilité pour le filtrage

        Returns:
            Tuple[linear_symbols, inverse_symbols, funding_data]
        """
        pass

    @abstractmethod
    def get_original_funding_data(self) -> Dict[str, str]:
        """
        Retourne les données de funding originales (next_funding_time).

        Returns:
            Dict[str, str]: Dictionnaire des next_funding_time originaux
        """
        pass

    @abstractmethod
    def set_symbol_categories(self, symbol_categories: Dict[str, str]) -> None:
        """
        Définit le mapping des catégories de symboles.

        Args:
            symbol_categories: Dictionnaire {symbol: category}
        """
        pass

    @abstractmethod
    def get_selected_symbols(self) -> List[str]:
        """
        Retourne la liste des symboles sélectionnés.

        Returns:
            List[str]: Liste des symboles de la watchlist
        """
        pass

