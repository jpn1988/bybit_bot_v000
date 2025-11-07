#!/usr/bin/env python3
"""
Interface pour le gestionnaire de fallback des données.

Cette interface définit le contrat pour les gestionnaires de fallback des données,
permettant de découpler les dépendances circulaires.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class FallbackDataManagerInterface(ABC):
    """
    Interface pour les gestionnaires de fallback des données.

    Cette interface permet de découpler les dépendances circulaires
    entre les différents managers du bot.
    """

    @abstractmethod
    async def update_funding_data_periodically(self) -> None:
        """
        Met à jour périodiquement les données de funding via l'API REST.

        Cette méthode est appelée par le BotLifecycleManager.
        """
        pass

    @abstractmethod
    def get_funding_data_for_scheduler(self) -> Dict[str, Dict[str, Any]]:
        """
        Récupère les données de funding formatées pour le Scheduler.

        Returns:
            Dict[str, Dict[str, Any]]: Données de funding formatées
                - Clé: Symbole (ex: "BTCUSDT")
                - Valeur: Dict avec funding_rate, funding_time, etc.
        """
        pass

    @abstractmethod
    def set_data_manager(self, data_manager: Any) -> None:
        """
        Définit le gestionnaire de données.

        Args:
            data_manager: Gestionnaire de données
        """
        pass

    @abstractmethod
    def set_watchlist_manager(self, watchlist_manager: Any) -> None:
        """
        Définit le gestionnaire de watchlist.

        Args:
            watchlist_manager: Gestionnaire de watchlist
        """
        pass

    @abstractmethod
    def get_fallback_summary(self) -> Dict[str, Any]:
        """
        Retourne un résumé de l'état du fallback des données.

        Returns:
            Dict[str, Any]: Résumé de l'état du fallback
        """
        pass

