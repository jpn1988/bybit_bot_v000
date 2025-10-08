"""Configuration du système de logging avec loguru."""

import sys
from datetime import datetime
from loguru import logger

try:
    from .config_unified import get_settings
except ImportError:
    from config_unified import get_settings

# Variable globale pour éviter les reentrant calls
_shutdown_logging_active = False
_logging_disabled = False


def disable_logging():
    """Désactive le logging pour éviter les erreurs lors de l'arrêt."""
    global _logging_disabled, _shutdown_logging_active
    _logging_disabled = True
    _shutdown_logging_active = True


def safe_log_info(message: str):
    """Logging sécurisé qui utilise print() si le logging est désactivé."""
    if _logging_disabled or _shutdown_logging_active:
        try:
            print(message)
            sys.stdout.flush()
        except Exception:
            pass  # Ignorer toute erreur
    else:
        try:
            logger.info(message)
        except Exception:
            try:
                print(message)
            except Exception:
                pass  # Ignorer toute erreur


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

    # Ajouter un handler avec le format spécifié et protection contre
    # les reentrant calls
    logger.add(
        sys.stdout,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {message}",
        level=log_level,
        colorize=True,
        enqueue=False,  # Éviter la file d'attente pour stdout
        backtrace=False,
        diagnose=False,
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
            diagnose=False,
        )
    except Exception:
        # Si on ne peut pas créer le fichier, on garde stdout uniquement
        pass

    return logger


def log_shutdown_summary(
    logger, last_candidates: list = None, uptime_seconds: float = 0.0
) -> None:
    """
    Affiche un résumé d'arrêt professionnel et structuré.

    Args:
        logger: Instance du logger à utiliser
        last_candidates: Liste des derniers candidats surveillés
        uptime_seconds: Temps de fonctionnement en secondes
    """
    global _shutdown_logging_active

    # Éviter les reentrant calls
    if _shutdown_logging_active:
        return

    _shutdown_logging_active = True

    try:
        # Utiliser print() au lieu de logger.info() pour éviter les reentrant calls
        banner_width = 38
        separator = "═" * banner_width

        print(f"\n{separator}")
        print(" 🛑 ARRÊT DU BOT")
        print(f" 📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{separator}")

        # Section étapes de shutdown
        print("\n🔻 Étapes de shutdown :")
        shutdown_steps = [
            ("Fermeture WebSockets", "OK"),
            ("Thread volatilité", "arrêté"),
            ("Clients HTTP", "fermés"),
            ("Nettoyage final", "terminé"),
        ]

        for i, (step_name, status) in enumerate(shutdown_steps):
            prefix = "└──" if i == len(shutdown_steps) - 1 else "├──"
            print(f"   {prefix} {step_name} … {status}")

        # Section derniers candidats
        if last_candidates:
            candidates_display = last_candidates[:7]  # Limiter à 7 candidats
            print(f"\n🎯 Derniers candidats surveillés : {candidates_display}")

        # Message final avec uptime
        uptime_hours = uptime_seconds / 3600
        uptime_minutes = (uptime_seconds % 3600) / 60

        if uptime_hours >= 1:
            uptime_str = f"{uptime_hours:.0f}h{uptime_minutes:.0f}m"
        else:
            uptime_str = f"{uptime_minutes:.0f}m"

        print(f"\n✅ Bot arrêté proprement (uptime: {uptime_str})")
        print("")  # Ligne vide finale

        # Forcer le flush pour s'assurer que tout est affiché
        sys.stdout.flush()

    except Exception as e:
        # En cas d'erreur, utiliser print() simple
        try:
            print(f"\n🛑 Bot arrêté (erreur logging: {e})")
        except Exception:
            pass  # Ignorer toute erreur finale
    finally:
        _shutdown_logging_active = False
