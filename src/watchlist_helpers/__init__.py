#!/usr/bin/env python3
"""
Helpers pour le gestionnaire de watchlist.

Ce package contient les classes helper qui simplifient WatchlistManager
en extrayant les responsabilités de bas niveau :
- WatchlistDataPreparer : Préparation des données
- WatchlistFilterApplier : Application des filtres
- WatchlistResultBuilder : Construction des résultats
"""

from .data_preparer import WatchlistDataPreparer
from .filter_applier import WatchlistFilterApplier
from .result_builder import WatchlistResultBuilder

__all__ = [
    "WatchlistDataPreparer",
    "WatchlistFilterApplier",
    "WatchlistResultBuilder",
]
