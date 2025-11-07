# ⚙️ Guide de Configuration SmartOrderPlacer

## 🎯 Configuration de base

### Paramètres essentiels

```python
# Dans smart_order_placer.py
ORDER_REFRESH_INTERVAL = 5  # secondes d'attente avant refresh
MAX_RETRIES = 3             # nombre max de tentatives
MIN_ORDER_VALUE_USDT = 5.0  # minimum requis par Bybit

# Offsets par niveau de liquidité
MAKER_OFFSET_LEVELS = {
    "high_liquidity": 0.0002,    # 0.02% - marchés très liquides
    "medium_liquidity": 0.0005,  # 0.05% - marchés normaux
    "low_liquidity": 0.0010      # 0.10% - marchés peu liquides
}
```

### Configuration par symbole

```python
# Configuration personnalisée par symbole
SYMBOL_CONFIGS = {
    "BTCUSDT": {
        "min_offset": 0.0001,     # Offset minimum pour BTC
        "max_offset": 0.0010,     # Offset maximum pour BTC
        "refresh_interval": 3,    # Refresh plus rapide pour BTC
        "min_order_value": 10.0   # Minimum plus élevé pour BTC
    },
    "ETHUSDT": {
        "min_offset": 0.0002,
        "max_offset": 0.0020,
        "refresh_interval": 5,
        "min_order_value": 5.0
    },
    "ALTCOINS": {
        "min_offset": 0.0005,     # Offsets plus larges pour altcoins
        "max_offset": 0.0050,
        "refresh_interval": 8,    # Refresh plus lent pour altcoins
        "min_order_value": 5.0
    }
}
```

## 🔧 Optimisation des performances

### Cache configuration

```python
# Durées de cache optimisées
CACHE_DURATIONS = {
    "orderbook": 30,      # 30 secondes pour order book
    "instruments": 3600,  # 1 heure pour infos instruments
    "liquidity": 60       # 1 minute pour classification liquidité
}

# Taille maximale du cache
MAX_CACHE_SIZE = {
    "orderbook": 100,     # 100 order books max
    "instruments": 500    # 500 instruments max
}
```

### Threading et concurrence

```python
# Configuration ThreadPoolExecutor
THREAD_POOL_CONFIG = {
    "max_workers": 4,           # Nombre max de threads
    "thread_name_prefix": "smart_order_",
    "daemon": True              # Threads daemon
}

# Timeouts
TIMEOUTS = {
    "api_call": 10,            # 10s timeout pour appels API
    "order_placement": 5,      # 5s timeout pour placement ordre
    "execution_wait": 5        # 5s attente exécution
}
```

## 📊 Monitoring et métriques

### Logs de performance

```python
# Configuration des logs
LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s | %(levelname)s | %(message)s",
    "handlers": [
        "console",      # Console pour debug
        "file",         # Fichier pour historique
        "metrics"       # Métriques pour monitoring
    ]
}

# Métriques à tracker
METRICS_TO_TRACK = [
    "success_rate",           # Taux de succès des ordres
    "avg_execution_time",     # Temps moyen d'exécution
    "avg_retry_count",        # Nombre moyen de retries
    "liquidity_distribution", # Distribution des niveaux de liquidité
    "price_accuracy",         # Précision des prix calculés
    "cache_hit_rate"          # Taux de hit du cache
]
```

### Dashboard de monitoring

```python
# Configuration dashboard
DASHBOARD_CONFIG = {
    "update_interval": 5,     # Mise à jour toutes les 5 secondes
    "metrics_retention": 24,  # Conservation 24h des métriques
    "alerts": {
        "success_rate_low": 0.8,      # Alerte si succès < 80%
        "execution_time_high": 10,    # Alerte si temps > 10s
        "retry_count_high": 5         # Alerte si retries > 5
    }
}
```

## 🚨 Gestion des erreurs

### Erreurs courantes et solutions

```python
ERROR_HANDLING = {
    "110094": {  # Order does not meet minimum order value
        "action": "adjust_quantity",
        "retry": True,
        "max_attempts": 3
    },
    "170140": {  # Order value exceeded lower limit
        "action": "increase_quantity",
        "retry": True,
        "max_attempts": 2
    },
    "170134": {  # Order price has too many decimals
        "action": "format_price",
        "retry": True,
        "max_attempts": 1
    },
    "10001": {   # Missing parameters
        "action": "validate_parameters",
        "retry": False,
        "log_level": "ERROR"
    }
}
```

### Fallback strategies

```python
# Stratégies de fallback
FALLBACK_STRATEGIES = {
    "smart_placer_failed": {
        "action": "use_classic_placement",
        "conditions": ["max_retries_exceeded", "api_error"]
    },
    "liquidity_classification_failed": {
        "action": "use_medium_liquidity",
        "conditions": ["orderbook_unavailable", "calculation_error"]
    },
    "price_calculation_failed": {
        "action": "use_market_price_offset",
        "conditions": ["orderbook_empty", "invalid_data"]
    }
}
```

## 🔄 Ajustements dynamiques

### Adaptation automatique

```python
# Ajustements basés sur les performances
DYNAMIC_ADJUSTMENTS = {
    "offset_adjustment": {
        "high_success_rate": 0.95,    # Si succès > 95%, réduire offset
        "low_success_rate": 0.80,     # Si succès < 80%, augmenter offset
        "adjustment_factor": 0.1      # Ajustement de 10%
    },
    "refresh_interval": {
        "fast_markets": 3,            # Marchés rapides: 3s
        "slow_markets": 8,            # Marchés lents: 8s
        "volatile_markets": 5         # Marchés volatils: 5s
    }
}
```

### Machine Learning (futur)

```python
# Configuration ML pour prédiction de liquidité
ML_CONFIG = {
    "enabled": False,                 # Pas encore implémenté
    "model_path": "models/liquidity_predictor.pkl",
    "features": [
        "spread_history",
        "volume_history", 
        "volatility",
        "time_of_day",
        "market_conditions"
    ],
    "retrain_interval": 24,          # Retrain toutes les 24h
    "prediction_confidence": 0.8     # Confiance minimum 80%
}
```

## 🧪 Tests et validation

### Tests unitaires

```python
# Configuration des tests
TEST_CONFIG = {
    "test_symbols": ["BTCUSDT", "ETHUSDT", "ADAUSDT"],
    "test_categories": ["linear", "spot"],
    "test_sides": ["Buy", "Sell"],
    "test_quantities": ["0.001", "0.01", "0.1"],
    "mock_api": True,                 # Utiliser API mock pour tests
    "test_timeout": 30               # Timeout 30s pour tests
}
```

### Tests d'intégration

```python
# Tests d'intégration avec Bybit
INTEGRATION_TESTS = {
    "testnet": True,                 # Utiliser testnet pour tests
    "real_orders": False,            # Pas d'ordres réels
    "validation_orders": True,       # Ordres de validation uniquement
    "cleanup_after": True            # Nettoyage après tests
}
```

## 📈 Optimisation avancée

### Stratégies par type de marché

```python
# Stratégies adaptées au type de marché
MARKET_STRATEGIES = {
    "bull_market": {
        "buy_offset_multiplier": 0.8,    # Offsets plus serrés pour achats
        "sell_offset_multiplier": 1.2,   # Offsets plus larges pour ventes
        "refresh_interval": 3
    },
    "bear_market": {
        "buy_offset_multiplier": 1.2,    # Offsets plus larges pour achats
        "sell_offset_multiplier": 0.8,   # Offsets plus serrés pour ventes
        "refresh_interval": 5
    },
    "sideways_market": {
        "buy_offset_multiplier": 1.0,    # Offsets normaux
        "sell_offset_multiplier": 1.0,
        "refresh_interval": 8
    }
}
```

### Optimisation des coûts

```python
# Optimisation pour minimiser les coûts
COST_OPTIMIZATION = {
    "prefer_maker_rebate": True,     # Préférer les ordres maker
    "min_spread_threshold": 0.001,   # Spread minimum 0.1%
    "max_slippage": 0.002,          # Slippage maximum 0.2%
    "cost_per_trade_target": 0.0001  # Coût cible par trade
}
```

## 🔐 Sécurité et fiabilité

### Validation des paramètres

```python
# Validation stricte des paramètres
VALIDATION_RULES = {
    "symbol_format": r"^[A-Z]{3,10}USDT$",
    "side_values": ["Buy", "Sell"],
    "category_values": ["linear", "inverse", "spot"],
    "quantity_min": 0.0001,
    "quantity_max": 1000000,
    "price_min": 0.00001,
    "price_max": 1000000
}
```

### Circuit breaker

```python
# Circuit breaker pour éviter les erreurs en cascade
CIRCUIT_BREAKER = {
    "failure_threshold": 5,         # 5 échecs consécutifs
    "recovery_timeout": 60,         # 60s avant récupération
    "half_open_max_calls": 3,       # 3 appels en half-open
    "excluded_errors": ["110094"]   # Erreurs exclues du circuit breaker
}
```

---

## 📋 Checklist de configuration

### ✅ Configuration de base
- [ ] Paramètres ORDER_REFRESH_INTERVAL et MAX_RETRIES définis
- [ ] Offsets MAKER_OFFSET_LEVELS configurés
- [ ] Minimum MIN_ORDER_VALUE_USDT défini
- [ ] Cache configuré avec durées appropriées

### ✅ Monitoring
- [ ] Logs configurés avec niveau approprié
- [ ] Métriques de performance activées
- [ ] Dashboard de monitoring configuré
- [ ] Alertes configurées

### ✅ Gestion d'erreurs
- [ ] Mapping des erreurs Bybit configuré
- [ ] Stratégies de fallback définies
- [ ] Circuit breaker configuré
- [ ] Validation des paramètres activée

### ✅ Tests
- [ ] Tests unitaires configurés
- [ ] Tests d'intégration configurés
- [ ] Tests sur testnet validés
- [ ] Tests de performance effectués

### ✅ Optimisation
- [ ] Stratégies par type de marché configurées
- [ ] Optimisation des coûts activée
- [ ] Ajustements dynamiques configurés
- [ ] Monitoring des performances en place

---

**Note** : Cette configuration doit être adaptée selon vos besoins spécifiques et testée en environnement de développement avant déploiement en production.
