"""
Order Validator - Validation des ordres avant placement.

Ce module valide les ordres avant leur placement et détecte les erreurs non-récupérables.
"""

import re
import logging
from typing import Optional, Dict, Any

MIN_ORDER_VALUE_PATTERN = re.compile(r"([\d.]+)\s*USDT", re.IGNORECASE)


class OrderValidator:
    """Valide les ordres avant placement."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)

    def parse_min_notional_from_error(self, ret_msg: str) -> Optional[float]:
        """
        Tente d'extraire la valeur minimale d'ordre depuis un message Bybit.

        Args:
            ret_msg: Message d'erreur de l'API Bybit

        Returns:
            float: Valeur minimale détectée ou None
        """
        if not ret_msg:
            return None
        match = MIN_ORDER_VALUE_PATTERN.search(ret_msg)
        if not match:
            return None
        try:
            return float(match.group(1))
        except (TypeError, ValueError):
            return None

    def is_non_recoverable_error(self, ret_code: int, ret_msg: str) -> bool:
        """
        Détermine si une erreur est non-récupérable (ne doit pas être retentée).

        Args:
            ret_code: Code de retour de l'API
            ret_msg: Message d'erreur

        Returns:
            bool: True si l'erreur est non-récupérable
        """
        non_recoverable_errors = [
            170131,  # Insufficient balance
            170032,  # Insufficient wallet balance
            170033,  # Insufficient available balance
            30228,   # No new positions during delisting
        ]
        ret_msg_lower = ret_msg.lower() if isinstance(ret_msg, str) else ''
        is_delisting_error = (
            ret_code == 30228 or 
            "delisting" in ret_msg_lower or 
            "no new positions during" in ret_msg_lower
        )
        return (
            ret_code in non_recoverable_errors or 
            "insufficient balance" in ret_msg_lower or 
            is_delisting_error
        )

    def validate_order_value(self, qty: float, price: float, min_notional: float, safety_factor: float = 1.02) -> bool:
        """
        Valide que la valeur de l'ordre respecte le minimum notionnel.

        Args:
            qty: Quantité
            price: Prix
            min_notional: Minimum notionnel requis
            safety_factor: Facteur de sécurité (défaut: 1.02 = 2%)

        Returns:
            bool: True si la valeur est suffisante
        """
        order_value = qty * price
        required_value = min_notional * safety_factor
        return order_value >= required_value - 1e-6

