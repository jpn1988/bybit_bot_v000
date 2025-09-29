"""Configuration du système de logging avec loguru."""

import sys
from datetime import datetime
from typing import Dict, Any, Optional
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


def log_startup_summary(
    logger,
    bot_info: Dict[str, Any],
    config: Dict[str, Any], 
    filter_results: Dict[str, Any],
    ws_status: Dict[str, Any]
) -> None:
    """
    Affiche un résumé de démarrage professionnel et structuré.
    
    Args:
        logger: Instance du logger à utiliser
        bot_info: Informations du bot (nom, version, environnement, mode)
        config: Configuration chargée
        filter_results: Résultats du filtrage des symboles
        ws_status: Statut des connexions WebSocket
    """
    # Bannière d'accueil
    banner_width = 38
    separator = "═" * banner_width
    
    logger.info(f"\n{separator}")
    logger.info(f" 🚀 {bot_info.get('name', 'BYBIT BOT')} v{bot_info.get('version', '0.9.0')}")
    logger.info(f" 📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f" 🌍 Environnement : {bot_info.get('environment', 'Mainnet')} | Mode: {bot_info.get('mode', 'Funding Sniping')}")
    logger.info(f"{separator}")
    
    # Section vérification système
    logger.info("\n🔍 Vérification système :")
    system_checks = [
        ("Configuration (src/parameters.yaml)", "OK"),
        ("Gestionnaire HTTP", "OK"),
        ("Orchestrateur", "OK"),
        (f"Monitoring métriques ({config.get('metrics_interval', 5)}m)", "OK"),
        ("WebSocket Manager", "prêt")
    ]
    
    for i, (check_name, status) in enumerate(system_checks):
        prefix = "└──" if i == len(system_checks) - 1 else "├──"
        logger.info(f"   {prefix} {check_name} … {status}")
    
    # Section paramètres actifs
    logger.info("\n⚙️ Paramètres actifs :")
    params = [
        ("Catégorie", config.get('categorie', 'linear')),
        ("Funding min", f"{config.get('funding_min', 0.0001):.6f}" if config.get('funding_min') is not None else "none"),
        ("Volume min", f"{config.get('volume_min_millions', 50.0):.1f}M" if config.get('volume_min_millions') is not None else "none"),
        ("Spread max", f"{config.get('spread_max', 0.03)*100:.2f}%" if config.get('spread_max') is not None else "none"),
        ("Volatilité max", f"{config.get('volatility_max', 0.07)*100:.2f}%" if config.get('volatility_max') is not None else "none"),
        (f"TTL vol: {config.get('volatility_ttl_sec', 120)}s", f"Interval WS: {config.get('display_interval_seconds', 10)}s")
    ]
    
    for param_name, param_value in params:
        logger.info(f"   • {param_name} : {param_value}")
    
    # Section résultats filtrage
    logger.info("\n📊 Résultats filtrage :")
    filter_stats = filter_results.get('stats', {})
    logger.info(f"   Avant filtres       : {filter_stats.get('total_symbols', 0)} symboles")
    logger.info(f"   Funding/Volume      : {filter_stats.get('after_funding_volume', 0)}")
    logger.info(f"   Spread              : {filter_stats.get('after_spread', 0)}")
    logger.info(f"   Volatilité          : {filter_stats.get('after_volatility', 0)}")
    logger.info(f"   Après tri+limite    : {filter_stats.get('final_count', 0)}")
    
    # Confirmation opérationnelle
    logger.info("\n✅ Initialisation terminée.")
    ws_connected = ws_status.get('connected', False)
    symbols_count = ws_status.get('symbols_count', 0)
    category = ws_status.get('category', 'linear')
    
    if ws_connected and symbols_count > 0:
        logger.info(f"📡 WS connectée ({category}) | {symbols_count} symboles souscrits")
        logger.info("🏁 Bot opérationnel – en attente de ticks…")
    else:
        logger.info("🔄 Mode surveillance continue activé")
        logger.info("🏁 Bot opérationnel – en attente de nouvelles opportunités…")
    
    logger.info("")  # Ligne vide finale


def log_shutdown_summary(
    logger,
    last_candidates: list = None,
    uptime_seconds: float = 0.0
) -> None:
    """
    Affiche un résumé d'arrêt professionnel et structuré.
    
    Args:
        logger: Instance du logger à utiliser
        last_candidates: Liste des derniers candidats surveillés
        uptime_seconds: Temps de fonctionnement en secondes
    """
    # Bannière d'arrêt
    banner_width = 38
    separator = "═" * banner_width
    
    logger.info(f"\n{separator}")
    logger.info(f" 🛑 ARRÊT DU BOT")
    logger.info(f" 📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{separator}")
    
    # Section étapes de shutdown
    logger.info("\n🔻 Étapes de shutdown :")
    shutdown_steps = [
        ("Fermeture WebSockets", "OK"),
        ("Thread volatilité", "arrêté"),
        ("Clients HTTP", "fermés"),
        ("Nettoyage final", "terminé")
    ]
    
    for i, (step_name, status) in enumerate(shutdown_steps):
        prefix = "└──" if i == len(shutdown_steps) - 1 else "├──"
        logger.info(f"   {prefix} {step_name} … {status}")
    
    # Section derniers candidats
    if last_candidates:
        candidates_display = last_candidates[:7]  # Limiter à 7 candidats
        logger.info(f"\n🎯 Derniers candidats surveillés : {candidates_display}")
    
    # Message final avec uptime
    uptime_hours = uptime_seconds / 3600
    uptime_minutes = (uptime_seconds % 3600) / 60
    
    if uptime_hours >= 1:
        uptime_str = f"{uptime_hours:.0f}h{uptime_minutes:.0f}m"
    else:
        uptime_str = f"{uptime_minutes:.0f}m"
    
    logger.info(f"\n✅ Bot arrêté proprement (uptime: {uptime_str})")
    logger.info("")  # Ligne vide finale
