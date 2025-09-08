# bybit_bot_v0

Bot de trading automatisé pour Bybit avec WebSocket et API REST, incluant un système de watchlist avec filtrage par funding et volume.

## 🚀 Démarrage rapide

1. Installer les dépendances : `pip install -r requirements.txt`
2. Configurer `.env` avec vos clés API Bybit
3. Lancer l'orchestrateur : `python src/app.py`

## 📊 Système de watchlist avancé

### Suivi des prix en temps réel avec filtrage intelligent
```bash
python src/run_ws_prices.py
```

### Configuration
#### Fichier YAML (`src/watchlist_config.fr.yaml`)
```yaml
categorie: "linear"      # "linear" | "inverse" | "both"
funding_min: null        # ex: 0.0001 pour >= 0.01%
funding_max: null        # ex: 0.0005 pour <= 0.05%
volume_min: 1000000      # ex: 1000000 pour >= 1M USDT [ANCIEN]
volume_min_millions: 5.0 # ex: 5.0 pour >= 5M USDT [NOUVEAU]
spread_max: 0.03         # ex: 0.03 pour <= 3.0% spread [NOUVEAU]
limite: 10               # ex: 10 symboles max
```

#### Variables d'environnement (priorité maximale)
```bash
# Windows
setx VOLUME_MIN_MILLIONS 5        # min 5M USDT
setx SPREAD_MAX 0.003             # max 0.30% spread

# Linux/Mac
export VOLUME_MIN_MILLIONS=5
export SPREAD_MAX=0.003
```

### Fonctionnalités avancées
- ✅ **Filtrage par funding rate** (min/max)
- ✅ **Filtrage par volume 24h** (format millions plus lisible)
- ✅ **Filtrage par spread** (bid/ask) - **NOUVEAU**
- ✅ **Tri par |funding| décroissant** (les plus extrêmes en premier)
- ✅ **Suivi des prix en temps réel** via WebSocket
- ✅ **Tableau optimisé** : Symbole | Funding % | Volume (M) | Spread %
- ✅ **Logs pédagogiques** avec comptes détaillés à chaque étape
- ✅ **Gestion d'erreurs robuste** pour les symboles invalides

### Exemple d'utilisation
```bash
# 1. Configurer les filtres via variables d'environnement
setx VOLUME_MIN_MILLIONS 5
setx SPREAD_MAX 0.003

# 2. Lancer le suivi des prix
python src/run_ws_prices.py
```

**Résultat attendu :**
```
🎛️ Filtres | catégorie=linear | volume_min_millions=5.0 | spread_max=0.0030 | limite=10
🧮 Comptes | avant filtres = 618 | après funding/volume = 42 | après spread = 16 | après tri+limit = 10
✅ Filtre spread : gardés=16 | rejetés=26 (seuil 0.30%)

Symbole  |    Funding % | Volume (M) |   Spread %
---------+--------------+------------+-----------
MYXUSDT  |     -2.0000% |      250.5 |    +0.104%
REXUSDT  |     +0.4951% |      121.9 |    +0.050%
OPENUSDT |     -0.2277% |       34.0 |    +0.069%
```

## 📁 Structure du projet

### Scripts principaux
- `src/app.py` - Orchestrateur (REST + WebSockets + comptage perp)
- `src/run_ws_prices.py` - **NOUVEAU** : Suivi des prix avec filtrage
- `src/main.py` - Point d'entrée principal (REST API)

### Modules de base
- `src/bybit_client.py` - Client Bybit API
- `src/config.py` - Configuration et variables d'environnement
- `src/logging_setup.py` - Configuration des logs

### Modules de watchlist
- `src/instruments.py` - Récupération des instruments perpétuels
- `src/filtering.py` - Filtrage par critères (funding, volume)
- `src/price_store.py` - Stockage des prix en mémoire
- `src/watchlist_config.fr.yaml` - Configuration en français

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
- **Suivi des prix avec filtres** : `python src/run_ws_prices.py`
- **Orchestrateur complet** : `python src/app.py`
- **REST privé (solde)** : `python src/main.py`
- **WS publique (test)** : `python src/run_ws_public.py`
- **WS privée (test)** : `python src/run_ws_private.py`

## 🔧 Configuration avancée
- **Variables d'environnement** : `VOLUME_MIN_MILLIONS`, `SPREAD_MAX`
- **Fichier de config** : `src/watchlist_config.fr.yaml`
- **Priorité** : ENV > fichier YAML > valeurs par défaut
