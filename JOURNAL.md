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
