"""Exceptions personnalisées pour le bot Bybit."""


class BotError(Exception):
    """Base des erreurs du bot."""


class NoSymbolsError(BotError):
    """Aucun symbole ne correspond aux critères ou n'est disponible."""
