#!/usr/bin/env python3
"""
Constantes et limites du système pour le bot Bybit.

Ce module contient toutes les constantes utilisées pour la validation
de la configuration.
"""

# Limites de trading
MAX_LIMIT_RECOMMENDED = 1000  # Nombre maximum de symboles recommandé
MAX_SPREAD_PERCENTAGE = 1.0  # 100% - Spread maximum autorisé

# Limites temporelles
MAX_FUNDING_TIME_MINUTES = 1440  # 24 heures - Fenêtre de funding maximale

# Limites de volatilité
MIN_VOLATILITY_TTL_SECONDS = 10  # Minimum 10 secondes pour le cache
MAX_VOLATILITY_TTL_SECONDS = 3600  # Maximum 1 heure pour le cache

# Limites d'affichage
MIN_DISPLAY_INTERVAL_SECONDS = 1  # Minimum 1 seconde entre les rafraîchissements
MAX_DISPLAY_INTERVAL_SECONDS = 300  # Maximum 5 minutes entre les rafraîchissements

# Limites de threading
MAX_WORKERS_THREADPOOL = 2  # Nombre maximum de workers dans le thread pool

