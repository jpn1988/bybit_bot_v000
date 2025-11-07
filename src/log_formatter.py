#!/usr/bin/env python3
"""
Formatteur de messages de log standardisé pour le bot Bybit.

Ce module fournit des fonctions pour formater les messages de log
de manière cohérente dans tout le bot.
"""

from typing import Any, Optional


def format_success(component: str, action: str, details: Optional[str] = None) -> str:
    """
    Formate un message de succès.

    Args:
        component: Nom du composant (ex: "WebSocket", "API")
        action: Action effectuée (ex: "connecté", "démarré")
        details: Détails supplémentaires (optionnel)

    Returns:
        str: Message formaté

    Example:
        >>> format_success("WebSocket", "connecté", "2 connexions actives")
        "✅ WebSocket: connecté - 2 connexions actives"
    """
    message = f"✅ {component}: {action}"
    if details:
        message += f" - {details}"
    return message


def format_warning(component: str, issue: str, solution: Optional[str] = None) -> str:
    """
    Formate un message d'avertissement.

    Args:
        component: Nom du composant
        issue: Problème rencontré
        solution: Solution suggérée (optionnel)

    Returns:
        str: Message formaté

    Example:
        >>> format_warning("API", "rate limit atteint", "attendre 60s")
        "⚠️ API: rate limit atteint - attendre 60s"
    """
    message = f"⚠️ {component}: {issue}"
    if solution:
        message += f" - {solution}"
    return message


def format_error(component: str, error: str, context: Optional[str] = None) -> str:
    """
    Formate un message d'erreur.

    Args:
        component: Nom du composant
        error: Erreur rencontrée
        context: Contexte supplémentaire (optionnel)

    Returns:
        str: Message formaté

    Example:
        >>> format_error("WebSocket", "connexion fermée", "timeout")
        "❌ WebSocket: connexion fermée - timeout"
    """
    message = f"❌ {component}: {error}"
    if context:
        message += f" - {context}"
    return message


def format_info(component: str, message: str, details: Optional[str] = None) -> str:
    """
    Formate un message d'information.

    Args:
        component: Nom du composant
        message: Message principal
        details: Détails supplémentaires (optionnel)

    Returns:
        str: Message formaté

    Example:
        >>> format_info("Bot", "démarré", "mode testnet")
        "ℹ️ Bot: démarré - mode testnet"
    """
    formatted = f"ℹ️ {component}: {message}"
    if details:
        formatted += f" - {details}"
    return formatted


def format_debug(component: str, action: str, data: Optional[Any] = None) -> str:
    """
    Formate un message de debug.

    Args:
        component: Nom du composant
        action: Action en cours
        data: Données de debug (optionnel)

    Returns:
        str: Message formaté

    Example:
        >>> format_debug("Filter", "appliqué", "10 symboles gardés")
        "🔍 Filter: appliqué - 10 symboles gardés"
    """
    message = f"🔍 {component}: {action}"
    if data is not None:
        message += f" - {data}"
    return message
