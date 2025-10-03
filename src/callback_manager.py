#!/usr/bin/env python3
"""
Gestionnaire de callbacks pour le bot Bybit.

Cette classe gère uniquement :
- La configuration des callbacks entre managers
- L'orchestration des callbacks
- La gestion des interactions entre composants
"""

from typing import List, Dict, Optional, Callable
from logging_setup import setup_logging
from unified_data_manager import UnifiedDataManager
from display_manager import DisplayManager
from unified_monitoring_manager import UnifiedMonitoringManager
from volatility_tracker import VolatilityTracker
from ws_manager import WebSocketManager


class CallbackManager:
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
        display_manager: DisplayManager,
        monitoring_manager: UnifiedMonitoringManager,
        volatility_tracker: VolatilityTracker,
        ws_manager: WebSocketManager,
        data_manager: UnifiedDataManager
    ):
        """
        Configure les callbacks entre les différents managers.
        
        Args:
            display_manager: Gestionnaire d'affichage
            monitoring_manager: Gestionnaire de surveillance
            volatility_tracker: Tracker de volatilité
            ws_manager: Gestionnaire WebSocket
            data_manager: Gestionnaire de données
        """
        # Callback pour la volatilité dans le display manager
        display_manager.set_volatility_callback(volatility_tracker.get_cached_volatility)
        
        # Callbacks pour le monitoring manager
        monitoring_manager.set_watchlist_manager(None)  # Sera défini plus tard
        monitoring_manager.set_volatility_tracker(volatility_tracker)
    
    def setup_ws_callbacks(
        self,
        ws_manager: WebSocketManager,
        data_manager: UnifiedDataManager
    ):
        """
        Configure les callbacks WebSocket.
        
        Args:
            ws_manager: Gestionnaire WebSocket
            data_manager: Gestionnaire de données
        """
        # Callback pour les données ticker
        ws_manager.set_ticker_callback(self._create_ticker_callback(data_manager))
    
    def setup_volatility_callbacks(
        self,
        volatility_tracker: VolatilityTracker,
        data_manager: UnifiedDataManager
    ):
        """
        Configure les callbacks de volatilité.
        
        Args:
            volatility_tracker: Tracker de volatilité
            data_manager: Gestionnaire de données
        """
        # Callback pour obtenir les symboles actifs
        volatility_tracker.set_active_symbols_callback(self._create_active_symbols_callback(data_manager))
    
    def _create_ticker_callback(self, data_manager: UnifiedDataManager) -> Callable:
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
            
            # Déléguer au DataManager
            data_manager.update_realtime_data(symbol, ticker_data)
        
        return ticker_callback
    
    def _create_active_symbols_callback(self, data_manager: UnifiedDataManager) -> Callable:
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
            return data_manager.get_all_symbols()
        
        return active_symbols_callback
