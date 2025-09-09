# Journal de bord — bybit_bot_v0

> Ce fichier documente **ce qui a été fait** (date, but, fichiers modifiés), **pourquoi**, **comment tester**, et **les prochaines étapes**.  
> **Règle d'or :** chaque modification significative ajoute une entrée ci-dessous.

## 🔰 Base initiale (2025-09-06)
**But :** Démarrage propre du projet, config `.env`, logs clairs, appel REST public pour l'heure serveur.  
**Fichiers clés :** `src/main.py`, `src/config.py`, `src/logging_setup.py`, `src/bybit_client.py`  
**Test :** `python src/main.py` → affiche l'heure serveur puis `OK`.  
**Résultat :** ✅ OK

## 🔐 Passage API privée (2025-09-06)
**But :** Lire le solde via Bybit v5 privé (UNIFIED).  
**Fichiers modifiés :** `src/bybit_client.py`, `src/main.py`, `.env`  
**Test :** `python src/main.py` → logs `✅ Solde USDT ...`  
**Résultat :** ✅ OK (equity ≈ walletBalance)

## 🌐 WebSocket publique — connexion (2025-09-06)
**But :** Vérifier ouverture WS publique (sans abonnement), logs + fermeture propre.  
**Fichier :** `src/run_ws_public.py`  
**Test :** `python src/run_ws_public.py`  
**Résultat :** ✅ OK (timeout si idle → normal)

## 🌐 WebSocket privée — auth & stabilité (2025-09-07)
**But :** Connexion, auth WS privée correcte (`"GET/realtime" + expires_ms`), ping/pong, reconnexion.  
**Fichier :** `src/run_ws_private.py`  
**Test :** `python src/run_ws_private.py`  
**Résultat :** ✅ OK (auth OK, souscription confirmée)

## 🧑‍✈️ Orchestrateur (2025-09-07)
**But :** Lancer REST privé + WS publique + WS privée, health-check périodique, arrêt propre.  
**Fichier :** `src/app.py`  
**Test :** `python src/app.py`  
**Résultat :** ✅ OK (CONNECTED sur public & privé)

## [2025-09-07] — Comptage de l'univers perp (linear/inverse)
**But :** Logguer au démarrage le nombre de contrats perp disponibles (USDT + coin-margined) pour informer l'orchestrateur et la stratégie.
**Fichiers modifiés :** src/app.py
**Tests/commandes :** `python src/app.py` → vérifier la présence des 4 logs :
  - "🗺️ Détection de l'univers perp en cours…"
  - "✅ Perp USDT (linear) détectés : X"
  - "✅ Perp coin-margined (inverse) détectés : Y"
  - "📊 Univers perp total : Z"
**Résultat :** ✅ OK

## [2025-09-07] — Système de watchlist avec filtrage par funding et volume
**But :** Créer un système complet de filtrage des contrats perpétuels par funding rate et volume, avec suivi des prix en temps réel.
**Fichiers créés :** 
  - `src/instruments.py` - Récupération des instruments perpétuels
  - `src/filtering.py` - Filtrage par critères (funding, volume)
  - `src/price_store.py` - Stockage des prix en mémoire
  - `src/run_ws_prices.py` - Script principal de suivi des prix
  - `src/watchlist_config.fr.yaml` - Configuration en français
**Fichiers modifiés :** 
  - `src/bybit_client.py` - Ajout de `public_base_url()`
  - `src/app.py` - Intégration du comptage perp au démarrage
**Fonctionnalités :**
  - Filtrage par catégorie (linear/inverse/both)
  - Filtrage par funding rate (min/max)
  - Filtrage par volume 24h minimum
  - Tri par |funding| décroissant
  - Suivi des prix en temps réel via WebSocket
  - Tableau aligné avec mark price, last price, funding %, volume 24h, âge
**Tests/commandes :** 
  - `python src/run_ws_prices.py` → affiche les paires filtrées avec prix temps réel
  - Modifier `src/watchlist_config.fr.yaml` pour ajuster les filtres
**Résultat :** ✅ OK (système complet et fonctionnel)

## [2025-09-08] — Amélioration du système de watchlist : filtres de spread et volume en millions
**But :** Ajouter un filtre de spread (bid/ask) et améliorer la gestion du volume avec un format en millions, plus des logs pédagogiques détaillés.
**Fichiers modifiés :** 
  - `src/config.py` - Ajout des variables d'environnement SPREAD_MAX et VOLUME_MIN_MILLIONS
  - `src/run_ws_prices.py` - Pipeline de filtrage enrichi avec spread et volume en millions
  - `src/watchlist_config.fr.yaml` - Configuration mise à jour avec les nouveaux paramètres
**Nouvelles fonctionnalités :**
  - **Filtre de spread** : Calcul automatique du spread (ask1-bid1)/((ask1+bid1)/2) via API REST
  - **Volume en millions** : Format plus lisible (5.0 = 5M USDT) avec priorité ENV > fichier > ancien format
  - **Gestion d'erreurs robuste** : Récupération des spreads un par un en cas de symboles invalides
  - **Tableau simplifié** : Suppression des colonnes Mark Price, Last Price et Âge (s)
  - **Logs pédagogiques** : Comptes détaillés à chaque étape du filtrage
**Configuration :**
  - Variables d'environnement : `VOLUME_MIN_MILLIONS=5` et `SPREAD_MAX=0.003`
  - Fichier YAML : `volume_min_millions: 5.0` et `spread_max: 0.03`
**Tests/commandes :** 
  - `setx VOLUME_MIN_MILLIONS 5 && setx SPREAD_MAX 0.003`
  - `python src/run_ws_prices.py` → tableau avec colonnes : Symbole | Funding % | Volume (M) | Spread %
**Résultat :** ✅ OK (filtres fonctionnels, tableau optimisé, logs clairs)

## [2025-01-27] — Renommage de l'orchestrateur principal : run_ws_prices.py → bot.py
**But :** Faire de `src/bot.py` l'orchestrateur officiel du bot avec un nom plus classique, sans refactor lourd.
**Fichiers modifiés :** 
  - `src/run_ws_prices.py` → `src/bot.py` (renommé)
  - `src/bot.py` - Ajustement des bandeaux de démarrage
  - `README.md` - Mise à jour des commandes et variables d'environnement
  - `JOURNAL.md` - Documentation du changement
**Décisions/raisons :**
  - Nom plus classique et professionnel pour l'orchestrateur principal
  - Conservation exacte de la logique actuelle (aucun refactor)
  - Mise à jour des libellés : "🚀 Orchestrateur du bot (filters + WebSocket prix)"
  - Message de statut : "🟢 Orchestrateur prêt (WS connectée, flux en cours)"
**Tests/commandes :** 
  - `python src/bot.py` → doit afficher les nouveaux titres et fonctionner identiquement
  - Vérification que `if __name__ == "__main__": main()` est présent
**Résultat :** ✅ OK (renommage réussi, comportement identique, documentation mise à jour)

---

## 🧩 Modèle d'entrée à réutiliser
### [AAAA-MM-JJ] — Titre court de la modification
**But :** (en une phrase, simple)
**Fichiers modifiés :** (liste)
**Décisions/raisons :** (bullets courtes)
**Tests/commandes :** (cmds exactes + résultat attendu)
**Risques/limitations :** (si pertinents)
**Prochaines étapes :** (1–3 bullets max)

---
