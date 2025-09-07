# bybit_bot_v0

Bot de trading automatisé pour Bybit avec WebSocket et API REST.

## 🚀 Démarrage rapide

1. Installer les dépendances : `pip install -r requirements.txt`
2. Configurer `.env` avec vos clés API Bybit
3. Lancer l'orchestrateur : `python src/app.py`

## 📁 Structure du projet

- `src/main.py` - Point d'entrée principal (REST API)
- `src/app.py` - Orchestrateur (REST + WebSockets)
- `src/bybit_client.py` - Client Bybit API
- `src/config.py` - Configuration et variables d'environnement
- `src/logging_setup.py` - Configuration des logs
- `src/run_ws_public.py` - WebSocket publique
- `src/run_ws_private.py` - WebSocket privée

## 🗒️ Journal de bord & Workflow
- Toutes les modifications importantes doivent être **documentées** dans `JOURNAL.md` (voir modèle).
- Avant de merger un changement :
  1. Mettre à jour `JOURNAL.md` (nouvelle entrée).
  2. Supprimer/renommer **tout code devenu inutile**.
  3. Vérifier les logs (simples, compréhensibles).
- Commandes utiles :
  - Démarrer orchestrateur : `python src/app.py`
  - REST privé (solde) : `python src/main.py`
  - WS publique (test de base) : `python src/run_ws_public.py`
  - WS privée (runner) : `python src/run_ws_private.py`
