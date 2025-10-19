#!/usr/bin/env python3
"""
Interface pour le gestionnaire de surveillance.

Cette interface définit le contrat pour les gestionnaires de surveillance,
permettant de découpler les dépendances circulaires.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Callable, Any


class MonitoringManagerInterface(ABC):
    """
    Interface pour les gestionnaires de surveillance.
    
    Cette interface permet de découpler les dépendances circulaires
    entre les différents managers du bot.
    """

    @abstractmethod
    def set_watchlist_manager(self, watchlist_manager: Any) -> None:
        """
        Définit le gestionnaire de watchlist.
        
        Args:
            watchlist_manager: Gestionnaire de watchlist
        """
        pass

    @abstractmethod
    def set_volatility_tracker(self, volatility_tracker: Any) -> None:
        """
        Définit le tracker de volatilité.
        
        Args:
            volatility_tracker: Tracker de volatilité
        """
        pass

    @abstractmethod
    def set_opportunity_manager(self, opportunity_manager: Any) -> None:
        """
        Définit le gestionnaire d'opportunités.
        
        Args:
            opportunity_manager: Gestionnaire d'opportunités
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
    async def start_continuous_monitoring(self) -> None:
        """
        Démarre la surveillance continue.
        """
        pass

    @abstractmethod
    async def stop_continuous_monitoring(self) -> None:
        """
        Arrête la surveillance continue.
        """
        pass

    @abstractmethod
    def set_on_new_opportunity_callback(self, callback: Callable) -> None:
        """
        Définit le callback pour les nouvelles opportunités.
        
        Args:
            callback: Fonction à appeler lors de nouvelles opportunités
        """
        pass
