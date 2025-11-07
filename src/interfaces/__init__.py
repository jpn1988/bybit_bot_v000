#!/usr/bin/env python3
"""
Package des interfaces pour le bot Bybit.

Ce package contient les interfaces (contrats) pour les composants principaux
du bot, permettant une meilleure testabilité et une architecture plus flexible.
"""

from .bybit_client_interface import BybitClientInterface
from .websocket_manager_interface import WebSocketManagerInterface
from .callback_manager_interface import CallbackManagerInterface
from .monitoring_manager_interface import MonitoringManagerInterface
from .lifecycle_manager_interface import LifecycleManagerInterface
from .position_event_handler_interface import PositionEventHandlerInterface
from .fallback_data_manager_interface import FallbackDataManagerInterface
from .spot_hedge_manager_interface import SpotHedgeManagerInterface
from .data_storage_interface import DataStorageInterface
from .data_manager_interface import DataManagerInterface
from .watchlist_manager_interface import WatchlistManagerInterface
from .volatility_tracker_interface import VolatilityTrackerInterface

__all__ = [
    "BybitClientInterface",
    "WebSocketManagerInterface",
    "CallbackManagerInterface",
    "MonitoringManagerInterface",
    "LifecycleManagerInterface",
    "PositionEventHandlerInterface",
    "FallbackDataManagerInterface",
    "SpotHedgeManagerInterface",
    "DataStorageInterface",
    "DataManagerInterface",
    "WatchlistManagerInterface",
    "VolatilityTrackerInterface",
]
