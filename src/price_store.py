"""Module pour stocker et gérer les prix en temps réel."""

import time
from typing import Dict, Tuple


# Stockage global des prix
_price_data: Dict[str, Dict[str, float]] = {}


def update(symbol: str, mark_price: float, last_price: float, timestamp: float) -> None:
    """
    Met à jour les prix pour un symbole donné.
    
    Args:
        symbol (str): Symbole du contrat (ex: BTCUSDT)
        mark_price (float): Prix de marque
        last_price (float): Dernier prix de transaction
        timestamp (float): Timestamp de la mise à jour
    """
    _price_data[symbol] = {
        "mark_price": mark_price,
        "last_price": last_price,
        "timestamp": timestamp
    }


def get_snapshot() -> Dict[str, Dict[str, float]]:
    """
    Récupère un instantané de tous les prix stockés.
    
    Returns:
        Dict[str, Dict[str, float]]: Dictionnaire des prix par symbole
    """
    return _price_data.copy()


def get_age_seconds(symbol: str) -> float:
    """
    Calcule l'âge en secondes des données pour un symbole.
    
    Args:
        symbol (str): Symbole du contrat
        
    Returns:
        float: Âge en secondes, ou -1 si pas de données
    """
    if symbol not in _price_data:
        return -1
    
    current_time = time.time()
    data_time = _price_data[symbol]["timestamp"]
    return current_time - data_time
