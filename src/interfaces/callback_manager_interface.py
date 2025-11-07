#!/usr/bin/env python3
"""
Interface pour le gestionnaire de callbacks.

Cette interface définit le contrat pour les gestionnaires de callbacks,
permettant de découpler les dépendances circulaires.
"""

from abc import ABC, abstractmethod
from typing import List, Callable, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from typing_imports import (
        DisplayManager,
        MonitoringManager,
        VolatilityTracker,
        WebSocketManager,
        DataManager,
        WatchlistManager,
        OpportunityManager,
    )


class CallbackManagerInterface(ABC):
    """
    Interface pour les gestionnaires de callbacks.

    Cette interface permet de découpler les dépendances circulaires
    entre les différents managers du bot.
    """

    @abstractmethod
    def setup_manager_callbacks(
        self,
        display_manager: "DisplayManager",
        monitoring_manager: "MonitoringManager",
        volatility_tracker: "VolatilityTracker",
        ws_manager: "WebSocketManager",
        data_manager: "DataManager",
        watchlist_manager: Optional["WatchlistManager"] = None,
        opportunity_manager: Optional["OpportunityManager"] = None,
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
        display_manager: "DisplayManager",
        data_manager: "DataManager",
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
        monitoring_manager: "MonitoringManager",
        opportunity_manager: "OpportunityManager",
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
        ws_manager: "WebSocketManager",
        data_manager: "DataManager",
    ) -> None:
        """
        Configure les callbacks pour les WebSockets.

        Args:
            ws_manager: Gestionnaire WebSocket
            data_manager: Gestionnaire de données
        """
        pass
