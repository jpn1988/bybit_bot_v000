#!/usr/bin/env python3
"""
Chargeur de settings depuis les variables d'environnement.

Ce module récupère et convertit les variables d'environnement en
paramètres de configuration typés.
"""

import os
from typing import Dict, Optional
from dotenv import load_dotenv
from .env_validator import validate_environment_variables

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()


def safe_float(value: Optional[str]) -> Optional[float]:
    """
    Convertit une valeur en float de manière sécurisée.
    
    Args:
        value: Valeur à convertir
        
    Returns:
        float ou None si la conversion échoue
    """
    try:
        return float(value) if value else None
    except (ValueError, TypeError):
        return None


def safe_int(value: Optional[str]) -> Optional[int]:
    """
    Convertit une valeur en int de manière sécurisée.
    
    Args:
        value: Valeur à convertir
        
    Returns:
        int ou None si la conversion échoue
    """
    try:
        return int(value) if value else None
    except (ValueError, TypeError):
        return None


def get_settings() -> Dict:
    """
    Retourne un dictionnaire avec les paramètres de configuration
    depuis les variables d'environnement.
    
    Cette fonction :
    1. Valide les variables d'environnement (détecte les fautes de frappe)
    2. Récupère et convertit les valeurs
    3. Retourne un dictionnaire typé
    
    Returns:
        dict: Dictionnaire contenant les paramètres de configuration
    """
    # Valider les variables d'environnement
    validate_environment_variables()
    
    # Récupérer les clés API et convertir les chaînes vides en None
    api_key = os.getenv("BYBIT_API_KEY") or None
    api_secret = os.getenv("BYBIT_API_SECRET") or None
    
    # Récupérer les variables d'environnement pour les filtres
    spread_max = os.getenv("SPREAD_MAX")
    volume_min_millions = os.getenv("VOLUME_MIN_MILLIONS")
    volatility_min = os.getenv("VOLATILITY_MIN")
    volatility_max = os.getenv("VOLATILITY_MAX")
    funding_min = os.getenv("FUNDING_MIN")
    funding_max = os.getenv("FUNDING_MAX")
    category = os.getenv("CATEGORY")
    limit = os.getenv("LIMIT")
    volatility_ttl_sec = os.getenv("VOLATILITY_TTL_SEC")
    funding_time_min_minutes = os.getenv("FUNDING_TIME_MIN_MINUTES")
    funding_time_max_minutes = os.getenv("FUNDING_TIME_MAX_MINUTES")
    display_interval_seconds = os.getenv("DISPLAY_INTERVAL_SECONDS")
    
    # Convertir en types appropriés
    return {
        "testnet": os.getenv("TESTNET", "true").lower() == "true",
        "timeout": safe_int(os.getenv("TIMEOUT", "10")) or 10,
        "log_level": os.getenv("LOG_LEVEL", "INFO").upper(),
        "api_key": api_key,
        "api_secret": api_secret,
        "spread_max": safe_float(spread_max),
        "volume_min_millions": safe_float(volume_min_millions),
        "volatility_min": safe_float(volatility_min),
        "volatility_max": safe_float(volatility_max),
        "funding_min": safe_float(funding_min),
        "funding_max": safe_float(funding_max),
        "category": category,
        "limit": safe_int(limit),
        "volatility_ttl_sec": safe_int(volatility_ttl_sec),
        "funding_time_min_minutes": safe_int(funding_time_min_minutes),
        "funding_time_max_minutes": safe_int(funding_time_max_minutes),
        "display_interval_seconds": safe_int(display_interval_seconds),
    }

