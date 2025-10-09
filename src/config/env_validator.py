#!/usr/bin/env python3
"""
Validateur de variables d'environnement pour le bot Bybit.

Ce module détecte et signale les variables d'environnement inconnues
pour aider à identifier les fautes de frappe.
"""

import os
import sys
from typing import Set


# Variables d'environnement valides pour la configuration
VALID_ENV_VARS = {
    "BYBIT_API_KEY",
    "BYBIT_API_SECRET",
    "TESTNET",
    "TIMEOUT",
    "LOG_LEVEL",
    "SPREAD_MAX",
    "VOLUME_MIN_MILLIONS",
    "VOLATILITY_MIN",
    "VOLATILITY_MAX",
    "FUNDING_MIN",
    "FUNDING_MAX",
    "CATEGORY",
    "LIMIT",
    "VOLATILITY_TTL_SEC",
    "FUNDING_TIME_MIN_MINUTES",
    "FUNDING_TIME_MAX_MINUTES",
    "WS_PRIV_CHANNELS",
    "DISPLAY_INTERVAL_SECONDS",
    "PUBLIC_HTTP_MAX_CALLS_PER_SEC",
    "PUBLIC_HTTP_WINDOW_SECONDS",
}

# Variables à ignorer complètement (faux positifs système)
IGNORED_ENV_VARS = {
    "FPS_BROWSER_APP_PROFILE_STRING",
    "FPS_BROWSER_APP_PROFILE_STRING_OLD",
}

# Préfixes de variables système à ignorer
SYSTEM_PREFIXES = [
    "PATH", "PYTHON", "WINDOWS", "USER", "HOME", "TEMP", "TMP",
    "PROGRAM", "SYSTEM", "ALLUSER", "APPDATA", "LOCALAPPDATA",
    "COMPUTERNAME", "USERNAME", "USERPROFILE", "WINDIR", "COMSPEC",
    "PATHEXT", "PROCESSOR", "NUMBER_OF_PROCESSORS", "OS", "DRIVE",
    "VIRTUAL_ENV", "CONDA", "PIP", "NODE", "NPM", "GIT", "SSH",
    "DOCKER", "KUBERNETES", "AWS", "AZURE", "GOOGLE", "JAVA",
    "MAVEN", "GRADLE", "NODEJS", "YARN", "BOWER", "FPS", "BROWSER",
    "APP", "PROFILE", "STRING",
]

# Mots-clés liés au bot
BOT_KEYWORDS = [
    "BYBIT", "FUNDING", "VOLATILITY", "SPREAD", "VOLUME",
    "CATEGORY", "LIMIT", "TTL", "TIME", "MIN", "MAX",
    "CHANNELS", "WS", "PRIV",
]


def is_system_variable(var_name: str) -> bool:
    """
    Vérifie si une variable d'environnement est une variable système.
    
    Args:
        var_name: Nom de la variable
        
    Returns:
        bool: True si c'est une variable système
    """
    return any(prefix in var_name.upper() for prefix in SYSTEM_PREFIXES)


def is_bot_related(var_name: str) -> bool:
    """
    Vérifie si une variable d'environnement semble liée au bot.
    
    Args:
        var_name: Nom de la variable
        
    Returns:
        bool: True si la variable semble liée au bot
    """
    return any(keyword in var_name.upper() for keyword in BOT_KEYWORDS)


def find_unknown_bot_variables() -> Set[str]:
    """
    Trouve toutes les variables d'environnement inconnues liées au bot.
    
    Returns:
        Set[str]: Ensemble des variables inconnues liées au bot
    """
    all_env_vars = set(os.environ.keys())
    unknown_vars = all_env_vars - VALID_ENV_VARS - IGNORED_ENV_VARS
    
    # Filtrer pour ne garder que les variables liées au bot
    bot_related_unknown = set()
    for var in unknown_vars:
        if not is_system_variable(var) and is_bot_related(var):
            bot_related_unknown.add(var)
    
    return bot_related_unknown


def validate_environment_variables() -> None:
    """
    Valide les variables d'environnement et affiche des avertissements
    pour les variables inconnues liées au bot.
    
    Cette fonction détecte les fautes de frappe dans les noms de variables.
    """
    bot_related_unknown = find_unknown_bot_variables()
    
    if not bot_related_unknown:
        return  # Aucune variable inconnue, tout est OK
    
    # Afficher les avertissements sur stderr
    for var in sorted(bot_related_unknown):
        print(
            f"⚠️ Variable d'environnement inconnue ignorée: {var}",
            file=sys.stderr,
        )
    
    # Afficher la liste des variables valides
    valid_vars_str = ", ".join(sorted(VALID_ENV_VARS))
    print(f"💡 Variables valides: {valid_vars_str}", file=sys.stderr)
    
    # Essayer aussi avec le logger si disponible
    try:
        import logging
        logger = logging.getLogger(__name__)
        
        for var in sorted(bot_related_unknown):
            logger.warning(f"⚠️ Variable d'environnement inconnue ignorée: {var}")
        
        logger.warning(f"💡 Variables valides: {valid_vars_str}")
    except Exception:
        pass  # Le message a déjà été affiché sur stderr

