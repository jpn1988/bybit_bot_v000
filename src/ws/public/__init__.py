#!/usr/bin/env python3
"""
Sous-package WebSocket public (Bybit v5).

Contient des composants modulaires pour le client WebSocket public:
- subscriptions.py: Construction des topics de souscription
- parser_router.py: Parsing et routage des messages
- transport.py: Gestion du backoff et de l'attente entre reconnexions
- models.py: Dataclasses pour les données structurées
"""

__all__ = [
    "subscriptions",
    "parser_router",
    "transport",
    "models",
]


