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
    # Fichier de log optionnel
    import os
    log_dir = os.getenv("LOG_DIR", "logs")
    log_file = os.getenv("LOG_FILE", "bybit_bot.log")
    rotation = os.getenv("LOG_ROTATION", "10 MB")
    retention = os.getenv("LOG_RETENTION", "7 days")
    compression = os.getenv("LOG_COMPRESSION", "zip")
    
    # Ajouter un handler avec le format spécifié
    logger.add(
        sys.stdout,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {message}",
        level=log_level,
        colorize=True
    )
    try:
        os.makedirs(log_dir, exist_ok=True)
        logger.add(
            f"{log_dir}/{log_file}",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {message}",
            level=log_level,
            rotation=rotation,
            retention=retention,
            compression=compression,
            enqueue=True,
            backtrace=False,
            diagnose=False
        )
    except Exception:
        # Si on ne peut pas créer le fichier, on garde stdout uniquement
        pass
    
    return logger
