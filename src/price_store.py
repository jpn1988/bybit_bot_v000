"""Module pour stocker et gérer les prix en temps réel."""

import threading
from typing import Dict


# Stockage global des prix (protégé par verrou)
_price_data: Dict[str, Dict[str, float]] = {}
_price_lock = threading.Lock()


def update(symbol: str, mark_price: float, last_price: float, timestamp: float) -> None:
    """
    Met à jour les prix pour un symbole donné.

    Args:
        symbol (str): Symbole du contrat (ex: BTCUSDT)
        mark_price (float): Prix de marque
        last_price (float): Dernier prix de transaction
        timestamp (float): Timestamp de la mise à jour
    """
    with _price_lock:
        _price_data[symbol] = {
            "mark_price": mark_price,
            "last_price": last_price,
            "timestamp": timestamp
        }
