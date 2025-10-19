#!/usr/bin/env python3
"""
Interface pour le gestionnaire de callbacks.

Cette interface définit le contrat pour les gestionnaires de callbacks,
permettant de découpler les dépendances circulaires.
"""

from abc import ABC, abstractmethod
from typing import List, Callable, Any, Optional


class CallbackManagerInterface(ABC):
    """
    Interface pour les gestionnaires de callbacks.
    
    Cette interface permet de découpler les dépendances circulaires
    entre les différents managers du bot.
    """

    @abstractmethod
    def setup_manager_callbacks(
        self,
        display_manager: Any,
        monitoring_manager: Any,
        volatility_tracker: Any,
        ws_manager: Any,
        data_manager: Any,
        watchlist_manager: Optional[Any] = None,
        opportunity_manager: Optional[Any] = None,
    ) -> None:
        """
        Configure tous les callbacks entre les différents managers.
        
        Args:
            display_manager: Gestionnaire d'affichage
            monitoring_manager: Gestionnaire de surveillance
            volatility_tracker: Tracker de volatilité
            ws_manager: Gestionnaire WebSocket
            data_manager: Gestionnaire de données
            watchlist_manager: Gestionnaire de watchlist (optionnel)
            opportunity_manager: Gestionnaire d'opportunités (optionnel)
        """
        pass

    @abstractmethod
    def setup_display_callbacks(
        self,
        display_manager: Any,
        data_manager: Any,
    ) -> None:
        """
        Configure les callbacks pour l'affichage.
        
        Args:
            display_manager: Gestionnaire d'affichage
            data_manager: Gestionnaire de données
        """
        pass

    @abstractmethod
    def setup_monitoring_callbacks(
        self,
        monitoring_manager: Any,
        opportunity_manager: Any,
    ) -> None:
        """
        Configure les callbacks pour la surveillance.
        
        Args:
            monitoring_manager: Gestionnaire de surveillance
            opportunity_manager: Gestionnaire d'opportunités
        """
        pass

    @abstractmethod
    def setup_websocket_callbacks(
        self,
        ws_manager: Any,
        data_manager: Any,
    ) -> None:
        """
        Configure les callbacks pour les WebSockets.
        
        Args:
            ws_manager: Gestionnaire WebSocket
            data_manager: Gestionnaire de données
        """
        pass
