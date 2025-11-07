"""
Orderbook Manager - Gestion du cache et récupération de l'orderbook.

Ce module gère le cache de l'orderbook pour éviter les appels API répétés.
"""

import time
import threading
import logging
from typing import Dict, Any, Optional

from utils.executors import GLOBAL_EXECUTOR

# Cache global pour l'orderbook
_orderbook_cache = {}
_cache_lock = threading.Lock()
CACHE_TTL = 2  # secondes


class OrderbookManager:
    """Gère le cache et la récupération de l'orderbook."""

    def __init__(self, bybit_client, logger: Optional[logging.Logger] = None):
        self.bybit_client = bybit_client
        self.logger = logger or logging.getLogger(__name__)

    def get_cached_orderbook(self, symbol: str, category: str) -> Optional[Dict[str, Any]]:
        """
        Récupère le carnet d'ordres avec cache pour éviter les appels répétés.

        Args:
            symbol: Symbole de la paire
            category: Catégorie (linear, spot, etc.)

        Returns:
            Dict contenant les données de l'orderbook ou None en cas d'erreur
        """
        cache_key = f"{symbol}_{category}"
        current_time = time.time()

        with _cache_lock:
            # Vérifier le cache
            if cache_key in _orderbook_cache:
                cached_data, timestamp = _orderbook_cache[cache_key]
                if current_time - timestamp < CACHE_TTL:
                    return cached_data
                else:
                    del _orderbook_cache[cache_key]

        # Récupérer depuis l'API
        try:
            executor = GLOBAL_EXECUTOR
            future = executor.submit(
                self.bybit_client.get_orderbook,
                category=category,
                symbol=symbol,
                limit=10
            )
            orderbook = future.result()

            # Mettre en cache
            with _cache_lock:
                _orderbook_cache[cache_key] = (orderbook, current_time)

            return orderbook

        except Exception as e:
            self.logger.error(f"❌ [CACHE] Erreur récupération carnet {symbol}: {e}")
            return None

