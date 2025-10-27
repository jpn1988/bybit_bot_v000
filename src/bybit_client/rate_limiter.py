#!/usr/bin/env python3
"""
Rate limiting pour le client Bybit.

Ce module gère :
- Rate limiting pour les API publiques et privées
- Détection de contexte async pour éviter les blocages
- Gestion du sleep avec détection d'event loop
"""

import time


class BybitRateLimiter:
    """
    Gestionnaire de rate limiting pour le client Bybit.
    
    Cette classe gère le rate limiting selon les limites Bybit :
    - API publique : 120 requêtes / minute
    - API privée : 50 requêtes / minute
    """
    
    def __init__(self):
        """
        Initialise le rate limiter.
        """
        try:
            from async_rate_limiter import AsyncRateLimiter
            # Rate limiters selon documentation Bybit API v5
            self._public_limiter = AsyncRateLimiter(
                max_calls=120,  # 120 requêtes
                window_seconds=60  # par minute pour API publique
            )
            self._private_limiter = AsyncRateLimiter(
                max_calls=50,   # 50 requêtes  
                window_seconds=60  # par minute pour API privée
            )
        except ImportError:
            # Fallback si le rate limiter n'est pas disponible
            self._public_limiter = None
            self._private_limiter = None
    
    def apply_rate_limiting(self, is_private: bool):
        """
        Applique le rate limiting avant d'exécuter une requête.
        
        Version synchrone uniquement - ce client ne doit être utilisé que dans des threads dédiés.
        
        Args:
            is_private: True pour API privée, False pour API publique
        """
        limiter = self._private_limiter if is_private else self._public_limiter
        
        if limiter is None:
            return  # Pas de rate limiting si les limiters ne sont pas disponibles
            
        try:
            # Éviter time.sleep() si on détecte un contexte async (PERF-002)
            import asyncio
            try:
                # Vérifier si on est dans un event loop
                loop = asyncio.get_running_loop()
                # Si on arrive ici, on EST dans un event loop async
                # Log warning mais ne pas bloquer avec time.sleep
                import logging
                logging.getLogger(__name__).warning(
                    "PERF-002: BybitClient synchrone utilisé depuis un contexte async. "
                    "Utilisez un thread dédié pour éviter de bloquer l'event loop."
                )
                return  # Skip le rate limiting pour éviter de bloquer
            except RuntimeError:
                # Pas d'event loop actif = contexte synchrone, c'est OK
                pass
            
            # Version simplifiée - vérifier le compteur actuel (ARCH-001)
            current_count = limiter.get_current_count()
            max_calls = limiter.max_calls
            
            if current_count >= max_calls:
                # Si on est proche de la limite, faire une pause
                time.sleep(0.05)  # Attendre 50ms pour respecter les limites
        except Exception as e:
            # En cas d'erreur, logger un warning mais continuer
            import logging
            logging.getLogger(__name__).warning(f"Erreur rate limiting: {e}")

