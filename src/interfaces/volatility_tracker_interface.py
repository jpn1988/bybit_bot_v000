#!/usr/bin/env python3
"""
Interface pour le gestionnaire de volatilité.

Cette interface définit le contrat pour les gestionnaires de volatilité,
permettant de découpler les dépendances circulaires.
"""

from abc import ABC, abstractmethod
from typing import Dict


class VolatilityTrackerInterface(ABC):
    """
    Interface pour les gestionnaires de volatilité.

    Cette interface permet de découpler les dépendances circulaires
    entre les différents managers du bot.
    """

    @abstractmethod
    def set_symbol_categories(self, symbol_categories: Dict[str, str]) -> None:
        """
        Définit le mapping des catégories de symboles.

        Args:
            symbol_categories: Dictionnaire {symbol: category}
        """
        pass

