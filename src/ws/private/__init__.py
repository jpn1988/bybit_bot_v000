#!/usr/bin/env python3
"""
Sous-package WebSocket privé (Bybit v5).

Composants:
- auth.py: AuthManager (signature HMAC + message d'auth)
- watchdog.py: AuthWatchdog (surveillance auth/connexion)
- router.py: PrivateMessageRouter (routing des messages privés)
"""

__all__ = [
    "auth",
    "watchdog",
    "router",
]


