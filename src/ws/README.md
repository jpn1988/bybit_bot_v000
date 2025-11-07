# Module WebSocket Refactorisé

## 🎯 Objectif

Ce module refactorise l'ancien `ws_manager.py` monolithique en modules spécialisés pour améliorer la lisibilité, la maintenabilité et la testabilité.

## 📁 Structure

```
src/ws/
├── __init__.py              # Package WebSocket
├── connection_pool.py       # Gestion ThreadPoolExecutor et lifecycle
├── strategy.py              # Stratégie de répartition linear/inverse
├── handlers.py              # Callbacks et métriques
├── manager.py               # Façade WebSocketManager simplifiée
└── README.md                # Cette documentation
```

## 🔧 Modules Spécialisés

### 1. `connection_pool.py` - Gestion du Pool de Connexions

**Responsabilités :**
- Créer et gérer le ThreadPoolExecutor
- Exécuter les connexions WebSocket dans des threads
- Gérer l'arrêt propre avec timeout
- Surveiller l'état des threads

**Classes :**
- `WebSocketConnectionPool` : Gestionnaire principal du pool

**Avantages :**
- ✅ Centralise la gestion des threads
- ✅ Évite la duplication de code
- ✅ Gestion robuste des timeouts
- ✅ Monitoring des threads

### 2. `strategy.py` - Stratégie de Connexion

**Responsabilités :**
- Analyser les symboles fournis
- Déterminer la stratégie de connexion optimale
- Séparer les symboles par catégorie
- Optimiser le nombre de connexions

**Classes :**
- `ConnectionStrategy` : Dataclass pour la stratégie
- `WebSocketConnectionStrategy` : Gestionnaire de stratégie

**Avantages :**
- ✅ Logique de répartition claire
- ✅ Validation des symboles
- ✅ Optimisation automatique
- ✅ Support des stratégies duales

### 3. `handlers.py` - Callbacks et Métriques

**Responsabilités :**
- Gérer les callbacks de données
- Tracker les métriques de connexion
- Router les données vers les gestionnaires appropriés
- Gérer les erreurs et exceptions

**Classes :**
- `WebSocketMetrics` : Dataclass pour les métriques
- `WebSocketHandlers` : Gestionnaire de callbacks

**Avantages :**
- ✅ Centralise la gestion des callbacks
- ✅ Métriques détaillées
- ✅ Gestion d'erreurs robuste
- ✅ Interface claire

### 4. `manager.py` - Façade Simplifiée

**Responsabilités :**
- Orchestrer les modules spécialisés
- Gérer le cycle de vie des connexions
- Fournir une interface simple et cohérente
- Maintenir la compatibilité

**Classes :**
- `WebSocketManager` : Façade principale

**Avantages :**
- ✅ Interface simplifiée
- ✅ Séparation des responsabilités
- ✅ Code plus lisible
- ✅ Facile à tester

## 🔄 Migration

### Avant (ws_manager.py monolithique)
```python
# 750+ lignes dans un seul fichier
class WebSocketManager:
    def __init__(self):
        # ThreadPoolExecutor
        # Callbacks
        # Stratégie
        # Métriques
        # Gestion des connexions
        # ... tout mélangé
```

### Après (modules spécialisés)
```python
# ws/manager.py - Façade simplifiée (~200 lignes)
class WebSocketManager:
    def __init__(self):
        self._connection_pool = WebSocketConnectionPool()
        self._strategy = WebSocketConnectionStrategy()
        self._handlers = WebSocketHandlers()
        # Délégation claire
```

## 📊 Bénéfices

### Lisibilité
- **Avant** : 750+ lignes dans un fichier
- **Après** : 4 modules de ~150-200 lignes chacun
- **Gain** : Code 3x plus lisible

### Maintenabilité
- **Avant** : Responsabilités mélangées
- **Après** : Une responsabilité par module
- **Gain** : Modifications isolées

### Testabilité
- **Avant** : Tests complexes sur un monolithe
- **Après** : Tests unitaires par module
- **Gain** : Tests plus simples et fiables

### Évolutivité
- **Avant** : Difficile d'ajouter de nouvelles fonctionnalités
- **Après** : Extension facile via nouveaux modules
- **Gain** : Architecture extensible

## 🧪 Tests

La refactorisation a été testée pour garantir :
- ✅ Compatibilité avec l'interface existante
- ✅ Fonctionnement des imports
- ✅ Cycle de vie des connexions
- ✅ Gestion des callbacks
- ✅ Métriques et statistiques

## 🚀 Utilisation

L'utilisation reste identique à l'ancienne version :

```python
from ws.manager import WebSocketManager

# Créer le manager
ws_manager = WebSocketManager(testnet=True)

# Configurer les callbacks
ws_manager.set_ticker_callback(lambda data: print(data))

# Démarrer les connexions
await ws_manager.start_connections(
    linear_symbols=["BTCUSDT", "ETHUSDT"],
    inverse_symbols=["BTCUSD"]
)

# Arrêter
await ws_manager.stop()
```

## 🔧 Configuration

### ThreadPoolExecutor
```python
# Dans connection_pool.py
pool.create_executor(max_workers=2, thread_name_prefix="ws_executor")
```

### Stratégie de Connexion
```python
# Dans strategy.py
strategy = strategy.analyze_symbols(linear_symbols, inverse_symbols)
```

### Callbacks
```python
# Dans handlers.py
handlers.set_ticker_callback(callback)
handlers.set_orderbook_callback(callback)
```

## 📈 Métriques

Le module fournit des métriques détaillées :

```python
stats = ws_manager.get_connection_stats()
# {
#     "total_connections": 2,
#     "connected_count": 2,
#     "total_reconnects": 0,
#     "last_error": None,
#     "last_activity": 1234567890.0,
#     "is_active": True
# }
```

## 🎯 Prochaines Étapes

1. **Monitoring** : Surveiller les performances en production
2. **Optimisations** : Ajuster les timeouts et limites
3. **Extensions** : Ajouter de nouvelles fonctionnalités
4. **Tests** : Couvrir plus de cas d'usage

## 📚 Références

- [Architecture des modules Python](https://docs.python.org/3/tutorial/modules.html)
- [ThreadPoolExecutor](https://docs.python.org/3/library/concurrent.futures.html)
- [WebSocket Bybit](https://bybit-exchange.github.io/docs/v5/ws/overview)
