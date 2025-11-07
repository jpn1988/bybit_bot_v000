#!/usr/bin/env python3
"""
Package de configuration pour le bot Bybit.

Ce package organise la configuration en modules séparés :
- constants.py : Constantes et limites du système
- env_validator.py : Validation des variables d'environnement
- settings_loader.py : Chargement des settings depuis .env
- config_validator.py : Validation de la configuration
- manager.py : Gestionnaire de configuration principal
- timeouts.py : Configuration centralisée des timeouts et intervalles
"""

from .constants import (
    # Limites de trading
    MAX_LIMIT_RECOMMENDED,
    MAX_SPREAD_PERCENTAGE,
    MAX_FUNDING_TIME_MINUTES,
    # Limites de volatilité
    MIN_VOLATILITY_TTL_SECONDS,
    MAX_VOLATILITY_TTL_SECONDS,
    # Limites d'affichage
    MIN_DISPLAY_INTERVAL_SECONDS,
    MAX_DISPLAY_INTERVAL_SECONDS,
    # Limites de threading
    MAX_WORKERS_THREADPOOL,
    # Intervalles et timeouts par défaut
    DEFAULT_FUNDING_UPDATE_INTERVAL,
    DEFAULT_METRICS_INTERVAL,
    DEFAULT_HTTP_TIMEOUT,
    DEFAULT_WEBSOCKET_TIMEOUT,
    DEFAULT_THREAD_SHUTDOWN_TIMEOUT,
    DEFAULT_MAX_RETRIES,
    # Limites de données
    MAX_SYMBOLS_PER_CONNECTION,
    DEFAULT_PAGINATION_LIMIT,
    MAX_FUNDING_RATE_DEVIATION,
    # Formats et affichage
    DEFAULT_DECIMAL_PLACES,
    DEFAULT_PERCENTAGE_PRECISION,
    # Catégories de contrats
    CATEGORY_LINEAR,
    CATEGORY_INVERSE,
    CATEGORY_BOTH,
    # Paramètres de configuration par défaut
    DEFAULT_FUNDING_MIN,
    DEFAULT_FUNDING_MAX,
    DEFAULT_VOLUME_MIN_MILLIONS,
    DEFAULT_SPREAD_MAX,
    DEFAULT_LIMIT,
    DEFAULT_VOLATILITY_TTL_SEC,
    DEFAULT_FUNDING_TIME_MIN_MINUTES,
    DEFAULT_FUNDING_TIME_MAX_MINUTES,
    DEFAULT_DISPLAY_INTERVAL_SECONDS,
    DEFAULT_FUNDING_THRESHOLD_MINUTES,
    # Poids par défaut (système de scoring)
    DEFAULT_WEIGHT_FUNDING,
    DEFAULT_WEIGHT_VOLUME,
    DEFAULT_WEIGHT_SPREAD,
    DEFAULT_WEIGHT_VOLATILITY,
    DEFAULT_TOP_SYMBOLS,
    # Trading automatique
    DEFAULT_AUTO_TRADING_ENABLED,
    DEFAULT_ORDER_SIZE_USDT,
    DEFAULT_ORDER_OFFSET_PERCENT,
    DEFAULT_MAX_POSITIONS,
    DEFAULT_DRY_RUN,
)
from .settings_loader import get_settings
from .manager import ConfigManager
from .timeouts import TimeoutConfig, ScanIntervalConfig
from .urls import URLConfig

__all__ = [
    "ConfigManager",
    "get_settings",
    "TimeoutConfig",
    "ScanIntervalConfig",
    "URLConfig",
    # Limites de trading
    "MAX_LIMIT_RECOMMENDED",
    "MAX_SPREAD_PERCENTAGE",
    "MAX_FUNDING_TIME_MINUTES",
    # Limites de volatilité
    "MIN_VOLATILITY_TTL_SECONDS",
    "MAX_VOLATILITY_TTL_SECONDS",
    # Limites d'affichage
    "MIN_DISPLAY_INTERVAL_SECONDS",
    "MAX_DISPLAY_INTERVAL_SECONDS",
    # Limites de threading
    "MAX_WORKERS_THREADPOOL",
    # Intervalles et timeouts par défaut
    "DEFAULT_FUNDING_UPDATE_INTERVAL",
    "DEFAULT_METRICS_INTERVAL",
    "DEFAULT_HTTP_TIMEOUT",
    "DEFAULT_WEBSOCKET_TIMEOUT",
    "DEFAULT_THREAD_SHUTDOWN_TIMEOUT",
    "DEFAULT_MAX_RETRIES",
    # Limites de données
    "MAX_SYMBOLS_PER_CONNECTION",
    "DEFAULT_PAGINATION_LIMIT",
    "MAX_FUNDING_RATE_DEVIATION",
    # Formats et affichage
    "DEFAULT_DECIMAL_PLACES",
    "DEFAULT_PERCENTAGE_PRECISION",
    # Catégories de contrats
    "CATEGORY_LINEAR",
    "CATEGORY_INVERSE",
    "CATEGORY_BOTH",
    # Paramètres de configuration par défaut
    "DEFAULT_FUNDING_MIN",
    "DEFAULT_FUNDING_MAX",
    "DEFAULT_VOLUME_MIN_MILLIONS",
    "DEFAULT_SPREAD_MAX",
    "DEFAULT_LIMIT",
    "DEFAULT_VOLATILITY_TTL_SEC",
    "DEFAULT_FUNDING_TIME_MIN_MINUTES",
    "DEFAULT_FUNDING_TIME_MAX_MINUTES",
    "DEFAULT_DISPLAY_INTERVAL_SECONDS",
    "DEFAULT_FUNDING_THRESHOLD_MINUTES",
    # Poids par défaut (système de scoring)
    "DEFAULT_WEIGHT_FUNDING",
    "DEFAULT_WEIGHT_VOLUME",
    "DEFAULT_WEIGHT_SPREAD",
    "DEFAULT_WEIGHT_VOLATILITY",
    "DEFAULT_TOP_SYMBOLS",
    # Trading automatique
    "DEFAULT_AUTO_TRADING_ENABLED",
    "DEFAULT_ORDER_SIZE_USDT",
    "DEFAULT_ORDER_OFFSET_PERCENT",
    "DEFAULT_MAX_POSITIONS",
    "DEFAULT_DRY_RUN",
]

