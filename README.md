# bybit_bot_v0

Bot de trading automatisé pour Bybit avec WebSocket et API REST, incluant un système de watchlist avec filtrage par funding et volume.

## 📐 Architecture du projet

**Nouveau développeur ?** Consultez ces guides dans cet ordre :

1. [`GUIDE_DEMARRAGE_BOT.md`](GUIDE_DEMARRAGE_BOT.md) - **Vue d'ensemble** (10 minutes) :
   - 🎯 4 couches principales (Orchestration, Données, Monitoring, Connexions)
   - 📊 Responsabilités de chaque "Manager"
   - 🔄 Flux de données complet
   - 🎯 Guide pratique pour modifier le code

2. [`GUIDE_DEMARRAGE_BOT.md`](GUIDE_DEMARRAGE_BOT.md) - **Flux de démarrage** (10 minutes) :
   - 🔢 Séquence de démarrage détaillée (7 étapes)
   - 📊 Diagrammes de séquence clairs
   - ❓ FAQ : "Pourquoi 4 fichiers ?", "Comment débugger ?", etc.
   - 🎯 Explication du pattern "Manager de Manager"

## 🚀 Démarrage rapide

1. Installer les dépendances : `pip install -r requirements.txt`
2. (Optionnel privé) Créer `.env` avec `BYBIT_API_KEY` et `BYBIT_API_SECRET`
3. Lancer le bot asynchrone : `python src/bot.py`

## 💾 Sauvegarde automatique GitHub

Pour sauvegarder automatiquement vos modifications vers GitHub :

```bash
# Méthode simple (message interactif)
python git_save.py

# Avec message directement
python git_save.py "Votre message de commit"
```

📖 **Guide complet** : Voir [`SAUVEGARDE_GIT.md`](SAUVEGARDE_GIT.md) pour plus de détails

## 📊 Système de watchlist avancé

### Suivi des prix en temps réel avec filtrage intelligent (Architecture asynchrone)
```bash
python src/bot.py
```

### Configuration

> **🎯 HIÉRARCHIE DE CONFIGURATION :**
> 1. **Variables d'environnement** (`.env`) - **PRIORITÉ MAXIMALE**
> 2. **Fichier YAML** (`parameters.yaml`) - **PRIORITÉ MOYENNE**  
> 3. **Valeurs par défaut** (code) - **PRIORITÉ MINIMALE**

#### Fichier YAML (`src/parameters.yaml`) - Configuration par défaut
```yaml
categorie: "linear"            # "linear" | "inverse" | "both"
funding_min: null              # ex: 0.0001 pour >= 0.01%
funding_max: null              # ex: 0.0005 pour <= 0.05%
volume_min: 1000000            # ex: 1000000 pour >= 1M USDT [ANCIEN]
volume_min_millions: 5.0       # ex: 5.0 pour >= 5M USDT [NOUVEAU]
spread_max: 0.003              # ex: 0.003 pour <= 0.30% spread
volatility_min: null           # ex: 0.002 pour >= 0.20% [NOUVEAU]
volatility_max: 0.007          # ex: 0.007 pour <= 0.70% [NOUVEAU]
funding_time_min_minutes: null # ex: 30 pour >= 30 min avant funding [NOUVEAU]
funding_time_max_minutes: null # ex: 120 pour <= 120 min avant funding [NOUVEAU]
volatility_ttl_sec: 120        # TTL du cache volatilité (secondes)
limite: 10                     # ex: 10 symboles max
```

#### Variables d'environnement (.env) - Configuration sensible et spécifique
```bash
# Windows
setx TESTNET true                  # true|false (défaut true)
setx LOG_LEVEL INFO               # DEBUG|INFO|WARNING|ERROR
setx VOLUME_MIN_MILLIONS 5        # min 5M USDT
setx SPREAD_MAX 0.003             # max 0.30% spread
setx VOLATILITY_MIN 0.002         # min 0.20% volatilité 5m
setx VOLATILITY_MAX 0.007         # max 0.70% volatilité 5m
setx FUNDING_MIN 0.0001           # min 0.01% funding
setx FUNDING_MAX 0.0005           # max 0.05% funding
setx FUNDING_TIME_MIN_MINUTES 30  # min minutes avant funding (optionnel)
setx FUNDING_TIME_MAX_MINUTES 120 # max minutes avant funding (optionnel)
setx VOLATILITY_TTL_SEC 120       # TTL du cache volatilité (s)
setx CATEGORY linear              # linear | inverse | both
setx LIMIT 10                     # nombre max de symboles
setx PUBLIC_HTTP_MAX_CALLS_PER_SEC 5  # rate limiter public
setx PUBLIC_HTTP_WINDOW_SECONDS 1     # fenêtre du rate limiter

# Linux/Mac
export TESTNET=true
export LOG_LEVEL=INFO
export VOLUME_MIN_MILLIONS=5
export SPREAD_MAX=0.003
export VOLATILITY_MIN=0.002
export VOLATILITY_MAX=0.007
export FUNDING_MIN=0.0001
export FUNDING_MAX=0.0005
export FUNDING_TIME_MIN_MINUTES=30
export FUNDING_TIME_MAX_MINUTES=120
export VOLATILITY_TTL_SEC=120
export CATEGORY=linear
export LIMIT=10
export PUBLIC_HTTP_MAX_CALLS_PER_SEC=5
export PUBLIC_HTTP_WINDOW_SECONDS=1
```

### Fonctionnalités avancées
- ✅ **Filtrage par funding rate** (min/max)
- ✅ **Filtrage par volume 24h** (format millions plus lisible)
- ✅ **Filtrage par spread** (bid/ask) via REST tickers
- ✅ **Filtre temporel avant funding** (fenêtre min/max en minutes) — NOUVEAU
- ✅ **Filtrage par volatilité 5m** (plage high-low, min/max) — NOUVEAU
- ✅ **Tri par |funding| décroissant** (les plus extrêmes en premier)
- ✅ **Suivi des prix en temps réel** via WebSocket
- ✅ **Tableau optimisé** : Symbole | Funding % | Volume (M) | Spread % | Volatilité % | Funding T
- ✅ **Logs pédagogiques** avec comptes détaillés à chaque étape
- ✅ **Gestion d'erreurs robuste** pour les symboles invalides

### Exemple d'utilisation
```bash
# 1. Configurer les filtres via variables d'environnement
setx VOLUME_MIN_MILLIONS 5
setx SPREAD_MAX 0.003
setx VOLATILITY_MIN 0.002
setx VOLATILITY_MAX 0.007

# 2. Lancer le suivi des prix
python src/bot.py
```

**Résultat attendu :**
```
🎛️ Filtres | catégorie=linear | volume_min_millions=5.0 | spread_max=0.0030 | volatility_min=0.002 | volatility_max=0.007 | ft_min(min)=30 | ft_max(min)=120 | limite=10 | vol_ttl=120s
🧮 Comptes | avant filtres = 618 | après funding/volume/temps = 42 | après spread = 16 | après volatilité = 16 | après tri+limit = 10
✅ Filtre spread : gardés=16 | rejetés=26 (seuil 0.30%)
✅ Calcul volatilité async: gardés=12 | rejetés=4 (seuils: min=0.20% | max=0.70%)

Symbole  |    Funding % | Volume (M) |   Spread % | Volatilité % |    Funding T
---------+--------------+------------+-----------+-------------+--------------
MYXUSDT  |     -2.0000% |      250.5 |    +0.104% |     +0.450% |       1h 12m
REXUSDT  |     +0.4951% |      121.9 |    +0.050% |     +0.320% |          45m
```

## 📁 Structure du projet

> **💡 Pour comprendre l'architecture complète, consultez [`GUIDE_DEMARRAGE_BOT.md`](GUIDE_DEMARRAGE_BOT.md)**

### Scripts principaux
- `src/bot.py` - **ORCHESTRATEUR PRINCIPAL** : Watchlist (REST) + suivi temps réel (WS)
- `src/main.py` - Point d'entrée privé (lecture du solde)

### Initialisation et cycle de vie
- `src/bot_initializer.py` - Création de tous les managers
- `src/bot_configurator.py` - Chargement et validation de la configuration
- `src/bot_starter.py` - Démarrage des composants (WebSocket, monitoring)
- `src/bot_health_monitor.py` - Surveillance de la santé du bot
- `src/shutdown_manager.py` - Arrêt propre de tous les composants
- `src/thread_manager.py` - Gestion des threads

### Gestion des données
- `src/data_manager.py` - Coordinateur des données de marché
- `src/data_fetcher.py` - Récupération des données API (funding, spread)
- `src/data_storage.py` - Stockage thread-safe avec Value Objects
- `src/data_validator.py` - Validation de l'intégrité des données

### Watchlist et filtrage
- `src/watchlist_manager.py` - Construction de la watchlist avec filtres
- `src/watchlist_helpers/data_preparer.py` - Préparation des données
- `src/watchlist_helpers/filter_applier.py` - Application des filtres
- `src/watchlist_helpers/result_builder.py` - Construction des résultats
- `src/filters/symbol_filter.py` - Filtres de symboles (funding, volume, temps)
- `src/filters/base_filter.py` - Interface de base pour les filtres

### Monitoring et opportunités
- `src/monitoring_manager.py` - Coordination de la surveillance
- `src/opportunity_manager.py` - Détection d'opportunités de trading
- `src/display_manager.py` - Affichage des tableaux en temps réel
- `src/table_formatter.py` - Formatage des tableaux
- `src/callback_manager.py` - Gestion centralisée des callbacks

### Volatilité
- `src/volatility_tracker.py` - Gestion de la volatilité 5 minutes
- `src/volatility.py` - Calcul de volatilité (VolatilityCalculator)
- `src/volatility_cache.py` - Cache avec TTL
- `src/volatility_scheduler.py` - Rafraîchissement automatique
- `src/volatility_computer.py` - Calculs optimisés
- `src/volatility_filter.py` - Filtrage par volatilité

### Connexions WebSocket et HTTP
- `src/ws_manager.py` - Gestion des connexions WebSocket
- `src/ws_public.py` - Client WebSocket public
- `src/ws_private.py` - Client WebSocket privé
- `src/http_client_manager.py` - Pool de clients HTTP avec rate limiting
- `src/http_utils.py` - Utilitaires HTTP

### Configuration et base
- `src/config/manager.py` - Gestion de la configuration (YAML + ENV)
- `src/config/settings_loader.py` - Chargement des paramètres
- `src/config/env_validator.py` - Validation des variables d'environnement
- `src/config/config_validator.py` - Validation de la configuration
- `src/config/constants.py` - Constantes globales
- `src/parameters.yaml` - **Configuration par défaut** (filtres, limites)
- `src/logging_setup.py` - Configuration des logs
- `src/bybit_client.py` - Client Bybit API
- `src/instruments.py` - Récupération des instruments perpétuels

### Value Objects (modèles de données)
- `src/models/funding_data.py` - Données de funding validées
- `src/models/ticker_data.py` - Données de ticker validées
- `src/models/symbol_data.py` - Données de symbole validées

### Utilitaires
- `src/metrics.py` - Métriques de performance
- `src/metrics_monitor.py` - Monitoring des métriques
- `src/error_handler.py` - Gestion centralisée des erreurs
- `src/pagination_handler.py` - Gestion de la pagination API

## 🗒️ Workflow de développement
- Toutes les modifications importantes doivent être **documentées** avec des messages de commit clairs.
- Avant de merger un changement :
  1. Tester les fonctionnalités modifiées.
  2. Supprimer/renommer **tout code devenu inutile**.
  3. Vérifier les logs (simples, compréhensibles).

## 🎯 Commandes utiles
- **Orchestrateur principal (watchlist + WS)** : `python src/bot.py`
- **REST privé (solde)** : `python src/main.py`

## 🔧 Configuration avancée
- **Variables d'environnement clés** : `TESTNET`, `TIMEOUT`, `LOG_LEVEL`, `VOLUME_MIN_MILLIONS`, `SPREAD_MAX`, `VOLATILITY_MIN`, `VOLATILITY_MAX`, `FUNDING_MIN`, `FUNDING_MAX`, `FUNDING_TIME_MIN_MINUTES`, `FUNDING_TIME_MAX_MINUTES`, `VOLATILITY_TTL_SEC`, `CATEGORY`, `LIMIT`, `PUBLIC_HTTP_MAX_CALLS_PER_SEC`, `PUBLIC_HTTP_WINDOW_SECONDS`
- **Clés privées (.env)** : `BYBIT_API_KEY`, `BYBIT_API_SECRET` (requis pour `src/main.py`)
- **Fichier de config** : `src/parameters.yaml`
- **Priorité** : ENV > fichier YAML > valeurs par défaut
