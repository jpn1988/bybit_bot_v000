"""
Order Retry Handler - Gestion des retries et ajustements de prix.

Ce module gère la logique de retry et les ajustements de prix pour les ordres.
"""

import logging
from typing import Optional, Dict, Any

from .symbol_rules_cache import SymbolRulesCache
from .orderbook_manager import OrderbookManager


class OrderRetryHandler:
    """Gère les retries et ajustements de prix."""

    def __init__(
        self,
        rules_cache: SymbolRulesCache,
        orderbook_manager: OrderbookManager,
        logger: Optional[logging.Logger] = None
    ):
        self.rules_cache = rules_cache
        self.orderbook_manager = orderbook_manager
        self.logger = logger or logging.getLogger(__name__)

    def compute_join_quote_price(self, symbol: str, side: str, category: str, fallback_price: float) -> float:
        """
        Calcule un prix 'join-quote' proche du meilleur prix, tout en restant maker.

        - Buy: au niveau du best bid (ou juste sous le best ask de 1 tick)
        - Sell: au niveau du best ask (ou juste au-dessus du best bid de 1 tick)

        Args:
            symbol: Symbole de la paire
            side: "Buy" ou "Sell"
            category: Catégorie (linear, spot, etc.)
            fallback_price: Prix de fallback si l'orderbook n'est pas disponible

        Returns:
            float: Prix join-quote calculé
        """
        try:
            ob = self.orderbook_manager.get_cached_orderbook(symbol, category)
            if not ob or not ob.get('b') or not ob.get('a'):
                return fallback_price
            best_bid = float(ob['b'][0][0])
            best_ask = float(ob['a'][0][0])
            tick = self.rules_cache.get_tick_size(symbol, category)
            if side == "Buy":
                candidate = best_ask - tick
                if candidate <= 0:
                    candidate = best_bid
                price = max(best_bid, candidate)
            else:
                candidate = best_bid + tick
                price = min(best_ask, candidate)
                if price <= best_bid:
                    price = best_bid + tick
            return price
        except Exception:
            return fallback_price

    def adjust_price_for_retry(self, current_price: float, side: str, base_offset: float, retry: int) -> float:
        """
        Ajuste le prix pour un retry (plus agressif).

        Args:
            current_price: Prix actuel
            side: "Buy" ou "Sell"
            base_offset: Offset de base
            retry: Numéro de retry (0 = première tentative)

        Returns:
            float: Nouveau prix ajusté
        """
        # Réduire l'offset de 20% à chaque retry
        adjustment_factor = 0.8 ** retry
        new_offset = base_offset * adjustment_factor

        if side == "Buy":
            # Pour un achat, réduire encore plus le prix
            return current_price * (1 - new_offset)
        else:
            # Pour une vente, augmenter encore plus le prix
            return current_price * (1 + new_offset)

