"""
Dynamic Price Calculator - Calcul des prix dynamiques selon la liquidité.

Ce module calcule le prix limite optimal pour un ordre maker.
"""

import logging
from typing import Dict, Any, Optional, Tuple

from .liquidity_classifier import LiquidityClassifier

# Configuration des offsets dynamiques par niveau de liquidité
MAKER_OFFSET_LEVELS = {
    "high_liquidity": 0.0002,    # 0.02% - paires très liquides
    "medium_liquidity": 0.0005,  # 0.05% - paires normales
    "low_liquidity": 0.001,      # 0.10% - paires peu liquides
}


class DynamicPriceCalculator:
    """Calcule le prix limite optimal selon la liquidité détectée."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.liquidity_classifier = LiquidityClassifier(logger)

    def compute_dynamic_price(self, symbol: str, side: str, orderbook: Dict[str, Any]) -> Tuple[float, str, float]:
        """
        Calcule le prix limite dynamique pour un ordre maker.

        Args:
            symbol: Symbole de la paire
            side: "Buy" ou "Sell"
            orderbook: Données du carnet d'ordres

        Returns:
            Tuple[float, str, float]: (prix_calculé, niveau_liquidité, offset_percent)
        """
        try:
            if not orderbook or 'b' not in orderbook or 'a' not in orderbook:
                raise ValueError("Carnet d'ordres invalide")

            bids = orderbook.get('b', [])
            asks = orderbook.get('a', [])

            if not bids or not asks:
                raise ValueError("Pas de données bid/ask")

            best_bid = float(bids[0][0])
            best_ask = float(asks[0][0])

            # Classifier la liquidité
            liquidity_level = self.liquidity_classifier.classify_liquidity(orderbook)
            offset_percent = MAKER_OFFSET_LEVELS[liquidity_level]

            # Calculer le prix limite selon le côté
            if side == "Buy":
                # Pour un achat, on place en dessous du best bid
                limit_price = best_bid * (1 - offset_percent)
            else:
                # Pour une vente, on place au-dessus du best ask
                limit_price = best_ask * (1 + offset_percent)

            self.logger.debug(
                f"💰 [PRICE_CALC] {symbol} {side}: "
                f"bid={best_bid:.6f}, ask={best_ask:.6f}, "
                f"liquidity={liquidity_level}, offset={offset_percent*100:.3f}%, "
                f"price={limit_price:.6f}"
            )

            return limit_price, liquidity_level, offset_percent

        except Exception as e:
            self.logger.error(f"❌ [PRICE_CALC] Erreur calcul prix {symbol}: {e}")
            # Fallback sur prix moyen avec offset medium
            if 'b' in orderbook and 'a' in orderbook and orderbook['b'] and orderbook['a']:
                best_bid = float(orderbook['b'][0][0])
                best_ask = float(orderbook['a'][0][0])
                mid_price = (best_bid + best_ask) / 2
                offset_percent = MAKER_OFFSET_LEVELS["medium_liquidity"]

                if side == "Buy":
                    limit_price = mid_price * (1 - offset_percent)
                else:
                    limit_price = mid_price * (1 + offset_percent)

                return limit_price, "medium_liquidity", offset_percent
            else:
                raise

