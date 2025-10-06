#!/usr/bin/env python3
"""
Initialiseur du bot Bybit - Version refactorisée.

Cette classe gère uniquement :
- L'initialisation des managers principaux
- La configuration des gestionnaires spécialisés
- La configuration des callbacks entre managers
"""

from typing import Optional
from logging_setup import setup_logging
from unified_data_manager import UnifiedDataManager
from display_manager import DisplayManager
from unified_monitoring_manager import UnifiedMonitoringManager
from ws_manager import WebSocketManager
from volatility_tracker import VolatilityTracker
from watchlist_manager import WatchlistManager
from callback_manager import CallbackManager
from opportunity_manager import OpportunityManager


class BotInitializer:
    """
    Initialiseur du bot Bybit.
    
    Responsabilités :
    - Initialisation des managers principaux
    - Configuration des gestionnaires spécialisés
    - Configuration des callbacks entre managers
    """
    
    def __init__(self, testnet: bool, logger=None):
        """
        Initialise l'initialiseur du bot.
        
        Args:
            testnet: Utiliser le testnet (True) ou le marché réel (False)
            logger: Logger pour les messages (optionnel)
        """
        self.testnet = testnet
        self.logger = logger or setup_logging()
        
        # Managers principaux
        self.data_manager: Optional[UnifiedDataManager] = None
        self.display_manager: Optional[DisplayManager] = None
        self.monitoring_manager: Optional[UnifiedMonitoringManager] = None
        self.ws_manager: Optional[WebSocketManager] = None
        self.volatility_tracker: Optional[VolatilityTracker] = None
        self.watchlist_manager: Optional[WatchlistManager] = None
        
        # Gestionnaires spécialisés
        self.callback_manager: Optional[CallbackManager] = None
        self.opportunity_manager: Optional[OpportunityManager] = None
    
    def initialize_managers(self):
        """
        Initialise les managers principaux.
        
        Cette méthode crée et configure tous les managers principaux
        nécessaires au fonctionnement du bot.
        """
        # Initialiser le gestionnaire de données
        self.data_manager = UnifiedDataManager(testnet=self.testnet, logger=self.logger)
        
        # Initialiser le gestionnaire d'affichage
        self.display_manager = DisplayManager(self.data_manager, logger=self.logger)
        
        # Initialiser le gestionnaire de surveillance unifié
        self.monitoring_manager = UnifiedMonitoringManager(
            self.data_manager, 
            testnet=self.testnet, 
            logger=self.logger
        )
        
        # Gestionnaire WebSocket dédié
        self.ws_manager = WebSocketManager(testnet=self.testnet, logger=self.logger)
        
        # Gestionnaire de volatilité dédié
        self.volatility_tracker = VolatilityTracker(
            testnet=self.testnet, 
            logger=self.logger
        )
        
        # Gestionnaire de watchlist dédié
        self.watchlist_manager = WatchlistManager(
            testnet=self.testnet, 
            logger=self.logger
        )
    
    def initialize_specialized_managers(self):
        """
        Initialise les gestionnaires spécialisés.
        
        Cette méthode crée les gestionnaires spécialisés pour
        les callbacks et les opportunités.
        """
        # Gestionnaire de callbacks
        self.callback_manager = CallbackManager(logger=self.logger)
        
        # Gestionnaire d'opportunités
        self.opportunity_manager = OpportunityManager(
            self.data_manager, 
            logger=self.logger
        )
    
    def setup_manager_callbacks(self):
        """
        Configure les callbacks entre les différents managers.
        
        Cette méthode délègue entièrement à CallbackManager pour centraliser
        toute la logique de configuration des callbacks.
        """
        if not all([
            self.callback_manager, self.display_manager, 
            self.monitoring_manager, self.volatility_tracker,
            self.ws_manager, self.data_manager
        ]):
            raise RuntimeError("Tous les managers doivent être initialisés avant la configuration des callbacks")
        
        # Délégation complète à CallbackManager pour centraliser la logique
        self.callback_manager.setup_all_callbacks(
            self.display_manager,
            self.monitoring_manager,
            self.volatility_tracker,
            self.ws_manager,
            self.data_manager,
            self.watchlist_manager,
            self.opportunity_manager
        )
    
    def get_managers(self):
        """
        Retourne tous les managers initialisés.
        
        Returns:
            dict: Dictionnaire contenant tous les managers
        """
        return {
            'data_manager': self.data_manager,
            'display_manager': self.display_manager,
            'monitoring_manager': self.monitoring_manager,
            'ws_manager': self.ws_manager,
            'volatility_tracker': self.volatility_tracker,
            'watchlist_manager': self.watchlist_manager,
            'callback_manager': self.callback_manager,
            'opportunity_manager': self.opportunity_manager
        }
