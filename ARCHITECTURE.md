# Architecture du Bot Bybit

> **Guide pour comprendre l'organisation du code en 5 minutes** 🎯

Ce document explique la structure du bot, les responsabilités de chaque composant et comment ils interagissent.

## 📐 Vue d'ensemble

Le bot est organisé en **4 couches principales** :

```
┌─────────────────────────────────────────────────────────────────┐
│                     1. ORCHESTRATION                            │
│                         (bot.py)                                │
│  Coordination de haut niveau et cycle de vie du bot            │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   2. DONNÉES     │  │  3. MONITORING   │  │ 4. CONNEXIONS    │
│                  │  │                  │  │                  │
│ - DataManager    │  │ - Monitoring     │  │ - WebSocket      │
│ - Watchlist      │  │ - Display        │  │ - HTTP Client    │
│ - Opportunity    │  │ - Volatility     │  │                  │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

---

## 🎯 Couche 1 : ORCHESTRATION (Cycle de vie)

### `bot.py` - Orchestrateur principal
**Responsabilité** : Point d'entrée et coordination de haut niveau

**Composants** :
- `BotOrchestrator` : Initialise et coordonne tous les managers
- `AsyncBotRunner` : Exécute le bot en mode asynchrone

**Dépendances d'initialisation** :
```
BotOrchestrator
├── BotInitializer      → Crée tous les managers (ligne 65)
├── BotConfigurator     → Charge la config (ligne 66)
├── DataManager         → Gestion des données (ligne 67)
├── BotStarter          → Démarre les composants (ligne 68)
├── BotHealthMonitor    → Surveillance santé (ligne 69)
├── ShutdownManager     → Arrêt propre (ligne 72)
└── ThreadManager       → Gestion threads (ligne 73)
```

**Flux de démarrage** (méthode `start()` lignes 110-163) :
1. Charger et valider la configuration
2. Récupérer les données de marché
3. Configurer les managers
4. Charger les données de la watchlist
5. Afficher le résumé de démarrage
6. Démarrer tous les composants (WebSocket, monitoring, etc.)
7. Maintenir le bot en vie avec la boucle de surveillance

---

## 📊 Couche 2 : DONNÉES (Récupération et filtrage)

### `data_manager.py` (anciennement `unified_data_manager.py`)
**Responsabilité** : Coordination générale des données de marché

**Architecture** :
```
DataManager
├── fetcher    → DataFetcher   (récupération API REST)
├── storage    → DataStorage   (stockage thread-safe)
└── validator  → DataValidator (validation intégrité)
```

**Usage recommandé** :
```python
# Accès DIRECT aux composants (style moderne)
data_manager.fetcher.fetch_funding_map(url, "linear", 10)
data_manager.storage.get_funding_data_object("BTCUSDT")
data_manager.validator.validate_data_integrity(...)

# Méthodes de coordination de haut niveau
data_manager.load_watchlist_data(url, perp_data, wm, vt)
```

**Fichiers associés** :
- `data_fetcher.py` : Récupération des données API (funding, spread)
- `data_storage.py` : Stockage thread-safe avec Value Objects
- `data_validator.py` : Validation de l'intégrité des données

### `watchlist_manager.py`
**Responsabilité** : Construction de la watchlist avec filtres

**Architecture** :
```
WatchlistManager
├── config_manager        → UnifiedConfigManager
├── market_data_fetcher   → DataManager
├── symbol_filter         → SymbolFilter
└── Helpers (watchlist_helpers/)
    ├── WatchlistDataPreparer    → Préparation des données
    ├── WatchlistFilterApplier   → Application des filtres
    └── WatchlistResultBuilder   → Construction des résultats
```

**Flux de construction** (méthode `build_watchlist()`) :
1. Préparer la configuration et récupérer les données de funding
2. Appliquer les filtres (funding, volume, spread, volatilité)
3. Trier par |funding| décroissant
4. Construire les listes finales (linear_symbols, inverse_symbols)

**Fichiers associés** :
- `watchlist_helpers/data_preparer.py` : Préparation et validation
- `watchlist_helpers/filter_applier.py` : Application séquentielle des filtres
- `watchlist_helpers/result_builder.py` : Construction des résultats

### `opportunity_manager.py`
**Responsabilité** : Détection de nouvelles opportunités de trading

**Fonctionnalités** :
- Détecte les symboles qui passent les filtres en temps réel
- Intègre automatiquement les nouvelles opportunités dans la watchlist
- Gère les symboles candidats (proches des critères)

**Callbacks** :
- `on_new_opportunity()` : Appelé quand de nouveaux symboles sont détectés
- `on_candidate_ticker()` : Appelé pour les tickers des candidats

---

## 📡 Couche 3 : MONITORING (Surveillance et affichage)

### `monitoring_manager.py` (anciennement `unified_monitoring_manager.py`)
**Responsabilité** : Surveillance globale du bot

**Composants surveillés** :
- Volatilité des symboles (cache et refresh)
- Opportunités de trading (détection temps réel)
- Santé des composants (threads, WebSocket)
- Métriques de performance

**Threads gérés** :
- Thread de surveillance des opportunités
- Thread de rafraîchissement de la volatilité
- Thread de monitoring des métriques

### `display_manager.py`
**Responsabilité** : Affichage des tableaux de prix en temps réel

**Fonctionnalités** :
- Tableau formaté avec colonnes : Symbole, Funding %, Volume (M), Spread %, Volatilité %, Funding T
- Rafraîchissement périodique (configurable via `DISPLAY_INTERVAL_SECONDS`)
- Formatage des valeurs avec couleurs et emojis

### `volatility_tracker.py`
**Responsabilité** : Gestion de la volatilité 5 minutes

**Architecture** :
```
VolatilityTracker
├── calculator  → VolatilityCalculator  (calculs purs)
├── cache       → VolatilityCache       (cache TTL)
└── scheduler   → VolatilityScheduler   (refresh automatique)
```

**Fonctionnalités** :
- Calcul de volatilité sur 5 bougies de 1 minute
- Cache avec TTL configurable (défaut 120s)
- Rafraîchissement automatique en arrière-plan
- Filtrage par bornes min/max

---

## 🌐 Couche 4 : CONNEXIONS (WebSocket et HTTP)

### `ws_manager.py` (WebSocketManager)
**Responsabilité** : Gestion des connexions WebSocket publiques

**Fonctionnalités** :
- Connexions isolées pour linear et inverse
- Souscription automatique aux tickers
- Reconnexion automatique avec backoff progressif
- Mise à jour du store de prix en temps réel

**Architecture** :
```
WebSocketManager
├── PublicWSClient (linear)   → ws_public.py
├── PublicWSClient (inverse)  → ws_public.py
└── Callbacks
    └── _handle_ticker()  → Met à jour data_manager.storage
```

### `http_client_manager.py`
**Responsabilité** : Gestion des clients HTTP avec rate limiting

**Fonctionnalités** :
- Pool de clients HTTP réutilisables
- Rate limiting automatique (configurable)
- Fermeture propre des connexions
- Support REST API publique et privée

---

## 🔧 Composants utilitaires

### Configuration
- `config_manager.py` (anciennement `config_unified.py`) : Gestion de la configuration
  - Chargement YAML + variables d'environnement
  - Validation des paramètres
  - Hiérarchie : ENV > YAML > défaut

### Cycle de vie
- `shutdown_manager.py` : Arrêt propre de tous les composants
- `thread_manager.py` : Gestion des threads (création, arrêt)
- `callback_manager.py` : Gestion centralisée des callbacks

### Filtrage
- `filters/symbol_filter.py` : Filtres de symboles (funding, volume, temps)
- `filters/base_filter.py` : Interface de base pour les filtres

### Données
- `models/funding_data.py` : Value Object pour les données de funding
- `models/ticker_data.py` : Value Object pour les données de ticker
- `models/symbol_data.py` : Value Object pour les données de symbole

---

## 🔄 Flux de données complet

### 1. Démarrage du bot
```
1. bot.py démarre
   ├─> BotInitializer crée tous les managers
   ├─> BotConfigurator charge parameters.yaml + .env
   ├─> DataManager récupère les données de marché via API REST
   └─> WatchlistManager filtre et construit la watchlist
```

### 2. Récupération des données de marché
```
DataManager.load_watchlist_data()
   ├─> DataFetcher.fetch_funding_map()    → API REST funding
   ├─> DataFetcher.fetch_spread_data()    → API REST tickers
   ├─> VolatilityTracker.compute_batch()  → API REST klines
   └─> DataStorage.set_funding_data_object()  → Stockage
```

### 3. Filtrage de la watchlist
```
WatchlistManager.build_watchlist()
   ├─> WatchlistDataPreparer.prepare_watchlist_data()
   │   └─> Récupère funding_map, perp_data
   ├─> WatchlistFilterApplier.apply_all_filters()
   │   ├─> Filtre par funding (min/max)
   │   ├─> Filtre par volume (min en millions)
   │   ├─> Filtre par spread (max)
   │   ├─> Filtre par volatilité (min/max)
   │   └─> Tri par |funding| décroissant + limite
   └─> WatchlistResultBuilder.build_final_watchlist()
       └─> Retourne (linear_symbols, inverse_symbols, funding_data)
```

### 4. Suivi en temps réel
```
WebSocketManager.start_connections()
   ├─> PublicWSClient (linear) souscrit aux symboles
   ├─> PublicWSClient (inverse) souscrit aux symboles
   └─> Callbacks sur chaque ticker reçu
       ├─> DataManager.storage.update_price_data()
       ├─> DisplayManager rafraîchit le tableau
       └─> OpportunityManager détecte les opportunités
```

### 5. Surveillance continue
```
Boucle principale (bot.py._keep_bot_alive())
   ├─> BotHealthMonitor vérifie les composants
   ├─> MonitoringManager surveille les threads
   ├─> VolatilityTracker rafraîchit le cache
   └─> Attente 1 seconde et répétition
```

---

## 📋 Tableau récapitulatif des managers

| Manager | Fichier | Lignes | Responsabilité | Dépendances |
|---------|---------|--------|----------------|-------------|
| **DataManager** | `data_manager.py` | ~473 | Coordination des données de marché | DataFetcher, DataStorage, DataValidator |
| **WatchlistManager** | `watchlist_manager.py` | ~326 | Construction de la watchlist | DataManager, SymbolFilter, Helpers |
| **OpportunityManager** | `opportunity_manager.py` | ~208 | Détection d'opportunités | DataManager, WatchlistManager |
| **MonitoringManager** | `monitoring_manager.py` | ~626 | Surveillance globale | VolatilityTracker, OpportunityManager |
| **DisplayManager** | `display_manager.py` | ~150 | Affichage des tableaux | DataManager, TableFormatter |
| **VolatilityTracker** | `volatility_tracker.py` | ~200 | Gestion de la volatilité | VolatilityCalculator, Cache, Scheduler |
| **WebSocketManager** | `ws_manager.py` | ~305 | Connexions WebSocket | PublicWSClient, DataManager |
| **ConfigManager** | `config_manager.py` | ~538 | Gestion de la configuration | - |
| **CallbackManager** | `callback_manager.py` | ~100 | Gestion des callbacks | - |
| **ShutdownManager** | `shutdown_manager.py` | ~150 | Arrêt propre | - |
| **ThreadManager** | `thread_manager.py` | ~100 | Gestion des threads | - |
| **HTTPClientManager** | `http_client_manager.py` | ~200 | Clients HTTP | - |

---

## 🎯 Guide pour les développeurs

### "Je veux modifier un filtre"
→ `filters/symbol_filter.py` ou `watchlist_helpers/filter_applier.py`

### "Je veux ajouter une nouvelle donnée de marché"
→ `data_fetcher.py` (récupération) + `data_storage.py` (stockage)

### "Je veux changer l'affichage du tableau"
→ `display_manager.py` + `table_formatter.py`

### "Je veux modifier la logique de volatilité"
→ `volatility.py` (VolatilityCalculator)

### "Je veux ajouter un nouveau WebSocket"
→ `ws_manager.py` + créer un nouveau client dans `ws_public.py` ou `ws_private.py`

### "Je veux changer la configuration"
→ `parameters.yaml` (valeurs par défaut) + `.env` (surcharge)

### "Je veux débugger un problème"
1. Activer `LOG_LEVEL=DEBUG` dans `.env`
2. Consulter `logs/bybit_bot.log`
3. Vérifier les logs de démarrage pour identifier le composant problématique

---

## 🚀 Démarrage rapide pour un nouveau développeur

### 1. Point d'entrée
Commencer par lire `bot.py` (314 lignes) :
- `BotOrchestrator.__init__()` : Initialisation (lignes 52-91)
- `BotOrchestrator.start()` : Séquence de démarrage (lignes 110-163)
- `BotOrchestrator._keep_bot_alive()` : Boucle principale (lignes 165-195)

### 2. Flux des données
Ensuite, suivre le flux dans cet ordre :
1. `data_manager.py` : Comprendre comment les données sont récupérées
2. `watchlist_manager.py` : Comprendre comment la watchlist est construite
3. `ws_manager.py` : Comprendre comment les prix sont suivis en temps réel

### 3. Composants spécialisés
Une fois le flux principal compris, explorer les composants selon les besoins :
- Filtrage : `filters/` et `watchlist_helpers/`
- Volatilité : `volatility_tracker.py` et `volatility.py`
- Monitoring : `monitoring_manager.py` et `display_manager.py`

---

## 📖 Références

- **Documentation technique détaillée** : `src/unified_data_manager_README.md`
- **Historique des changements** : `JOURNAL.md`
- **Guide de contribution** : `CONTRIBUTING.md`
- **Configuration** : `README.md` (section Configuration)

---

**Dernière mise à jour** : 9 octobre 2025
**Auteur** : Documentation générée pour améliorer la lisibilité du code

