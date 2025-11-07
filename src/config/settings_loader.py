#!/usr/bin/env python3
"""
Chargeur de settings depuis les variables d'environnement.

Ce module récupère et convertit les variables d'environnement en
paramètres de configuration typés.
"""

import os
from typing import Dict, Optional

import yaml
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


def validate_credentials() -> None:
    """
    Valide que les clés API ne sont pas les valeurs par défaut.

    Raises:
        ValueError: Si les credentials ne sont pas correctement configurés
    """
    api_key = os.getenv("BYBIT_API_KEY", "")
    api_secret = os.getenv("BYBIT_API_SECRET", "")

    # Vérifier si les clés sont les valeurs placeholder par défaut
    if api_key == "your_api_key_here" or api_secret == "your_api_secret_here":
        raise ValueError(
            "🔐 ERREUR SÉCURITÉ: Les clés API utilisent les valeurs par défaut.\n"
            "Veuillez configurer vos vraies clés API dans le fichier .env:\n"
            "1. Copiez .env.example vers .env\n"
            "2. Remplacez 'your_api_key_here' et 'your_api_secret_here' par vos vraies clés\n"
            "3. Obtenez vos clés sur: https://testnet.bybit.com/app/user/api-management"
        )

    # Vérifier si les clés sont vides (mais permettre None pour usage public uniquement)
    if not api_key or not api_secret:
        print("⚠️ Avertissement: Clés API non configurées, fonctionnalités privées désactivées")
        print("💡 Pour activer les fonctionnalités privées, configurez BYBIT_API_KEY et BYBIT_API_SECRET dans .env")


def get_settings() -> Dict:
    """
    Retourne un dictionnaire avec les paramètres de configuration
    depuis les variables d'environnement.

    Cette fonction :
    1. Valide les variables d'environnement (détecte les fautes de frappe)
    2. Valide les credentials API pour sécurité
    3. Récupère et convertit les valeurs
    4. Retourne un dictionnaire typé

    Returns:
        dict: Dictionnaire contenant les paramètres de configuration
    """
    # Valider les variables d'environnement
    validate_environment_variables()

    # SEC-001: Valider les credentials pour sécurité
    validate_credentials()

    # Charger la configuration YAML (parameters.yaml) pour récupérer les valeurs par défaut
    yaml_config = {}
    try:
        with open("src/parameters.yaml", "r", encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        yaml_config = {}
    except Exception:
        yaml_config = {}

    bybit_yaml = yaml_config.get("bybit_private") if isinstance(yaml_config, dict) else {}
    if not isinstance(bybit_yaml, dict):
        bybit_yaml = {}

    # Récupérer les clés API et convertir les chaînes vides en None
    api_key = os.getenv("BYBIT_API_KEY") or None
    api_secret = os.getenv("BYBIT_API_SECRET") or None

    # Paramètres spécifiques Bybit avec fallback YAML → valeurs par défaut
    recv_window_ms = safe_int(os.getenv("BYBIT_RECV_WINDOW_MS"))
    if recv_window_ms is None:
        recv_window_ms = safe_int(bybit_yaml.get("recv_window_ms")) or 7000

    time_sync_enabled_env = os.getenv("BYBIT_TIME_SYNC_ENABLED")
    if time_sync_enabled_env is not None:
        time_sync_enabled = time_sync_enabled_env.lower() == "true"
    else:
        time_sync_enabled = bool(bybit_yaml.get("time_sync_enabled", True))

    time_sync_interval_seconds = safe_int(os.getenv("BYBIT_TIME_SYNC_INTERVAL_SECONDS"))
    if time_sync_interval_seconds is None:
        time_sync_interval_seconds = safe_int(bybit_yaml.get("time_sync_interval_seconds")) or 60

    private_max_retries = safe_int(os.getenv("BYBIT_PRIVATE_MAX_RETRIES"))
    if private_max_retries is None:
        private_max_retries = safe_int(bybit_yaml.get("max_retries")) or 4

    private_backoff_base = safe_float(os.getenv("BYBIT_PRIVATE_BACKOFF_BASE"))
    if private_backoff_base is None:
        private_backoff_base = safe_float(bybit_yaml.get("backoff_base")) or 0.5

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
        "recv_window_ms": recv_window_ms,
        "time_sync_enabled": time_sync_enabled,
        "time_sync_interval_seconds": time_sync_interval_seconds,
        "private_max_retries": private_max_retries,
        "private_backoff_base": private_backoff_base,
    }

