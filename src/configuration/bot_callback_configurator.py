#!/usr/bin/env python3
"""
Configurateur de callbacks pour le bot Bybit.

Ce module centralise la configuration de tous les callbacks entre composants,
améliorant la maintenabilité et la traçabilité des relations entre composants.

Responsabilité unique : Câbler les callbacks entre composants déjà créés
"""

from typing import Optional
from logging_setup import setup_logging
from models.bot_components_bundle import BotComponentsBundle


class BotCallbackConfigurator:
    """
    Configurateur de callbacks pour le bot Bybit.
    
    Cette classe centralise la configuration de tous les callbacks entre
    composants, éliminant la dispersion de la logique de configuration.
    
    Elle configure:
    - Les callbacks entre managers (monitoring → opportunity, etc.)
    - Les callbacks de position (opened/closed)
    - Les callbacks WebSocket (ticker, orderbook)
    - Toute autre relation de dépendance via callbacks
    
    Exemple d'utilisation:
        configurator = BotCallbackConfigurator(logger=logger)
        configurator.configure_all_callbacks(bundle)
    """
    
    def __init__(self, logger=None):
        """
        Initialise le configurateur de callbacks.
        
        Args:
            logger: Logger pour les messages (optionnel)
        """
        self.logger = logger or setup_logging()
    
    def configure_all_callbacks(self, bundle: BotComponentsBundle):
        """
        Configure tous les callbacks entre composants.
        
        Cette méthode orchestre la configuration complète des callbacks
        dans le bon ordre, respectant les dépendances entre composants.
        
        Ordre de configuration:
        1. Callbacks de position (opened/closed)
        2. Callbacks WebSocket (ticker, orderbook)
        3. Callbacks de monitoring (opportunities, candidates)
        4. Callbacks de lifecycle (health, shutdown)
        
        Args:
            bundle: Bundle contenant tous les composants à configurer
        """
        self.logger.debug("🔌 Configuration des callbacks entre composants...")
        
        # 1. Configurer les callbacks de position
        self._configure_position_callbacks(bundle)
        
        # 2. Configurer les callbacks WebSocket
        self._configure_websocket_callbacks(bundle)
        
        # 3. Configurer les callbacks de monitoring
        self._configure_monitoring_callbacks(bundle)
        
        # 4. Configurer les callbacks de lifecycle
        self._configure_lifecycle_callbacks(bundle)
        
        self.logger.debug("✅ Tous les callbacks configurés avec succès")
    
    def _configure_position_callbacks(self, bundle: BotComponentsBundle):
        """Configure les callbacks de position (opened/closed)."""
        # Les callbacks de position seront configurés dynamiquement
        # dans start() après la création de SchedulerManager, PositionMonitor, etc.
        # On prépare juste les références ici
        pass
    
    def _configure_websocket_callbacks(self, bundle: BotComponentsBundle):
        """Configure les callbacks WebSocket (ticker, orderbook)."""
        # Les callbacks WebSocket sont déjà configurés par le CallbackManager
        # dans setup_manager_callbacks(). On n'a rien à faire ici.
        pass
    
    def _configure_monitoring_callbacks(self, bundle: BotComponentsBundle):
        """Configure les callbacks de monitoring (opportunities, candidates)."""
        # Les callbacks de monitoring sont déjà configurés par le CallbackManager
        # dans setup_manager_callbacks(). On n'a rien à faire ici.
        pass
    
    def _configure_lifecycle_callbacks(self, bundle: BotComponentsBundle):
        """Configure les callbacks de lifecycle (health, shutdown, etc.)."""
        # Le lifecycle_manager a déjà son callback de funding update configuré
        # dans _configure_component_relations() de la factory. On n'a rien à faire ici.
        pass
    
    def configure_scheduler_callbacks(self, bundle: BotComponentsBundle):
        """
        Configure les callbacks du SchedulerManager.
        
        Cette méthode est appelée dynamiquement après la création du scheduler
        dans la méthode start() de BotOrchestrator.
        
        Args:
            bundle: Bundle contenant tous les composants
        """
        if bundle.scheduler and bundle.position_event_handler:
            bundle.scheduler.on_position_opened_callback = bundle.position_event_handler.on_position_opened
    
    def configure_position_monitor_callbacks(self, bundle: BotComponentsBundle):
        """
        Configure les callbacks du PositionMonitor.
        
        Cette méthode est appelée dynamiquement après la création du position_monitor
        dans la méthode start() de BotOrchestrator.
        
        Args:
            bundle: Bundle contenant tous les composants
        """
        if bundle.position_monitor and bundle.position_event_handler:
            bundle.position_monitor.on_position_opened = bundle.position_event_handler.on_position_opened
            bundle.position_monitor.on_position_closed = bundle.position_event_handler.on_position_closed
    
    def configure_funding_close_callbacks(self, bundle: BotComponentsBundle):
        """
        Configure les callbacks du FundingCloseManager.
        
        Cette méthode est appelée dynamiquement après la création du funding_close_manager
        dans la méthode start() de BotOrchestrator.
        
        Args:
            bundle: Bundle contenant tous les composants
        """
        if bundle.funding_close_manager and bundle.position_event_handler:
            bundle.funding_close_manager.on_position_closed = bundle.position_event_handler.on_position_closed
            # IMPORTANT: Configurer le PositionEventHandler avec le FundingCloseManager
            bundle.position_event_handler.set_funding_close_manager(bundle.funding_close_manager)
