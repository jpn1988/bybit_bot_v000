"""
Price Formatter - Formatage des prix selon les règles Bybit.

Ce module formate les prix selon tick_size et les règles de précision.
"""

import logging
from typing import Optional

from .symbol_rules_cache import SymbolRulesCache


class PriceFormatter:
    """Formate les prix selon les règles Bybit."""

    def __init__(self, rules_cache: SymbolRulesCache, logger: Optional[logging.Logger] = None):
        self.rules_cache = rules_cache
        self.logger = logger or logging.getLogger(__name__)

    def format_price(self, symbol: str, price: float, category: str = "linear") -> str:
        """
        Formate le prix selon les règles de précision de Bybit pour le symbole donné.

        Args:
            symbol: Symbole de la paire
            price: Prix à formater
            category: Catégorie (linear, spot, etc.)

        Returns:
            str: Prix formaté selon les règles Bybit
        """
        try:
            tick_size = self.rules_cache.get_tick_size(symbol, category)

            # Arrondir selon le tick size
            formatted_price = round(price / tick_size) * tick_size

            # Déterminer le nombre de décimales à afficher
            decimal_places = self._calculate_decimal_places_from_tick_size(tick_size)

            return f"{formatted_price:.{decimal_places}f}"

        except Exception as e:
            self.logger.warning(f"[PRICE_FORMAT] ⚠️ Erreur formatage prix {symbol}: {e}")
            # Fallback simple
            return f"{price:.5f}"

    def _calculate_decimal_places_from_tick_size(self, tick_size: float) -> int:
        """Calcule le nombre de décimales à afficher selon le tick size."""
        if tick_size >= 1:
            return 0
        elif tick_size >= 0.1:
            return 1
        elif tick_size >= 0.01:
            return 2
        elif tick_size >= 0.001:
            return 3
        elif tick_size >= 0.0001:
            return 4
        elif tick_size >= 0.00001:
            return 5
        else:
            return 6

