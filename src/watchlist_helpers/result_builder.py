#!/usr/bin/env python3
"""
Helper pour la construction des résultats de watchlist.

Cette classe extrait la logique de construction des résultats
du WatchlistManager pour améliorer la lisibilité.
"""

from typing import List, Tuple, Dict
from logging_setup import setup_logging


class WatchlistResultBuilder:
    """
    Helper pour construire les résultats finaux de la watchlist.

    Responsabilités :
    - Construction du dictionnaire de résultats
    - Séparation des symboles par catégorie
    - Validation des résultats finaux
    """

    def __init__(self, symbol_filter, symbol_categories, logger=None):
        """
        Initialise le constructeur de résultats.

        Args:
            symbol_filter: Instance de SymbolFilter
            symbol_categories: Mapping des catégories de symboles
            logger: Logger pour les messages (optionnel)
        """
        self.symbol_filter = symbol_filter
        self.symbol_categories = symbol_categories
        self.logger = logger or setup_logging()

    def build_final_results(
        self, final_symbols: List
    ) -> Tuple[List[str], List[str], Dict]:
        """
        Construit les résultats finaux à partir des symboles filtrés.

        Args:
            final_symbols: Liste des symboles après tous les filtres

        Returns:
            Tuple (linear_symbols, inverse_symbols, funding_data)
        """
        # Séparer les symboles par catégorie
        (
            linear_symbols,
            inverse_symbols,
        ) = self.symbol_filter.separate_symbols_by_category(
            final_symbols, self.symbol_categories
        )

        # Construire le dictionnaire de funding_data
        funding_data = self.symbol_filter.build_funding_data_dict(
            final_symbols
        )

        return linear_symbols, inverse_symbols, funding_data

    def build_final_watchlist(
        self, final_symbols: List
    ) -> Tuple[List[str], List[str], Dict]:
        """
        Construit et retourne la watchlist finale.

        Args:
            final_symbols: Symboles après tous les filtres

        Returns:
            Tuple (linear_symbols, inverse_symbols, funding_data)
        """
        # Vérifier s'il y a des résultats
        if not final_symbols:
            self.logger.warning(
                "⚠️ Aucun symbole ne correspond aux critères de filtrage"
            )
            return [], [], {}

        # Construire les résultats finaux
        return self.build_final_results(final_symbols)
