#!/usr/bin/env python3
"""
Structure de données pour transporter tous les composants du bot.

Ce module définit BotComponentsBundle, une dataclass immutable qui regroupe
tous les composants du bot pour permettre leur injection en bloc dans BotOrchestrator.
"""

from dataclasses import dataclass
from typing import Optional, Any


@dataclass
class BotComponentsBundle:
    """
    Bundle contenant tous les composants du bot.
    
    Ce bundle permet de transporter tous les composants créés par la factory
    vers le BotOrchestrator en une seule injection, évitant ainsi la configuration
    impérative dispersée.
    
    Note: Les composants scheduler, position_monitor et funding_close_manager
    sont créés dynamiquement dans start() et peuvent être modifiés après création.
    
    Attributs:
        # Managers principaux
        data_manager: Gestionnaire de données unifié
        display_manager: Gestionnaire d'affichage
        monitoring_manager: Gestionnaire de surveillance
        ws_manager: Gestionnaire WebSocket
        watchlist_manager: Gestionnaire de watchlist
        callback_manager: Gestionnaire de callbacks
        opportunity_manager: Gestionnaire d'opportunités
        volatility_tracker: Tracker de volatilité
        
        # Composants helper
        initializer: Initialiseur des managers
        configurator: Configurateur du bot
        starter: Démarreur des composants
        health_monitor: Moniteur de santé
        shutdown_manager: Gestionnaire d'arrêt
        thread_manager: Gestionnaire de threads
        
        # Composants lifecycle
        lifecycle_manager: Gestionnaire du cycle de vie
        position_event_handler: Gestionnaire des événements de position
        fallback_data_manager: Gestionnaire de fallback des données
        
        # Client
        bybit_client: Client Bybit authentifié (optionnel)
        
        # Composants spécialisés (initialisés dans start())
        scheduler: SchedulerManager (optionnel, créé dans start())
        position_monitor: PositionMonitor (optionnel, créé dans start())
        funding_close_manager: FundingCloseManager (optionnel, créé dans start())
        
    Exemple:
        # Créer tous les composants
        bundle = BotComponentsBundle(
            data_manager=data_mgr,
            display_manager=display_mgr,
            # ... tous les autres
        )
        
        # Injecter dans BotOrchestrator
        orchestrator = BotOrchestrator(components_bundle=bundle, logger=logger)
    """
    
    # Managers principaux
    data_manager: Any
    display_manager: Any
    monitoring_manager: Any
    ws_manager: Any
    watchlist_manager: Any
    callback_manager: Any
    opportunity_manager: Any
    volatility_tracker: Any
    
    # Composants helper
    initializer: Any
    configurator: Any
    data_loader: Any
    starter: Any
    health_monitor: Any
    shutdown_manager: Any
    thread_manager: Any
    
    # Composants lifecycle
    lifecycle_manager: Any
    position_event_handler: Any
    fallback_data_manager: Any
    
    # Client
    bybit_client: Optional[Any] = None
    
    # Composants spécialisés (initialisés plus tard dans start())
    scheduler: Optional[Any] = None
    position_monitor: Optional[Any] = None
    funding_close_manager: Optional[Any] = None
    
    def get_all_managers(self) -> dict:
        """
        Retourne un dictionnaire avec tous les managers principaux.
        
        Returns:
            Dict contenant tous les managers indexés par leur nom
        """
        return {
            "data_manager": self.data_manager,
            "display_manager": self.display_manager,
            "monitoring_manager": self.monitoring_manager,
            "ws_manager": self.ws_manager,
            "watchlist_manager": self.watchlist_manager,
            "callback_manager": self.callback_manager,
            "opportunity_manager": self.opportunity_manager,
            "volatility_tracker": self.volatility_tracker,
        }
    
    def get_helper_components(self) -> dict:
        """
        Retourne un dictionnaire avec tous les composants helper.
        
        Returns:
            Dict contenant tous les helpers indexés par leur nom
        """
        return {
            "initializer": self.initializer,
            "configurator": self.configurator,
            "data_loader": self.data_loader,
            "starter": self.starter,
            "health_monitor": self.health_monitor,
            "shutdown_manager": self.shutdown_manager,
            "thread_manager": self.thread_manager,
        }
    
    def get_lifecycle_components(self) -> dict:
        """
        Retourne un dictionnaire avec tous les composants de cycle de vie.
        
        Returns:
            Dict contenant tous les composants de lifecycle indexés par leur nom
        """
        return {
            "lifecycle_manager": self.lifecycle_manager,
            "position_event_handler": self.position_event_handler,
            "fallback_data_manager": self.fallback_data_manager,
        }
