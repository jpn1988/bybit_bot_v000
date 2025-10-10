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
    MAX_LIMIT_RECOMMENDED,
    MAX_SPREAD_PERCENTAGE,
    MAX_FUNDING_TIME_MINUTES,
    MIN_VOLATILITY_TTL_SECONDS,
    MAX_VOLATILITY_TTL_SECONDS,
    MIN_DISPLAY_INTERVAL_SECONDS,
    MAX_DISPLAY_INTERVAL_SECONDS,
    MAX_WORKERS_THREADPOOL,
)
from .settings_loader import get_settings
from .manager import ConfigManager
from .timeouts import TimeoutConfig, ScanIntervalConfig

__all__ = [
    "ConfigManager",
    "get_settings",
    "TimeoutConfig",
    "ScanIntervalConfig",
    "MAX_LIMIT_RECOMMENDED",
    "MAX_SPREAD_PERCENTAGE",
    "MAX_FUNDING_TIME_MINUTES",
    "MIN_VOLATILITY_TTL_SECONDS",
    "MAX_VOLATILITY_TTL_SECONDS",
    "MIN_DISPLAY_INTERVAL_SECONDS",
    "MAX_DISPLAY_INTERVAL_SECONDS",
    "MAX_WORKERS_THREADPOOL",
]

