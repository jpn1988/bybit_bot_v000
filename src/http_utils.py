"""Utilitaires HTTP: rate limiter simple."""

import os
import time
import threading
from collections import deque


class RateLimiter:
    """Rate limiter simple (fenêtre glissante) thread-safe.

    max_calls: nombre max d'appels dans window_seconds.
    """

    def __init__(self, max_calls: int = 5, window_seconds: float = 1.0):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._timestamps = deque()
        self._lock = threading.Lock()

    def acquire(self):
        """Bloque si nécessaire pour respecter la limite."""
        while True:
            now = time.time()
            with self._lock:
                # Retirer les timestamps hors fenêtre
                while self._timestamps and now - self._timestamps[0] > self.window_seconds:
                    self._timestamps.popleft()
                if len(self._timestamps) < self.max_calls:
                    self._timestamps.append(now)
                    return
                # Temps à attendre jusqu'à expiration du plus ancien
                wait_time = self.window_seconds - (now - self._timestamps[0])
            if wait_time > 0:
                time.sleep(min(wait_time, 0.05))


def get_rate_limiter() -> RateLimiter:
    """Construit un rate limiter à partir des variables d'environnement."""
    try:
        max_calls = int(os.getenv("PUBLIC_HTTP_MAX_CALLS_PER_SEC", "5"))
        window = float(os.getenv("PUBLIC_HTTP_WINDOW_SECONDS", "1"))
    except Exception:
        max_calls = 5
        window = 1.0
    return RateLimiter(max_calls=max_calls, window_seconds=window)


