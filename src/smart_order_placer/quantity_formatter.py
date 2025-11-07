"""
Quantity Formatter - Formatage des quantités selon les règles Bybit.

Ce module formate les quantités selon qty_step, min_qty et quantity_precision.
"""

import logging
import math
from typing import Optional

from .symbol_rules_cache import SymbolRulesCache


class QuantityFormatter:
    """Formate les quantités selon les règles Bybit."""

    def __init__(self, rules_cache: SymbolRulesCache, logger: Optional[logging.Logger] = None):
        self.rules_cache = rules_cache
        self.logger = logger or logging.getLogger(__name__)

    def format_quantity(self, symbol: str, quantity: float, category: str, round_up: bool = False) -> str:
        """
        Formate la quantité selon les règles Bybit (qtyStep, minOrderQty).

        Args:
            symbol: Symbole Bybit
            quantity: Quantité souhaitée (float)
            category: "linear", "spot", etc.
            round_up: Si True, arrondit au pas supérieur (utile pour min notional)

        Returns:
            str: Quantité formatée
        """
        try:
            rules = self.rules_cache.get_quantity_rules(symbol, category)
            qty_step = rules['qty_step']
            min_qty = rules['min_qty']
            quantity_precision = rules.get('quantity_precision')

            # Arrondi au pas (avec sécurité pour ne pas tomber à 0)
            if round_up:
                steps = max(1, math.ceil(quantity / qty_step))
            else:
                steps = max(1, math.floor(quantity / qty_step))
            formatted = max(min_qty, steps * qty_step)

            if quantity_precision is not None and quantity_precision >= 0:
                formatted_str = f"{formatted:.{quantity_precision}f}"
            else:
                # Utiliser la fonction utilitaire pour calculer les décimales nécessaires
                decimals = self._calculate_decimal_precision_from_step(qty_step)
                formatted_str = f"{formatted:.{decimals}f}"

            if '.' in formatted_str:
                formatted_str = formatted_str.rstrip('0').rstrip('.') or '0'
            return formatted_str
        except Exception as e:
            self.logger.warning(f"[QTY_FORMAT] ⚠️ Erreur formatage quantité {symbol}: {e}")
            return f"{max(quantity, 0.001):.3f}".rstrip('0').rstrip('.')

    def _calculate_decimal_precision_from_step(self, qty_step: float) -> int:
        """
        Calcule le nombre de décimales nécessaires depuis qty_step.
        
        Args:
            qty_step: Pas de quantité (ex: 0.1, 0.01, 0.001)
        
        Returns:
            Nombre de décimales nécessaires (0-8 maximum)
        
        Examples:
            qty_step=1.0 -> 0 décimales
            qty_step=0.1 -> 1 décimale
            qty_step=0.01 -> 2 décimales
            qty_step=0.001 -> 3 décimales
        """
        if qty_step >= 1.0:
            # Pas entier, pas de décimales
            return 0
        elif qty_step == 0:
            # Pas zéro, utiliser 8 décimales par défaut (sécurité)
            return 8
        else:
            # Convertir qty_step en chaîne pour compter les décimales
            # Utiliser une approche robuste pour éviter les erreurs de floating point
            step_str = f"{qty_step:.10f}".rstrip('0').rstrip('.')
            if '.' in step_str:
                decimals = len(step_str.split('.')[1])
            else:
                decimals = 0
            
            # Limiter à 8 décimales maximum pour éviter les problèmes
            return min(decimals, 8)

