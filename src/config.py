"""Configuration module for bybit_bot_v0."""

import os
from dotenv import load_dotenv

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()


def get_settings():
    """
    Retourne un dictionnaire avec les paramètres de configuration.
    
    Returns:
        dict: Dictionnaire contenant les paramètres de configuration
    """
    # Récupérer les clés API et convertir les chaînes vides en None
    api_key = os.getenv("BYBIT_API_KEY") or None
    api_secret = os.getenv("BYBIT_API_SECRET") or None
    
    # Récupérer les nouvelles variables d'environnement pour les filtres
    spread_max = os.getenv("SPREAD_MAX")
    volume_min_millions = os.getenv("VOLUME_MIN_MILLIONS")
    volatility_min = os.getenv("VOLATILITY_MIN")
    volatility_max = os.getenv("VOLATILITY_MAX")
    # Variables supplémentaires alignées avec le README
    funding_min = os.getenv("FUNDING_MIN")
    funding_max = os.getenv("FUNDING_MAX")
    category = os.getenv("CATEGORY")  # linear | inverse | both
    limit = os.getenv("LIMIT")
    volatility_ttl_sec = os.getenv("VOLATILITY_TTL_SEC")
    # Nouveaux paramètres de filtre temporel funding
    funding_time_min_minutes = os.getenv("FUNDING_TIME_MIN_MINUTES")
    funding_time_max_minutes = os.getenv("FUNDING_TIME_MAX_MINUTES")
    
    # Convertir en float/int si présentes, sinon None
    spread_max = float(spread_max) if spread_max else None
    volume_min_millions = float(volume_min_millions) if volume_min_millions else None
    volatility_min = float(volatility_min) if volatility_min else None
    volatility_max = float(volatility_max) if volatility_max else None
    funding_min = float(funding_min) if funding_min else None
    funding_max = float(funding_max) if funding_max else None
    limit = int(limit) if limit else None
    volatility_ttl_sec = int(volatility_ttl_sec) if volatility_ttl_sec else None
    # Conversions minutes → int
    funding_time_min_minutes = int(funding_time_min_minutes) if funding_time_min_minutes else None
    funding_time_max_minutes = int(funding_time_max_minutes) if funding_time_max_minutes else None
    
    return {
        "testnet": os.getenv("TESTNET", "true").lower() == "true",
        "timeout": int(os.getenv("TIMEOUT", "10")),
        "log_level": os.getenv("LOG_LEVEL", "INFO").upper(),
        "api_key": api_key,
        "api_secret": api_secret,
        "spread_max": spread_max,
        "volume_min_millions": volume_min_millions,
        "volatility_min": volatility_min,
        "volatility_max": volatility_max,
        # Ajouts alignés README
        "funding_min": funding_min,
        "funding_max": funding_max,
        "category": category,
        "limit": limit,
        "volatility_ttl_sec": volatility_ttl_sec,
        # Nouveaux paramètres temporels
        "funding_time_min_minutes": funding_time_min_minutes,
        "funding_time_max_minutes": funding_time_max_minutes,
    }
