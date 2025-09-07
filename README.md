# bybit_bot_v0

Bot de trading automatisé pour Bybit avec WebSocket et API REST, incluant un système de watchlist avec filtrage par funding et volume.

## 🚀 Démarrage rapide

1. Installer les dépendances : `pip install -r requirements.txt`
2. Configurer `.env` avec vos clés API Bybit
3. Lancer l'orchestrateur : `python src/app.py`

## 📊 Système de watchlist (NOUVEAU)

### Suivi des prix en temps réel avec filtrage
```bash
python src/run_ws_prices.py
```

### Configuration
Éditer `src/watchlist_config.fr.yaml` :
```yaml
categorie: "linear"      # "linear" | "inverse" | "both"
funding_min: null        # ex: 0.0001 pour >= 0.01%
funding_max: null        # ex: 0.0005 pour <= 0.05%
volume_min: 1000000      # ex: 1000000 pour >= 1M USDT
limite: 10               # ex: 10 symboles max
```

### Fonctionnalités
- ✅ **Filtrage par funding rate** (min/max)
- ✅ **Filtrage par volume 24h** (liquidité minimum)
- ✅ **Tri par |funding| décroissant** (les plus extrêmes en premier)
- ✅ **Suivi des prix en temps réel** via WebSocket
- ✅ **Tableau aligné** avec mark price, last price, funding %, volume 24h, âge

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
- **Suivi des prix** : `python src/run_ws_prices.py`
- **Orchestrateur complet** : `python src/app.py`
- **REST privé (solde)** : `python src/main.py`
- **WS publique (test)** : `python src/run_ws_public.py`
- **WS privée (test)** : `python src/run_ws_private.py`
