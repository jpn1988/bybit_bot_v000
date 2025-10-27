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

# Intervalles et timeouts par défaut
DEFAULT_FUNDING_UPDATE_INTERVAL = 5  # secondes - Intervalle de mise à jour des funding
DEFAULT_METRICS_INTERVAL = 5  # minutes - Intervalle de monitoring des métriques
DEFAULT_HTTP_TIMEOUT = 30  # secondes - Timeout par défaut pour les requêtes HTTP
DEFAULT_WEBSOCKET_TIMEOUT = 10  # secondes - Timeout pour les connexions WebSocket
DEFAULT_THREAD_SHUTDOWN_TIMEOUT = 5  # secondes - Timeout pour l'arrêt des threads
DEFAULT_MAX_RETRIES = 3  # Nombre maximum de tentatives pour les opérations

# Limites de données
MAX_SYMBOLS_PER_CONNECTION = 200  # Nombre maximum de symboles par connexion WebSocket
DEFAULT_PAGINATION_LIMIT = 1000  # Limite par défaut pour la pagination API
MAX_FUNDING_RATE_DEVIATION = 0.1  # 10% - Déviation maximale du funding rate

# Formats et affichage
DEFAULT_DECIMAL_PLACES = 4  # Nombre de décimales par défaut pour l'affichage
DEFAULT_PERCENTAGE_PRECISION = 2  # Précision par défaut pour les pourcentages

