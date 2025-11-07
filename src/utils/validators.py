#!/usr/bin/env python3
"""
Utilitaires de validation pour les paramètres du bot Bybit.

Ce module centralise les fonctions de validation communes utilisées
par plusieurs composants du bot pour éviter la duplication de code.
"""

from typing import Dict, Any, Optional, Set


def validate_string_param(param_name: str, param_value: Optional[str]) -> None:
    """
    Valide qu'un paramètre de type string n'est pas None ou vide.

    Args:
        param_name: Nom du paramètre (pour les messages d'erreur)
        param_value: Valeur du paramètre à valider

    Raises:
        ValueError: Si le paramètre est None ou vide
        TypeError: Si le paramètre n'est pas une chaîne de caractères
    """
    if param_value is None:
        raise ValueError(f"Le paramètre '{param_name}' ne peut pas être None")
    if not isinstance(param_value, str):
        raise TypeError(f"Le paramètre '{param_name}' doit être une chaîne de caractères, reçu: {type(param_value).__name__}")
    if not param_value.strip():
        raise ValueError(f"Le paramètre '{param_name}' ne peut pas être vide")


def validate_dict_param(param_name: str, param_value: Optional[Dict[str, Any]]) -> None:
    """
    Valide qu'un paramètre de type dict n'est pas None ou vide.

    Args:
        param_name: Nom du paramètre (pour les messages d'erreur)
        param_value: Valeur du paramètre à valider

    Raises:
        ValueError: Si le paramètre est None ou vide
        TypeError: Si le paramètre n'est pas un dictionnaire
    """
    if param_value is None:
        raise ValueError(f"Le paramètre '{param_name}' ne peut pas être None")
    if not isinstance(param_value, dict):
        raise TypeError(f"Le paramètre '{param_name}' doit être un dictionnaire, reçu: {type(param_value).__name__}")
    if not param_value:
        raise ValueError(f"Le paramètre '{param_name}' ne peut pas être un dictionnaire vide")


def validate_set_param(param_name: str, param_value: Optional[Set[str]]) -> None:
    """
    Valide qu'un paramètre de type set n'est pas None.

    Args:
        param_name: Nom du paramètre (pour les messages d'erreur)
        param_value: Valeur du paramètre à valider

    Raises:
        ValueError: Si le paramètre est None
        TypeError: Si le paramètre n'est pas un set
    """
    if param_value is None:
        raise ValueError(f"Le paramètre '{param_name}' ne peut pas être None")
    if not isinstance(param_value, set):
        raise TypeError(f"Le paramètre '{param_name}' doit être un set, reçu: {type(param_value).__name__}")


def validate_not_none(param_name: str, param_value: Any) -> None:
    """
    Valide qu'un paramètre n'est pas None.

    Args:
        param_name: Nom du paramètre (pour les messages d'erreur)
        param_value: Valeur du paramètre à valider

    Raises:
        ValueError: Si le paramètre est None
    """
    if param_value is None:
        raise ValueError(f"Le paramètre '{param_name}' ne peut pas être None")


def validate_positive_number(param_name: str, param_value: Any, include_zero: bool = False) -> None:
    """
    Valide qu'un paramètre est un nombre positif.

    Args:
        param_name: Nom du paramètre (pour les messages d'erreur)
        param_value: Valeur du paramètre à valider
        include_zero: Si True, autorise zéro (défaut: False)

    Raises:
        ValueError: Si le paramètre n'est pas un nombre positif
        TypeError: Si le paramètre n'est pas un nombre
    """
    if not isinstance(param_value, (int, float)):
        raise TypeError(f"Le paramètre '{param_name}' doit être un nombre, reçu: {type(param_value).__name__}")
    if include_zero and param_value < 0:
        raise ValueError(f"Le paramètre '{param_name}' doit être positif ou nul (>= 0), reçu: {param_value}")
    if not include_zero and param_value <= 0:
        raise ValueError(f"Le paramètre '{param_name}' doit être strictement positif (> 0), reçu: {param_value}")

