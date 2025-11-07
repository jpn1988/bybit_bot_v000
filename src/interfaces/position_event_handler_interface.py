#!/usr/bin/env python3
"""
Interface pour le gestionnaire des événements de position.

Cette interface définit le contrat pour les gestionnaires d'événements de position,
permettant de découpler les dépendances circulaires.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class PositionEventHandlerInterface(ABC):
    """
    Interface pour les gestionnaires d'événements de position.

    Cette interface permet de découpler les dépendances circulaires
    entre les différents managers du bot.
    """

    @abstractmethod
    def on_position_opened(self, symbol: str, position_data: Dict[str, Any]) -> Any:
        """
        Callback appelé lors de l'ouverture d'une position.

        Args:
            symbol: Symbole de la position ouverte (ex: "BTCUSDT")
            position_data: Données de la position (taille, prix, etc.)

        Returns:
            Any: Résultat de l'opération (peut être awaitable)
        """
        pass

    @abstractmethod
    def on_position_closed(self, symbol: str, position_data: Dict[str, Any]) -> None:
        """
        Callback appelé lors de la fermeture d'une position.

        Args:
            symbol: Symbole de la position fermée (ex: "BTCUSDT")
            position_data: Données de la position (P&L, etc.)
        """
        pass

    @abstractmethod
    def set_monitoring_manager(self, monitoring_manager: Any) -> None:
        """
        Définit le gestionnaire de monitoring.

        Args:
            monitoring_manager: Gestionnaire de monitoring
        """
        pass

    @abstractmethod
    def set_ws_manager(self, ws_manager: Any) -> None:
        """
        Définit le gestionnaire WebSocket.

        Args:
            ws_manager: Gestionnaire WebSocket
        """
        pass

    @abstractmethod
    def set_display_manager(self, display_manager: Any) -> None:
        """
        Définit le gestionnaire d'affichage.

        Args:
            display_manager: Gestionnaire d'affichage
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
    def set_funding_close_manager(self, funding_close_manager: Any) -> None:
        """
        Définit le gestionnaire de fermeture de funding.

        Args:
            funding_close_manager: Gestionnaire de fermeture de funding
        """
        pass

    @abstractmethod
    def set_spot_hedge_manager(self, spot_hedge_manager: Any) -> None:
        """
        Définit le gestionnaire de hedging spot.

        Args:
            spot_hedge_manager: Gestionnaire de hedging spot
        """
        pass

    @abstractmethod
    def remove_position_from_scheduler(self, symbol: str, scheduler: Any) -> None:
        """
        Retire une position du scheduler.

        Args:
            symbol: Symbole de la position
            scheduler: Instance du scheduler
        """
        pass

