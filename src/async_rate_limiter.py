#!/usr/bin/env python3
"""
Rate Limiter asynchrone pour contrôler la fréquence des requêtes API.

Cette classe permet de limiter le nombre d'appels par fenêtre de temps
pour respecter les limites de l'API Bybit.
"""

import asyncio
import time
import os
from collections import deque
from typing import Optional


class AsyncRateLimiter:
    """
    Rate limiter asynchrone avec fenêtre glissante.
    
    Responsabilité unique : Limiter la fréquence des appels asynchrones.
    """

    def __init__(self, max_calls: int = 5, window_seconds: float = 1.0):
        """
        Initialise le rate limiter.

        Args:
            max_calls: Nombre maximum d'appels par fenêtre
            window_seconds: Durée de la fenêtre en secondes
        """
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._timestamps = deque()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """
        Attend de manière asynchrone si nécessaire pour respecter la limite.
        
        Cette méthode doit être appelée avant chaque requête API pour
        garantir le respect des limites de taux.
        """
        while True:
            now = time.time()
            async with self._lock:
                # Retirer les timestamps hors fenêtre
                while (
                    self._timestamps
                    and now - self._timestamps[0] > self.window_seconds
                ):
                    self._timestamps.popleft()
                
                # Vérifier si on peut faire l'appel
                if len(self._timestamps) < self.max_calls:
                    self._timestamps.append(now)
                    return
                
                # Calculer le temps à attendre
                wait_time = self.window_seconds - (now - self._timestamps[0])
            
            # Attendre en dehors du lock
            if wait_time > 0:
                await asyncio.sleep(min(wait_time, 0.05))

    def reset(self):
        """Réinitialise le rate limiter (vide l'historique)."""
        self._timestamps.clear()

    def get_current_count(self) -> int:
        """
        Retourne le nombre d'appels dans la fenêtre actuelle.
        
        Returns:
            Nombre d'appels dans la fenêtre courante
        """
        now = time.time()
        # Nettoyer les anciens timestamps
        while (
            self._timestamps
            and now - self._timestamps[0] > self.window_seconds
        ):
            self._timestamps.popleft()
        return len(self._timestamps)


def get_async_rate_limiter(
    max_calls: Optional[int] = None, window_seconds: Optional[float] = None
) -> AsyncRateLimiter:
    """
    Construit un rate limiter asynchrone à partir des variables d'environnement
    ou des paramètres fournis.

    Args:
        max_calls: Nombre maximum d'appels (utilise env si None)
        window_seconds: Durée de la fenêtre (utilise env si None)

    Returns:
        Instance configurée d'AsyncRateLimiter
    """
    # Utiliser les paramètres fournis ou lire depuis l'environnement
    if max_calls is None:
        try:
            max_calls = int(os.getenv("PUBLIC_HTTP_MAX_CALLS_PER_SEC", "5"))
        except (ValueError, TypeError) as e:
            import logging
            logging.getLogger(__name__).warning(
                f"Erreur conversion PUBLIC_HTTP_MAX_CALLS_PER_SEC: {e}"
            )
            max_calls = 5

    if window_seconds is None:
        try:
            window_seconds = float(os.getenv("PUBLIC_HTTP_WINDOW_SECONDS", "1"))
        except (ValueError, TypeError) as e:
            import logging
            logging.getLogger(__name__).warning(
                f"Erreur conversion PUBLIC_HTTP_WINDOW_SECONDS: {e}"
            )
            window_seconds = 1.0

    return AsyncRateLimiter(max_calls=max_calls, window_seconds=window_seconds)

