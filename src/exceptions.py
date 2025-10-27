#!/usr/bin/env python3
"""
Exceptions personnalisées pour le bot Bybit.

Ce module définit les exceptions spécifiques utilisées dans le bot
pour une meilleure gestion d'erreurs et un debugging plus facile.
"""


class BotException(Exception):
    """Exception de base pour toutes les erreurs du bot."""
    pass


class BotConfigurationError(BotException):
    """Erreur de configuration du bot."""
    pass


class WebSocketConnectionError(BotException):
    """Erreur de connexion WebSocket."""
    pass


class APIError(BotException):
    """Erreur lors d'un appel API."""
    pass


class DataValidationError(BotException):
    """Erreur de validation des données."""
    pass


class FundingDataError(BotException):
    """Erreur liée aux données de funding."""
    pass


class VolatilityCalculationError(BotException):
    """Erreur lors du calcul de volatilité."""
    pass


class WatchlistError(BotException):
    """Erreur liée à la gestion de la watchlist."""
    pass


class MonitoringError(BotException):
    """Erreur dans le système de monitoring."""
    pass


class TradingError(BotException):
    """Erreur liée aux opérations de trading."""
    pass
