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
    
    return {
        "testnet": os.getenv("TESTNET", "true").lower() == "true",
        "timeout": int(os.getenv("TIMEOUT", "10")),
        "log_level": os.getenv("LOG_LEVEL", "INFO").upper(),
        "api_key": api_key,
        "api_secret": api_secret
    }
