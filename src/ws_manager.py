#!/usr/bin/env python3
"""
Gestionnaire WebSocket refactorisé pour le bot Bybit.

Ce fichier maintient la compatibilité avec l'interface existante tout en utilisant
les modules spécialisés pour une meilleure maintenabilité.

IMPORTANT: Ce fichier remplace ws_manager.py après validation.
"""

# Import de la nouvelle implémentation modulaire
try:
    # Import relatif (quand utilisé comme module)
    from .ws.manager import WebSocketManager as RefactoredWebSocketManager
except ImportError:
    # Import absolu (quand exécuté directement)
    from ws.manager import WebSocketManager as RefactoredWebSocketManager

# Alias pour maintenir la compatibilité
WebSocketManager = RefactoredWebSocketManager

# Export de l'interface pour les imports existants
__all__ = ['WebSocketManager']
