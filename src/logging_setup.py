"""Configuration du système de logging avec loguru."""

import sys
from loguru import logger
from config import get_settings


def setup_logging():
    """Configure le système de logging avec loguru."""
    # Supprimer le handler par défaut
    logger.remove()
    
    # Récupérer le niveau de log depuis la configuration
    settings = get_settings()
    log_level = settings["log_level"]
    
    # Ajouter un handler avec le format spécifié
    logger.add(
        sys.stdout,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {message}",
        level=log_level,
        colorize=True
    )
    
    return logger
