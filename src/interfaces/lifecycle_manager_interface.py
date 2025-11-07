#!/usr/bin/env python3
"""
Interface pour le gestionnaire du cycle de vie du bot.

Cette interface définit le contrat pour les gestionnaires du cycle de vie,
permettant de découpler les dépendances circulaires.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Callable, Optional


class LifecycleManagerInterface(ABC):
    """
    Interface pour les gestionnaires du cycle de vie du bot.

    Cette interface permet de découpler les dépendances circulaires
    entre les différents managers du bot.
    """

    @abstractmethod
    async def start_lifecycle(self, components: Dict[str, Any]) -> None:
        """
        Démarre le cycle de vie du bot.

        Args:
            components: Dictionnaire des composants du bot
        """
        pass

    @abstractmethod
    async def stop_lifecycle(self, components: Dict[str, Any]) -> None:
        """
        Arrête le cycle de vie du bot.

        Args:
            components: Dictionnaire des composants du bot
        """
        pass

    @abstractmethod
    async def keep_bot_alive(self, components: Dict[str, Any]) -> None:
        """
        Maintient le bot en vie avec une boucle d'attente.

        Args:
            components: Dictionnaire des composants du bot
        """
        pass

    @abstractmethod
    def get_uptime(self) -> float:
        """
        Retourne le temps de fonctionnement en secondes.

        Returns:
            float: Temps de fonctionnement en secondes
        """
        pass

    @abstractmethod
    def is_running(self) -> bool:
        """
        Vérifie si le bot est en cours d'exécution.

        Returns:
            bool: True si le bot est en cours d'exécution, False sinon
        """
        pass

    @abstractmethod
    def get_metrics_monitor(self) -> Any:
        """
        Retourne l'instance du moniteur de métriques active.

        Returns:
            Any: Instance du moniteur de métriques
        """
        pass

    @abstractmethod
    def set_on_funding_update_callback(self, callback: Callable) -> None:
        """
        Définit le callback pour la mise à jour des funding.

        Args:
            callback: Fonction à appeler pour la mise à jour périodique des funding
        """
        pass

