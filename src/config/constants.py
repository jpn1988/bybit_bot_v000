#!/usr/bin/env python3
"""
Constantes et limites du système pour le bot Bybit.

Ce module contient toutes les constantes utilisées pour la validation
de la configuration.
"""

# ============================================================================
# LIMITES DE TRADING
# ============================================================================
MAX_LIMIT_RECOMMENDED = 1000  # Nombre maximum de symboles recommandé
MAX_SPREAD_PERCENTAGE = 1.0  # 100% - Spread maximum autorisé

# ============================================================================
# LIMITES TEMPORELLES
# ============================================================================
MAX_FUNDING_TIME_MINUTES = 1440  # 24 heures - Fenêtre de funding maximale

# ============================================================================
# LIMITES DE VOLATILITÉ
# ============================================================================
MIN_VOLATILITY_TTL_SECONDS = 10  # Minimum 10 secondes pour le cache
MAX_VOLATILITY_TTL_SECONDS = 3600  # Maximum 1 heure pour le cache

# ============================================================================
# LIMITES D'AFFICHAGE
# ============================================================================
MIN_DISPLAY_INTERVAL_SECONDS = 1  # Minimum 1 seconde entre les rafraîchissements
MAX_DISPLAY_INTERVAL_SECONDS = 300  # Maximum 5 minutes entre les rafraîchissements

# ============================================================================
# LIMITES DE THREADING
# ============================================================================
MAX_WORKERS_THREADPOOL = 2  # Nombre maximum de workers dans le thread pool

# ============================================================================
# INTERVALLES ET TIMEOUTS PAR DÉFAUT
# ============================================================================
DEFAULT_FUNDING_UPDATE_INTERVAL = 5  # secondes - Intervalle de mise à jour des funding
DEFAULT_METRICS_INTERVAL = 5  # minutes - Intervalle de monitoring des métriques
DEFAULT_HTTP_TIMEOUT = 30  # secondes - Timeout par défaut pour les requêtes HTTP
DEFAULT_WEBSOCKET_TIMEOUT = 10  # secondes - Timeout pour les connexions WebSocket
DEFAULT_THREAD_SHUTDOWN_TIMEOUT = 5  # secondes - Timeout pour l'arrêt des threads
DEFAULT_MAX_RETRIES = 3  # Nombre maximum de tentatives pour les opérations

# ============================================================================
# LIMITES DE DONNÉES
# ============================================================================
MAX_SYMBOLS_PER_CONNECTION = 200  # Nombre maximum de symboles par connexion WebSocket
DEFAULT_PAGINATION_LIMIT = 1000  # Limite par défaut pour la pagination API
MAX_FUNDING_RATE_DEVIATION = 0.1  # 10% - Déviation maximale du funding rate

# ============================================================================
# FORMATS ET AFFICHAGE
# ============================================================================
DEFAULT_DECIMAL_PLACES = 4  # Nombre de décimales par défaut pour l'affichage
DEFAULT_PERCENTAGE_PRECISION = 2  # Précision par défaut pour les pourcentages

# ============================================================================
# PARAMÈTRES DE CONFIGURATION PAR DÉFAUT (parameters.yaml)
# ============================================================================

# Catégories de contrats
CATEGORY_LINEAR = "linear"  # Contrats USDT
CATEGORY_INVERSE = "inverse"  # Contrats USD
CATEGORY_BOTH = "both"  # Tous les contrats

# Limites de funding
DEFAULT_FUNDING_MIN = 0.0001  # Funding minimum par défaut (0.01%)
DEFAULT_FUNDING_MAX = None  # Pas de limite maximale par défaut

# Volume et spread
DEFAULT_VOLUME_MIN_MILLIONS = 100  # Volume minimum par défaut (100M USDT)
DEFAULT_SPREAD_MAX = None  # Pas de limite de spread par défaut

# Limites générales
DEFAULT_LIMIT = 20  # Limite par défaut de symboles à afficher
DEFAULT_VOLATILITY_TTL_SEC = 60  # TTL du cache volatilité par défaut (60 secondes)

# Temps de funding
DEFAULT_FUNDING_TIME_MIN_MINUTES = None  # Pas de minimum par défaut
DEFAULT_FUNDING_TIME_MAX_MINUTES = 60  # Maximum 60 minutes avant funding

# Affichage
DEFAULT_DISPLAY_INTERVAL_SECONDS = 5  # Intervalle d'affichage par défaut (5 secondes)
DEFAULT_FUNDING_THRESHOLD_MINUTES = 1  # Seuil de détection du funding imminent (1 minute)

# ============================================================================
# POIDS PAR DÉFAUT (Système de scoring)
# ============================================================================
DEFAULT_WEIGHT_FUNDING = 1000  # Poids du funding rate (CRITÈRE PRINCIPAL)
DEFAULT_WEIGHT_VOLUME = 0.01  # Poids du volume (logarithme)
DEFAULT_WEIGHT_SPREAD = 0.1  # Poids du spread (soustrait)
DEFAULT_WEIGHT_VOLATILITY = 0.05  # Poids de la volatilité (soustrait)
DEFAULT_TOP_SYMBOLS = 20  # Nombre maximum de symboles à conserver après tri

# ============================================================================
# TRADING AUTOMATIQUE
# ============================================================================
DEFAULT_AUTO_TRADING_ENABLED = True  # Activer le trading automatique par défaut
DEFAULT_ORDER_SIZE_USDT = 10  # Taille de l'ordre par défaut (10 USDT)
DEFAULT_ORDER_OFFSET_PERCENT = 0.1  # Offset du prix limite par défaut (0.1%)
DEFAULT_MAX_POSITIONS = 1  # Nombre maximum de positions simultanées
DEFAULT_DRY_RUN = False  # Mode test désactivé par défaut

# ============================================================================
# LIMITES POUR MAKER CONFIG
# ============================================================================
DEFAULT_MAX_RETRIES_PERP = 3  # Nombre de tentatives max pour ordres perp par défaut
DEFAULT_MAX_RETRIES_SPOT = 8  # Nombre de tentatives max pour ordres spot par défaut
MIN_REFRESH_INTERVAL_SECONDS = 0.1  # Intervalle minimum de rafraîchissement (secondes)

# ============================================================================
# LIMITES POUR SPOT_HEDGE (en ratio, comme dans parameters.yaml)
# ============================================================================
MIN_SPOT_HEDGE_OFFSET_PERCENT = 0.0  # Offset minimum (0.0 = 0%)
MAX_SPOT_HEDGE_OFFSET_PERCENT = 1.0  # Offset maximum (1.0 = 100%)
MIN_SPOT_HEDGE_TIMEOUT_MINUTES = 1  # Timeout minimum pour spot hedge (minutes)

# ============================================================================
# LIMITES POUR CLOSE ORDERS (en ratio, comme dans parameters.yaml)
# ============================================================================
MIN_CLOSE_ORDER_OFFSET_PERCENT = 0.0  # Offset minimum pour fermeture (0.0 = 0%)
MAX_CLOSE_ORDER_OFFSET_PERCENT = 1.0  # Offset maximum pour fermeture (1.0 = 100%)
MIN_ORDER_TIMEOUT_MINUTES = 1  # Timeout minimum pour les ordres (minutes)

