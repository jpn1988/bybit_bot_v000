#!/usr/bin/env python3
"""
Gestionnaire de callbacks pour le bot Bybit.

Cette classe gère uniquement :
- La configuration des callbacks entre managers
- L'orchestration des callbacks
- La gestion des interactions entre composants
"""

from typing import List, Callable, Any, Optional, TYPE_CHECKING
from logging_setup import setup_logging
from interfaces.callback_manager_interface import CallbackManagerInterface

# Éviter les imports circulaires avec TYPE_CHECKING
if TYPE_CHECKING:
    from typing_imports import (
        DataManager,
        DisplayManager,
        MonitoringManager,
        VolatilityTracker,
        WebSocketManager,
        WatchlistManager,
        OpportunityManager,
    )


class CallbackManager(CallbackManagerInterface):
    """
    Gestionnaire de callbacks pour le bot Bybit.

    Responsabilités :
    - Configuration des callbacks entre managers
    - Orchestration des interactions
    - Gestion des callbacks de données
    """

    def __init__(self, logger=None):
        """
        Initialise le gestionnaire de callbacks.

        Args:
            logger: Logger pour les messages (optionnel)
        """
        self.logger = logger or setup_logging()

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
        Configure TOUS les callbacks entre les différents managers.

        Args:
            display_manager: Gestionnaire d'affichage
            monitoring_manager: Gestionnaire de surveillance
            volatility_tracker: Tracker de volatilité
            ws_manager: Gestionnaire WebSocket
            data_manager: Gestionnaire de données
            watchlist_manager: Gestionnaire de watchlist (optionnel)
            opportunity_manager: Gestionnaire d'opportunités (optionnel)
        """
        # Callback pour la volatilité dans le display manager
        display_manager.set_volatility_callback(
            volatility_tracker.get_cached_volatility
        )

        # Callbacks pour le monitoring manager
        if watchlist_manager:
            monitoring_manager.set_watchlist_manager(watchlist_manager)
        monitoring_manager.set_volatility_tracker(volatility_tracker)
        monitoring_manager.set_ws_manager(ws_manager)

        # Callbacks d'opportunités (si opportunity_manager fourni)
        if opportunity_manager and watchlist_manager:
            monitoring_manager.set_on_new_opportunity_callback(
                lambda linear, inverse: opportunity_manager.on_new_opportunity(
                    linear, inverse, ws_manager, watchlist_manager
                )
            )

            monitoring_manager.set_on_candidate_ticker_callback(
                lambda symbol, ticker_data: opportunity_manager.on_candidate_ticker(
                    symbol, ticker_data, watchlist_manager
                )
            )

    def setup_all_callbacks(
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
        Configure TOUS les callbacks en une seule méthode.

        Cette méthode centralise la configuration de tous les callbacks
        pour éviter la duplication de code dans BotInitializer.

        Args:
            display_manager: Gestionnaire d'affichage
            monitoring_manager: Gestionnaire de surveillance
            volatility_tracker: Tracker de volatilité
            ws_manager: Gestionnaire WebSocket
            data_manager: Gestionnaire de données
            watchlist_manager: Gestionnaire de watchlist (optionnel)
            opportunity_manager: Gestionnaire d'opportunités (optionnel)
        """
        # Configurer les callbacks principaux
        self.setup_manager_callbacks(
            display_manager,
            monitoring_manager,
            volatility_tracker,
            ws_manager,
            data_manager,
            watchlist_manager,
            opportunity_manager,
        )

        # Configurer les callbacks WebSocket
        self.setup_ws_callbacks(ws_manager, data_manager)

        # Configurer les callbacks de volatilité
        self.setup_volatility_callbacks(volatility_tracker, data_manager)

    def setup_ws_callbacks(
        self, ws_manager: "WebSocketManager", data_manager: "DataManager"
    ) -> None:
        """
        Configure les callbacks WebSocket.

        Args:
            ws_manager: Gestionnaire WebSocket
            data_manager: Gestionnaire de données
        """
        # Callback pour les données ticker
        ws_manager.set_ticker_callback(
            self._create_ticker_callback(data_manager)
        )

    def setup_volatility_callbacks(
        self,
        volatility_tracker: "VolatilityTracker",
        data_manager: "DataManager",
    ) -> None:
        """
        Configure les callbacks de volatilité.

        Args:
            volatility_tracker: Tracker de volatilité
            data_manager: Gestionnaire de données
        """
        # Callback pour obtenir les symboles actifs
        volatility_tracker.set_active_symbols_callback(
            self._create_active_symbols_callback(data_manager)
        )

    def _create_ticker_callback(
        self, data_manager: "DataManager"
    ) -> Callable[[dict], None]:
        """
        Crée le callback pour les données ticker.

        Args:
            data_manager: Gestionnaire de données

        Returns:
            Fonction callback pour les tickers
        """

        def ticker_callback(ticker_data: dict):
            """
            Met à jour les données en temps réel à partir des données ticker WebSocket.
            Callback appelé par WebSocketManager.

            Args:
                ticker_data (dict): Données du ticker reçues via WebSocket
            """
            symbol = ticker_data.get("symbol", "")
            if not symbol:
                return

            # Déléguer au DataStorage
            data_manager.storage.update_realtime_data(symbol, ticker_data)

        return ticker_callback

    def _create_active_symbols_callback(
        self, data_manager: "DataManager"
    ) -> Callable[[], List[str]]:
        """
        Crée le callback pour obtenir les symboles actifs.

        Args:
            data_manager: Gestionnaire de données

        Returns:
            Fonction callback pour les symboles actifs
        """

        def active_symbols_callback() -> List[str]:
            """
            Retourne la liste des symboles actuellement actifs.

            Returns:
                Liste des symboles actifs
            """
            return data_manager.storage.get_all_symbols()

        return active_symbols_callback

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
        # Configuration des callbacks d'affichage si nécessaire
        pass

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
        # Configuration des callbacks de surveillance si nécessaire
        pass

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
        # Cette méthode est déjà implémentée comme setup_ws_callbacks
        self.setup_ws_callbacks(ws_manager, data_manager)
