#!/usr/bin/env python3
"""
Module de configuration unifié pour le bot Bybit - Version refactorisée.

Ce module maintient la compatibilité avec l'ancien code en réexportant
les composants du package config/.

NOUVEAU : Le code a été refactorisé en modules séparés dans config/ :
- config/constants.py : Constantes et limites
- config/env_validator.py : Validation des variables d'environnement
- config/settings_loader.py : Chargement des settings depuis .env
- config/config_validator.py : Validation de configuration
- config/manager.py : Gestionnaire principal

HIÉRARCHIE DE PRIORITÉ :
1. Variables d'environnement (.env) - PRIORITÉ MAXIMALE
2. Fichier YAML (parameters.yaml) - PRIORITÉ MOYENNE
3. Valeurs par défaut - PRIORITÉ MINIMALE
"""

# Réexporter tous les composants pour la compatibilité
from config import (
    ConfigManager,
    get_settings,
    MAX_LIMIT_RECOMMENDED,
    MAX_SPREAD_PERCENTAGE,
    MAX_FUNDING_TIME_MINUTES,
    MIN_VOLATILITY_TTL_SECONDS,
    MAX_VOLATILITY_TTL_SECONDS,
    MIN_DISPLAY_INTERVAL_SECONDS,
    MAX_DISPLAY_INTERVAL_SECONDS,
    MAX_WORKERS_THREADPOOL,
)

# Alias pour la compatibilité avec l'ancien code
UnifiedConfigManager = ConfigManager

__all__ = [
    "ConfigManager",
    "UnifiedConfigManager",
    "get_settings",
    "MAX_LIMIT_RECOMMENDED",
    "MAX_SPREAD_PERCENTAGE",
    "MAX_FUNDING_TIME_MINUTES",
    "MIN_VOLATILITY_TTL_SECONDS",
    "MAX_VOLATILITY_TTL_SECONDS",
    "MIN_DISPLAY_INTERVAL_SECONDS",
    "MAX_DISPLAY_INTERVAL_SECONDS",
    "MAX_WORKERS_THREADPOOL",
]

