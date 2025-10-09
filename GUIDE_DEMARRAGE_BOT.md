# Guide de démarrage du bot - Flux détaillé

## 🎯 Objectif de ce document

Expliquer **en langage simple** comment le bot démarre, étape par étape, pour que n'importe quel développeur comprenne le flux en 10 minutes.

## 🔍 Le problème du "Manager de Manager"

Le bot utilise 4 fichiers pour orchestrer son démarrage :
- `bot.py` → Orchestrateur principal
- `bot_initializer.py` → Initialise les managers
- `bot_configurator.py` → Configure le bot
- `bot_starter.py` → Démarre les composants

**Pourquoi 4 fichiers ?** Pour respecter le principe de responsabilité unique (SRP) :
- Chaque fichier a UNE responsabilité claire
- Plus facile à tester individuellement
- Plus facile à modifier sans casser le reste

## 📊 Vue d'ensemble simplifiée

```
┌─────────────────────────────────────────────────────────────┐
│                     1. INITIALISATION                       │
│                                                              │
│  BotOrchestrator.__init__()                                 │
│  │                                                           │
│  ├─> BotInitializer                                         │
│  │    └─> Crée tous les managers (data, watchlist, WS...)  │
│  │                                                           │
│  ├─> BotConfigurator                                        │
│  │    └─> Prépare la configuration                          │
│  │                                                           │
│  └─> BotStarter                                             │
│       └─> Prépare le démarrage                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     2. DÉMARRAGE                            │
│                                                              │
│  BotOrchestrator.start()                                    │
│  │                                                           │
│  ├─> 1. BotConfigurator.load_and_validate_config()         │
│  │       └─> Charge parameters.yaml + variables ENV        │
│  │                                                           │
│  ├─> 2. BotConfigurator.get_market_data()                  │
│  │       └─> Récupère les données de marché via API        │
│  │                                                           │
│  ├─> 3. BotConfigurator.configure_managers()               │
│  │       └─> Configure data_manager, watchlist, etc.       │
│  │                                                           │
│  ├─> 4. DataManager.load_watchlist_data()                  │
│  │       └─> Construit la liste des symboles à suivre      │
│  │                                                           │
│  ├─> 5. BotStarter.display_startup_summary()               │
│  │       └─> Affiche le résumé de démarrage                │
│  │                                                           │
│  ├─> 6. BotStarter.start_bot_components()                  │
│  │       └─> Démarre WebSocket, monitoring, affichage      │
│  │                                                           │
│  └─> 7. BotOrchestrator._keep_bot_alive()                  │
│        └─> Boucle principale de surveillance               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     3. SURVEILLANCE                          │
│                                                              │
│  Boucle infinie tant que running = True                     │
│  │                                                           │
│  ├─> BotHealthMonitor.check_components_health()            │
│  │    └─> Vérifie que tous les composants fonctionnent     │
│  │                                                           │
│  ├─> BotHealthMonitor.monitor_memory_usage()               │
│  │    └─> Vérifie la consommation mémoire                  │
│  │                                                           │
│  └─> asyncio.sleep(1.0)                                     │
│       └─> Attendre 1 seconde avant la prochaine itération  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔢 Séquence de démarrage détaillée

### PHASE 1 : Initialisation des composants (dans `__init__`)

#### Étape 1.1 : Création de l'orchestrateur
```python
# bot.py, ligne 52
orchestrator = BotOrchestrator()
```

**Que se passe-t-il ?**
- Crée le logger
- Initialise `running = True`
- Récupère la configuration (testnet ou mainnet)

#### Étape 1.2 : Création des helpers
```python
# bot.py, lignes 65-73
self._initializer = BotInitializer(...)
self._configurator = BotConfigurator(...)
self._data_loader = UnifiedDataManager(...)
self._starter = BotStarter(...)
self._health_monitor = BotHealthMonitor(...)
self._shutdown_manager = ShutdownManager(...)
self._thread_manager = ThreadManager(...)
```

**Pourquoi tant de helpers ?**
- Chaque helper a UNE responsabilité précise
- Plus facile à comprendre qu'un fichier de 1000 lignes
- Plus facile à tester individuellement

#### Étape 1.3 : Initialisation des managers
```python
# bot.py, ligne 76
self._initialize_components()
```

**Que fait cette méthode ?**
```python
# bot.py, lignes 92-108
def _initialize_components(self):
    # 1. Créer tous les managers
    self._initializer.initialize_managers()
    self._initializer.initialize_specialized_managers()
    
    # 2. Configurer les callbacks entre managers
    self._initializer.setup_manager_callbacks()
    
    # 3. Récupérer les références aux managers
    managers = self._initializer.get_managers()
    self.data_manager = managers["data_manager"]
    self.display_manager = managers["display_manager"]
    self.monitoring_manager = managers["monitoring_manager"]
    # ... etc
```

**Résultat** : Tous les managers sont créés et configurés, prêts à être utilisés.

---

### PHASE 2 : Démarrage du bot (méthode `start()`)

#### Étape 2.1 : Chargement de la configuration
```python
# bot.py, ligne 114
config = self._configurator.load_and_validate_config(
    self.watchlist_manager.config_manager
)
```

**Que se passe-t-il ?**
1. Charge `parameters.yaml`
2. Applique les variables d'environnement
3. Valide la cohérence des paramètres
4. Retourne la configuration validée

**Si erreur** → Le bot s'arrête proprement

#### Étape 2.2 : Récupération des données de marché
```python
# bot.py, ligne 122
base_url, perp_data = self._configurator.get_market_data()
```

**Que se passe-t-il ?**
1. Récupère l'URL de l'API (testnet ou mainnet)
2. Récupère la liste de tous les contrats perpétuels via API REST
3. Retourne `base_url` et `perp_data` (dict avec "linear", "inverse", "total")

**Exemple de perp_data** :
```python
{
    "linear": ["BTCUSDT", "ETHUSDT", ...],    # 641 symboles
    "inverse": ["BTCUSD", "ETHUSD", ...],     # 120 symboles
    "total": 761
}
```

#### Étape 2.3 : Configuration des managers
```python
# bot.py, ligne 128
self._configurator.configure_managers(
    config, perp_data, self.data_manager,
    self.volatility_tracker, self.watchlist_manager,
    self.display_manager
)
```

**Que se passe-t-il ?**
1. Configure le `data_manager` avec les catégories de symboles
2. Configure le `volatility_tracker` avec le TTL du cache
3. Configure le `watchlist_manager` avec les paramètres de filtrage
4. Configure le `display_manager` avec l'intervalle d'affichage

#### Étape 2.4 : Construction de la watchlist
```python
# bot.py, ligne 138
if not self._data_loader.load_watchlist_data(
    base_url, perp_data, self.watchlist_manager,
    self.volatility_tracker
):
    return  # Erreur → arrêt propre
```

**Que se passe-t-il ?** (flux complexe, détaillé ci-dessous)
1. Le `WatchlistManager` récupère les données de funding
2. Applique les filtres (funding, volume, spread, volatilité)
3. Trie par |funding| décroissant
4. Limite au nombre max configuré
5. Stocke les résultats dans le `data_manager`

**Résultat** : Liste des symboles à suivre (ex: 10 symboles)

#### Étape 2.5 : Affichage du résumé
```python
# bot.py, ligne 147
self._starter.display_startup_summary(
    config, perp_data, self.data_manager
)
```

**Que se passe-t-il ?**
- Affiche les filtres appliqués
- Affiche le nombre de symboles sélectionnés
- Affiche un résumé des données chargées

#### Étape 2.6 : Démarrage des composants
```python
# bot.py, ligne 152
await self._starter.start_bot_components(
    self.volatility_tracker, self.display_manager,
    self.ws_manager, self.data_manager,
    self.monitoring_manager, base_url, perp_data
)
```

**Que se passe-t-il ?**
1. Démarre le `volatility_tracker` (refresh automatique)
2. Démarre le `display_manager` (affichage du tableau)
3. Démarre le `ws_manager` (connexions WebSocket)
4. Démarre le `monitoring_manager` (surveillance des opportunités)

**Résultat** : Le bot reçoit des données en temps réel via WebSocket

#### Étape 2.7 : Maintien du bot en vie
```python
# bot.py, ligne 163
await self._keep_bot_alive()
```

**Que se passe-t-il ?**
- Boucle infinie qui vérifie la santé des composants
- Vérifie la mémoire toutes les X secondes
- Attendre 1 seconde entre chaque itération

---

### PHASE 3 : Construction de la watchlist (détail)

Cette phase est la plus complexe. Voici le flux détaillé :

```
DataManager.load_watchlist_data()
│
├─> 1. Valider les paramètres d'entrée
│    └─> Vérifie base_url, perp_data, watchlist_manager, volatility_tracker
│
├─> 2. Construire la watchlist
│    │
│    └─> WatchlistManager.build_watchlist()
│         │
│         ├─> 2.1. Préparer les données (WatchlistDataPreparer)
│         │    ├─> Récupérer funding_map via API REST
│         │    │   └─> Appel API : /v5/market/funding/history
│         │    │       Résultat : { "BTCUSDT": {funding, volume, time}, ... }
│         │    │
│         │    └─> Extraire les paramètres de configuration
│         │        └─> funding_min, funding_max, volume_min, spread_max, etc.
│         │
│         ├─> 2.2. Appliquer les filtres (WatchlistFilterApplier)
│         │    │
│         │    ├─> Filtre 1 : Funding + Volume + Temps
│         │    │   └─> Garde les symboles avec :
│         │    │       • funding_min ≤ |funding| ≤ funding_max
│         │    │       • volume ≥ volume_min
│         │    │       • funding_time_min ≤ temps ≤ funding_time_max
│         │    │   Résultat : 42 symboles (exemple)
│         │    │
│         │    ├─> Filtre 2 : Spread
│         │    │   └─> Appel API REST pour chaque symbole
│         │    │       Calcule spread = (ask - bid) / mid
│         │    │       Garde si spread ≤ spread_max
│         │    │   Résultat : 16 symboles
│         │    │
│         │    ├─> Filtre 3 : Volatilité
│         │    │   └─> Calcul asynchrone de la volatilité 5 min
│         │    │       Pour chaque symbole : récupère 5 klines 1min
│         │    │       Calcule volatility = (high - low) / mid
│         │    │       Garde si volatility_min ≤ vol ≤ volatility_max
│         │    │   Résultat : 12 symboles
│         │    │
│         │    └─> Filtre 4 : Tri + Limite
│         │        └─> Trie par |funding| décroissant
│         │            Limite aux X premiers (ex: 10)
│         │        Résultat : 10 symboles
│         │
│         └─> 2.3. Construire les résultats (WatchlistResultBuilder)
│              └─> Sépare en linear_symbols et inverse_symbols
│                  Construit funding_data dict
│                  Retourne (linear_symbols, inverse_symbols, funding_data)
│
├─> 3. Mettre à jour les données dans le storage
│    └─> DataStorage.set_funding_data_object() pour chaque symbole
│
└─> 4. Valider l'intégrité des données
     └─> DataValidator.validate_data_integrity()
```

---

## 🎯 Points clés à retenir

### 1. Séparation des responsabilités

| Fichier | Responsabilité | Quand l'utiliser |
|---------|----------------|------------------|
| `bot.py` | Orchestration globale | Comprendre le flux général |
| `bot_initializer.py` | Créer les managers | Ajouter un nouveau manager |
| `bot_configurator.py` | Charger et valider la config | Modifier les paramètres |
| `bot_starter.py` | Démarrer les composants | Ajouter un nouveau composant à démarrer |

### 2. Ordre de lecture recommandé

Si vous êtes **nouveau sur le projet** :

1. **Commencer par** : `ARCHITECTURE.md`
   - Vue d'ensemble complète
   - Diagrammes clairs
   - 15 minutes de lecture

2. **Ensuite** : `GUIDE_DEMARRAGE_BOT.md` (ce fichier)
   - Comprendre le flux de démarrage
   - Séquence détaillée
   - 10 minutes de lecture

3. **Puis** : `bot.py`
   - Lire les commentaires en haut
   - Suivre la méthode `start()`
   - 20 minutes de lecture

4. **Enfin** : Les autres fichiers selon besoin
   - `bot_initializer.py` si vous voulez ajouter un manager
   - `bot_configurator.py` si vous voulez modifier la config
   - etc.

### 3. Flux simplifié en une phrase

**Le bot charge sa config, récupère les données de marché, filtre les symboles intéressants, se connecte en WebSocket pour suivre les prix en temps réel, et surveille continuellement la santé de ses composants.**

---

## 🔍 FAQ - Questions fréquentes

### Q1 : Pourquoi 4 fichiers au lieu d'un seul ?

**R** : Principe de responsabilité unique (SRP). Chaque fichier a UNE raison de changer :
- `bot.py` → Logique d'orchestration modifiée
- `bot_initializer.py` → Nouveau manager à créer
- `bot_configurator.py` → Nouvelle configuration à charger
- `bot_starter.py` → Nouveau composant à démarrer

**Avantage** : Plus facile à comprendre, tester et maintenir.

### Q2 : Quelle est la différence entre un "manager" et un "helper" ?

**R** :
- **Manager** : Gère des données ou des composants (ex: `data_manager`, `watchlist_manager`)
- **Helper** : Aide l'orchestrateur à faire son travail (ex: `bot_initializer`, `bot_configurator`)

**Analogie** : Les managers sont les employés, les helpers sont les assistants du patron.

### Q3 : Comment ajouter un nouveau manager ?

**R** : Suivre ces étapes :

1. Créer le fichier du manager (ex: `my_manager.py`)
2. Ajouter l'initialisation dans `bot_initializer.py`
3. Récupérer la référence dans `bot.py` (`_initialize_components()`)
4. Utiliser le manager dans `start()` ou ailleurs

### Q4 : Pourquoi tant de logs au démarrage ?

**R** : Pour faciliter le debugging. Chaque étape est loggée pour :
- Voir où le bot en est
- Identifier rapidement les problèmes
- Comprendre ce qui se passe en production

### Q5 : Comment débugger un problème de démarrage ?

**R** :

1. **Activer les logs détaillés** : `LOG_LEVEL=DEBUG` dans `.env`
2. **Regarder les logs** : Le bot affiche chaque étape
3. **Identifier l'étape qui échoue** : Regarder le dernier log avant l'erreur
4. **Consulter ce guide** : Trouver la section correspondante
5. **Lire le code** : Aller dans le fichier identifié

### Q6 : Pourquoi la watchlist prend du temps à se construire ?

**R** : Parce que le bot fait beaucoup d'appels API :

- **Étape 1** : Récupérer les données de funding (641 symboles) → 1 appel API
- **Étape 2** : Récupérer les spreads (42 symboles après filtre 1) → 42 appels API
- **Étape 3** : Calculer les volatilités (16 symboles après filtre 2) → 16×5 = 80 appels API

**Total** : ~120 appels API → prend 5-10 secondes

**Optimisations** :
- Rate limiting pour ne pas être bloqué par l'API
- Parallélisation des appels (semaphore = 5)
- Cache de volatilité (TTL = 120s)

---

## 📚 Documents connexes

- [`ARCHITECTURE.md`](ARCHITECTURE.md) - Vue d'ensemble complète de l'architecture
- [`README.md`](README.md) - Documentation utilisateur et configuration
- [`JOURNAL.md`](JOURNAL.md) - Historique des changements

---

**Dernière mise à jour** : 9 octobre 2025
**Auteur** : Documentation pour améliorer la compréhension du flux de démarrage

