#!/usr/bin/env python3
"""
Centralisation des imports de types pour éviter les imports circulaires.

Ce module centralise tous les imports de types qui peuvent causer des
imports circulaires, permettant une meilleure organisation et maintenance.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Imports de types pour les composants principaux
    from bot import BotOrchestrator, AsyncBotRunner
    from data_manager import DataManager
    from monitoring_manager import MonitoringManager
    from bot_initializer import BotInitializer
    from bot_configurator import BotConfigurator
    from bot_starter import BotStarter
    from bot_health_monitor import BotHealthMonitor
    from position_monitor import PositionMonitor
    from shutdown_manager import ShutdownManager
    from thread_manager import ThreadManager
    from scheduler_manager import SchedulerManager
    from funding_close_manager import FundingCloseManager
    from bot_lifecycle_manager import BotLifecycleManager
    from position_event_handler import PositionEventHandler
    from fallback_data_manager import FallbackDataManager

    # Imports de types pour les factories
    from factories.bot_factory import BotFactory
    from factories.bot_component_factory import BotComponentFactory

    # Imports de types pour les modèles
    from models.bot_components_bundle import BotComponentsBundle
    from models.funding_data import FundingData
    from models.symbol_data import SymbolData
    from models.ticker_data import TickerData

    # Imports de types pour les interfaces
    from interfaces.bybit_client_interface import BybitClientInterface
    from interfaces.websocket_manager_interface import WebSocketManagerInterface
    from interfaces.callback_manager_interface import CallbackManagerInterface
    from interfaces.monitoring_manager_interface import MonitoringManagerInterface

    # Imports de types pour les composants de données
    from data_fetcher import DataFetcher
    from data_storage import DataStorage
    from data_validator import DataValidator
    from volatility_tracker import VolatilityTracker
    from watchlist_manager import WatchlistManager
    from callback_manager import CallbackManager
    from opportunity_manager import OpportunityManager
    from candidate_monitor import CandidateMonitor
    from display_manager import DisplayManager
    from ws.manager import WebSocketManager

    # Imports de types pour les clients et services externes
    from bybit_client import BybitClient
    from http_client_manager import HTTPClientManager
    from metrics_monitor import MetricsMonitor
