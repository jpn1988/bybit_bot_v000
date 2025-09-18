"""Exceptions personnalisées pour le bot Bybit."""


class BotError(Exception):
    """Base des erreurs du bot."""


class NoSymbolsError(BotError):
    """Aucun symbole ne correspond aux critères ou n'est disponible."""


class FundingUnavailableError(BotError):
    """Aucun funding disponible pour la catégorie sélectionnée."""


class ConfigError(BotError):
    """Erreur de configuration (paramètres invalides ou manquants)."""


