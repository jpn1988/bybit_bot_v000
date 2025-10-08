#!/usr/bin/env python3
"""
Gestionnaire de threads pour le bot Bybit.

Cette classe est maintenant simplifiée et ne contient plus de méthodes inutiles.
"""

try:
    from .logging_setup import setup_logging
except ImportError:
    from logging_setup import setup_logging


class ThreadManager:
    """
    Gestionnaire de threads pour le bot Bybit.

    Cette classe a été simplifiée - les méthodes complexes d'arrêt forcé
    ont été supprimées car elles n'étaient pas utilisées.
    """

    def __init__(self, logger=None):
        """
        Initialise le gestionnaire de threads.

        Args:
            logger: Logger pour les messages (optionnel)
        """
        self.logger = logger or setup_logging()

