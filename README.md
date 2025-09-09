# bybit_bot_v0

Bot de trading automatisé pour Bybit avec WebSocket et API REST, incluant un système de watchlist avec filtrage par funding et volume.

## 🚀 Démarrage rapide

1. Installer les dépendances : `pip install -r requirements.txt`
2. Configurer `.env` avec vos clés API Bybit
3. Lancer l'orchestrateur : `python src/bot.py`

## 📊 Système de watchlist avancé

### Suivi des prix en temps réel avec filtrage intelligent
```bash
python src/bot.py
```

### Configuration
#### Fichier YAML (`src/parameters.yaml`)
```yaml
categorie: "linear"      # "linear" | "inverse" | "both"
funding_min: null        # ex: 0.0001 pour >= 0.01%
funding_max: null        # ex: 0.0005 pour <= 0.05%
volume_min: 1000000      # ex: 1000000 pour >= 1M USDT [ANCIEN]
volume_min_millions: 5.0 # ex: 5.0 pour >= 5M USDT [NOUVEAU]
spread_max: 0.03         # ex: 0.03 pour <= 3.0% spread
volatility_min: null     # ex: 0.002 pour >= 0.20% [NOUVEAU]
volatility_max: 0.007    # ex: 0.007 pour <= 0.70% [NOUVEAU]
limite: 10               # ex: 10 symboles max
```

#### Variables d'environnement (priorité maximale)
```bash
# Windows
setx VOLUME_MIN_MILLIONS 5        # min 5M USDT
setx SPREAD_MAX 0.003             # max 0.30% spread
setx VOLATILITY_MIN 0.002         # min 0.20% volatilité 5m
setx VOLATILITY_MAX 0.007         # max 0.70% volatilité 5m
setx FUNDING_MIN 0.0001           # min 0.01% funding
setx FUNDING_MAX 0.0005           # max 0.05% funding
setx CATEGORY linear              # linear | inverse | both
setx LIMIT 10                     # nombre max de symboles

# Linux/Mac
export VOLUME_MIN_MILLIONS=5
export SPREAD_MAX=0.003
export VOLATILITY_MIN=0.002
export VOLATILITY_MAX=0.007
export FUNDING_MIN=0.0001
export FUNDING_MAX=0.0005
export CATEGORY=linear
export LIMIT=10
```

### Fonctionnalités avancées
- ✅ **Filtrage par funding rate** (min/max)
- ✅ **Filtrage par volume 24h** (format millions plus lisible)
- ✅ **Filtrage par spread** (bid/ask)
- ✅ **Filtrage par volatilité 5m** (plage high-low, min/max) - **NOUVEAU**
- ✅ **Tri par |funding| décroissant** (les plus extrêmes en premier)
- ✅ **Suivi des prix en temps réel** via WebSocket
- ✅ **Tableau optimisé** : Symbole | Funding % | Volume (M) | Spread % | Volatilité %
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
🎛️ Filtres | catégorie=linear | volume_min_millions=5.0 | spread_max=0.0030 | volatility_min=0.002 | volatility_max=0.007 | limite=10
🧮 Comptes | avant filtres = 618 | après funding/volume = 42 | après spread = 16 | après volatilité = 12 | après tri+limit = 10
✅ Filtre spread : gardés=16 | rejetés=26 (seuil 0.30%)
✅ Filtre volatilité: gardés=12 | rejetés=4 (seuils: min=0.20% | max=0.70%)
🔎 Volatilité 5m = 0.45% → OK BTCUSDT
⚠️ Volatilité 5m = 1.20% > seuil max 0.70% → rejeté ETHUSDT

Symbole  |    Funding % | Volume (M) |   Spread % | Volatilité %
---------+--------------+------------+-----------+-------------
MYXUSDT  |     -2.0000% |      250.5 |    +0.104% |     +0.450%
REXUSDT  |     +0.4951% |      121.9 |    +0.050% |     +0.320%
OPENUSDT |     -0.2277% |       34.0 |    +0.069% |     +0.180%
```

## 📁 Structure du projet

### Scripts principaux
- `src/bot.py` - **ORCHESTRATEUR PRINCIPAL** : Suivi des prix avec filtrage
- `src/app.py` - Orchestrateur (REST + WebSockets + comptage perp)
- `src/main.py` - Point d'entrée principal (REST API)

### Modules de base
- `src/bybit_client.py` - Client Bybit API
- `src/config.py` - Configuration et variables d'environnement
- `src/logging_setup.py` - Configuration des logs

### Modules de watchlist
- `src/instruments.py` - Récupération des instruments perpétuels
- `src/filtering.py` - Filtrage par critères (funding, volume)
- `src/volatility.py` - Calcul de volatilité 5 minutes
- `src/price_store.py` - Stockage des prix en mémoire
- `src/parameters.yaml` - Configuration des paramètres

### Scripts de test
- `src/run_ws_public.py` - WebSocket publique
- `src/run_ws_private.py` - WebSocket privée

## 🗒️ Journal de bord & Workflow
- Toutes les modifications importantes doivent être **documentées** dans `JOURNAL.md` (voir modèle).
- Avant de merger un changement :
  1. Mettre à jour `JOURNAL.md` (nouvelle entrée).
  2. Supprimer/renommer **tout code devenu inutile**.
  3. Vérifier les logs (simples, compréhensibles).

## 🎯 Commandes utiles
- **Orchestrateur principal** : `python src/bot.py`
- **Orchestrateur complet** : `python src/app.py`
- **REST privé (solde)** : `python src/main.py`
- **WS publique (test)** : `python src/run_ws_public.py`
- **WS privée (test)** : `python src/run_ws_private.py`

## 🔧 Configuration avancée
- **Variables d'environnement** : `VOLUME_MIN_MILLIONS`, `SPREAD_MAX`, `VOLATILITY_MIN`, `VOLATILITY_MAX`
- **Fichier de config** : `src/parameters.yaml`
- **Priorité** : ENV > fichier YAML > valeurs par défaut
