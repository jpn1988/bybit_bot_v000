"""
Liquidity Classifier - Classification de la liquidité d'une paire.

Ce module analyse l'order book pour déterminer le niveau de liquidité.
"""

import logging
from typing import Dict, Any, Optional

# Seuils de classification de liquidité
LIQUIDITY_THRESHOLDS = {
    "spread_high": 0.0005,       # spread < 0.05% = haute liquidité
    "spread_medium": 0.002,      # spread < 0.20% = moyenne liquidité
    "orderbook_depth_high": 50000,  # volume top 10 > 50k USDT
    "orderbook_depth_medium": 10000, # volume top 10 > 10k USDT
}


class LiquidityClassifier:
    """Analyse la liquidité d'une paire basée sur le spread et la profondeur du carnet."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)

    def classify_liquidity(self, orderbook: Dict[str, Any]) -> str:
        """
        Classifie la liquidité d'une paire basée sur le carnet d'ordres.

        Args:
            orderbook: Données du carnet d'ordres de Bybit

        Returns:
            str: "high_liquidity", "medium_liquidity", ou "low_liquidity"
        """
        try:
            if not orderbook or 'b' not in orderbook or 'a' not in orderbook:
                self.logger.warning("[LIQUIDITY] ⚠️ Carnet d'ordres invalide, fallback medium")
                return "medium_liquidity"

            bids = orderbook.get('b', [])
            asks = orderbook.get('a', [])

            if not bids or not asks:
                self.logger.warning("[LIQUIDITY] ⚠️ Pas de données bid/ask, fallback medium")
                return "medium_liquidity"

            # Calculer le spread relatif
            best_bid = float(bids[0][0])
            best_ask = float(asks[0][0])
            spread_relative = (best_ask - best_bid) / best_bid

            # Calculer la profondeur (top 10 niveaux)
            depth_usdt = self._calculate_orderbook_depth(bids, asks, best_bid, best_ask)

            # Classification multi-critères
            if (spread_relative < LIQUIDITY_THRESHOLDS["spread_high"] and
                depth_usdt > LIQUIDITY_THRESHOLDS["orderbook_depth_high"]):
                return "high_liquidity"
            elif (spread_relative < LIQUIDITY_THRESHOLDS["spread_medium"] and
                  depth_usdt > LIQUIDITY_THRESHOLDS["orderbook_depth_medium"]):
                return "medium_liquidity"
            else:
                return "low_liquidity"

        except Exception as e:
            self.logger.error(f"❌ [LIQUIDITY] Erreur classification: {e}")
            return "medium_liquidity"  # Fallback sécurisé

    def _calculate_orderbook_depth(self, bids: list, asks: list, best_bid: float, best_ask: float) -> float:
        """Calcule la profondeur du carnet en USDT (top 10 niveaux)."""
        try:
            depth_usdt = 0.0

            # Somme des volumes bid (top 10)
            for i, (price_str, size_str) in enumerate(bids[:10]):
                price = float(price_str)
                size = float(size_str)
                depth_usdt += price * size

            # Somme des volumes ask (top 10)
            for i, (price_str, size_str) in enumerate(asks[:10]):
                price = float(price_str)
                size = float(size_str)
                depth_usdt += price * size

            return depth_usdt

        except Exception as e:
            self.logger.warning(f"[LIQUIDITY] ⚠️ Erreur calcul profondeur: {e}")
            return 0.0

