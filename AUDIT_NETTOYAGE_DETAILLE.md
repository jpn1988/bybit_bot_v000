# Audit de Nettoyage – Bot Bybit

Ce rapport dresse la cartographie actuelle du bot, met en évidence les risques structurels et propose un plan d’action priorisé. Aucun fichier de code n’a été modifié.

## Structure globale

### Orchestration et démarrage
- `src/bot.py` : `BotOrchestrator` coordonne initialisation, configuration, démarrage et arrêt. Il instancie `BotInitializer`, `BotConfigurator`, `BotStarter`, `BotLifecycleManager`, relie `PositionMonitor`, `FundingCloseManager`, `SpotHedgeManager`, `SchedulerManager` et gère l’injection du `BybitClient`.
- `src/bot.py` : `AsyncBotRunner` fournit le point d’entrée CLI, configure le logger, crée un `BotFactory` (mode bundle), installe les signaux d’arrêt et exécute `BotOrchestrator.start()` dans l’event loop.
- `src/factories/bot_factory.py` : fabrique alternative qui pré-construit tous les managers (bundle) pour réduire les coûts d’initialisation et éviter les cycles d’import.

### Initialisation, configuration et lifecycle
- `src/bot_initializer.py` : crée les managers principaux (`DataManager`, `DisplayManager`, `MonitoringManager`, `WebSocketManager`, `VolatilityTracker`, `WatchlistManager`, `CallbackManager`, `OpportunityManager`, `CandidateMonitor`) et fixe les callbacks croisés.
- `src/bot_configurator.py` : charge `parameters.yaml`, récupère les univers perp/spot, configure les managers (catégories, TTL volatilité, intervalle d’affichage).
- `src/bot_starter.py` : lance `VolatilityTracker`, `DisplayManager`, `WebSocketManager`, `MonitoringManager`, vérifie les positions existantes (REST) et active le `CandidateMonitor`.
- `src/bot_lifecycle_manager.py` : regroupe le cycle de vie (tâche périodique de funding, boucle de surveillance toutes les secondes, arrêt centralisé via `ShutdownManager`).
- `src/shutdown_manager.py` : gère signal Ctrl+C, arrêt asynchrone/synchrone des managers, nettoyage mémoire et résumé de shutdown.
- `src/thread_manager.py` : coquille légère qui conserve un logger pour centraliser la gestion de threads (les méthodes lourdes ont été supprimées).

### Données, watchlist et métriques
- `src/data_manager.py` et `src/data_fetcher.py` : chargent la watchlist initiale, gèrent cache et validation, exposent `storage` pour les données temps réel.
- `src/fallback_data_manager.py` : fournit un plan B REST (funding map), appelé par `BotLifecycleManager` toutes les `DEFAULT_FUNDING_UPDATE_INTERVAL` secondes.
- `src/monitoring_manager.py` : chef d’orchestre des scans (marché + candidats) avec `OpportunityManager`, `CandidateMonitor`, `OpportunityScanner` ; maintient la liste des positions actives pour mettre en pause la watchlist.
- `src/bot_health_monitor.py` : suivi d’état des managers et monitoring mémoire (avec `psutil`).
- `src/metrics_monitor.py` : thread périodique pour les métriques (par défaut toutes les 5 minutes).

### WebSockets, positions et événements
- `src/ws/manager.py` : façade sur `WebSocketConnectionPool`, `WebSocketConnectionStrategy` et `WebSocketHandlers`. Gère les connexions publiques, la répartition linear/inverse, les callbacks ticker/orderbook et propose `switch_to_single_symbol` / `restore_full_watchlist`.
- `src/ws/connection_pool.py` : encapsule un `ThreadPoolExecutor` partagé, avec logs d’avertissement si on recrée un executor alors qu’il est actif.
- `src/position_monitor.py` : WebSocket privé (topic `position`), tourne dans un thread dédié, déclenche les callbacks d’ouverture/fermeture.
- `src/position_event_handler.py` : réagit aux événements de `PositionMonitor`, bascule le WebSocket sur le symbole unique, filtre l’affichage, synchronise `SchedulerManager`, `FundingCloseManager`, `SpotHedgeManager`.

### Trading automatique, ordres et hedge
- `src/scheduler_manager.py` : boucle asynchrone (toutes les `scan_interval` secondes) qui lit la watchlist (via callback `FallbackDataManager`), détecte les funding imminents, déclenche le trading via `SmartOrderPlacer` et surveille les ordres par `OrderMonitor`.
- `src/smart_order_placer.py` : pipeline maker (analyse liquidité, calcul prix dynamique, rafraîchissement PostOnly). Utilise `concurrent.futures` pour les appels REST et un cache orderbook TTL.
- `src/order_monitor.py` : surveille les ordres en attente, annule ceux qui dépassent leur timeout et appelle un callback de fallback (market) si nécessaire.
- `src/spot_hedge_manager.py` : gère le hedge spot immédiat, suit les hedges actifs, surveille les timeouts via son propre `OrderMonitor` et déclenche un fallback market.
- `src/funding_close_manager.py` : surveille positions pour fermeture post-funding (thread polling + WebSocket privé). La logique est neutralisée si `auto_close_after_funding=false`, mais les hooks restent actifs.

### Clients Bybit et couches techniques
- `src/bybit_client_backup.py`, `src/bybit_client/__init__.py`, `src/bybit_client/private_client.py` : réexport du client historique (synchrone) en attendant la migration complète vers une version async.
- `src/bybit_client/rate_limiter.py` : applique un rate-limiter async mais avertit (`PERF-002`) quand le client synchrone est appelé depuis l’event loop.
- `src/config` : centralisation des constantes, timeouts, URLs, validation d’environnement.
- `src/parallel_api_manager.py`, `src/async_rate_limiter.py`, `src/volatility_scheduler.py` : gestion des parallélisations et tâches longues (volatilité, appels REST batch).

## Points critiques

### Redondances et chevauchements
- `start_metrics_monitoring()` est déclenché dans `BotOrchestrator.__init__` et de nouveau dans `BotLifecycleManager.start_lifecycle()`. Chaque appel recrée un thread `MetricsMonitor` sans fermer le précédent.
- Trois `OrderMonitor` distincts (`SchedulerManager`, `SpotHedgeManager`, `FundingCloseManager`) exécutent une logique équivalente d’annulation/rappel → coûts CPU supplémentaires, annulations concurrentes possibles et duplication de logs.
- `FundingCloseManager` et `SpotHedgeManager` s’exécutent sur les mêmes événements de positions alors que `SchedulerManager` orchestre déjà ouverture/fermeture. Le flux de clôture est donc fragmenté et difficile à raisonner.
- Mise à jour des données de funding en double : la tâche `_periodic_funding_update()` de `BotLifecycleManager` (5 secondes) et la boucle du `SchedulerManager` (5 secondes) récupèrent chacune les funding rates, en parallèle du flux WebSocket.

### Exécutions multiples et recréations inutiles
- `WebSocketConnectionPool.create_executor()` est rappelé lors de chaque `switch_to_single_symbol` / `restore_full_watchlist`, provoquant l’avertissement « ThreadPoolExecutor déjà créé » et des threads orphelins si le précédent n’est pas complètement stoppé.
- `SmartOrderPlacer.place_order_with_refresh()` instancie un nouveau `ThreadPoolExecutor` pour toutes les opérations (`_get_cached_orderbook`, `_place_order_sync`, retries), créant des threads jetables et des pics CPU.
- `BotLifecycleManager.keep_bot_alive()` loggue chaque seconde l’état de la boucle. Les fichiers de log gonflent rapidement sans information exploitable.
- `CandidateMonitor` est recréé si `MonitoringManager._init_candidate_monitor()` est appelé avant que l’initialisation paresseuse ne soit terminée (risque de duplication en cas de démarrages répétés).

### Logs verbeux ou peu exploitables
- `FundingCloseManager._on_funding_event()` inscrit en `info` chaque payload WebSocket (`data={...}`), ce qui remplit les logs lorsque le topic `position` émet fréquemment.
- Les boucles `keep_bot_alive`, `SchedulerManager.run_with_callback` et `FundingCloseManager._check_positions_periodically` écrivent des messages répétitifs toutes les quelques secondes même sans changement d’état.
- Le warning `PERF-002` du `BybitRateLimiter` apparaît encore lorsque le client synchrone est invoqué depuis des coroutines (voir section async).

### Diagnostic des tâches asynchrones et du client REST
- `SmartOrderPlacer` et `OrderMonitor` utilisent massivement `future.result()` dans le thread appelant. Quand ils sont déclenchés depuis l’event loop (ex. via `asyncio.to_thread` partiel ou appels directs dans le thread principal), l’event loop reste bloqué jusqu’au retour du futur.
- `SchedulerManager._handle_automatic_trading()` déplace une partie de la logique dans `asyncio.to_thread`, mais la récupération d’infos d’instruments (`ThreadPoolExecutor` local + `future.result()`) reste exécutée dans la coroutine → blocage potentiel et création d’un nouvel exécuteur à chaque passage.
- `SpotHedgeManager.on_perp_position_opened()` peut être appelé depuis le thread événementiel (ex. via `PositionEventHandler` dans certains scénarios). Les appels directs à `BybitClient.get_tickers` et `place_order` y sont synchrones et déclenchent le warning PERF-002.
- `OrderMonitor.check_orders_status()` est appelé via `asyncio.to_thread` par le scheduler mais pas par `SpotHedgeManager` ni `FundingCloseManager`, qui l’exécutent dans leurs propres threads sans coordination (risque de contention sur l’API privée).

### Fréquences et cadences
| Composant | Source | Intervalle / déclencheur | Impact actuel | Recommandation |
|-----------|--------|---------------------------|---------------|----------------|
| `BotLifecycleManager._periodic_funding_update` | `bot_lifecycle_manager.py` | 5 s (`DEFAULT_FUNDING_UPDATE_INTERVAL`) | Charge REST constante, redondante avec WebSocket et scheduler | Passer à 30–60 s et conditionner à la disponibilité de données WS |
| `SchedulerManager` | `scheduler_manager.py` | 5 s (`scan_interval`) sur un seul symbole | Opportunités ignorées lorsque plusieurs pairs sont imminentes | Introduire un round-robin ou analyser N symboles / cycle, intervalle ≥10 s |
| `SmartOrderPlacer` | `smart_order_placer.py` | Refresh toutes les 2 s (spot ≈1 s) | Rafales d’annulations/recréations, stress API | Ajuster dynamiquement (3–5 s) avec offsets progressifs |
| `FundingCloseManager._check_positions_periodically` | `funding_close_manager.py` | Boucle 5–15 s | Polling actif alors que `auto_close_after_funding=false` | Suspendre complètement le thread si l’auto-close est désactivée |
| `VolatilityScheduler` | `volatility_scheduler.py` | 20–40 s (selon TTL) | Thread dédié permanent même hors activité | N’exécuter le refresh que si des symboles actifs existent |
| `BotLifecycleManager.keep_bot_alive` | `bot_lifecycle_manager.py` | 1 s | Logs très bavards, aucune temporisation adaptative | Déporter les logs en `debug` conditionnel, porter l’attente à 3–5 s |

### Étude des logs
- **Logs à conserver** : démarrages/arrêts des managers, confirmation des ordres (maker confirmé), résumés d’affichage, alertes `⚡ [SCHEDULER]` lorsqu’une paire devient imminente, résumé `log_shutdown_summary`.
- **Logs à réduire** : boucle `keep_bot_alive`, `🕒 [SCHEDULER]` sans changement d’état, `FundingCloseManager` (positions surveillées à chaque passage), tri des candidats.
- **Logs à supprimer** : payload complet des messages WebSocket dans `FundingCloseManager._on_funding_event`, warnings d’executor déjà créé, répétition `💰 Positions surveillées` lors des callbacks.

### Analyse des gestionnaires (chevauchements)
- `FundingCloseManager` reçoit toujours les callbacks de positions via `PositionEventHandler` même quand `auto_close_after_funding=false`, ce qui maintient des structures internes et du bruit de log. Il devrait être totalement débranché (callbacks non enregistrés, thread non démarré) lorsque l’auto-fermeture est désactivée.
- `SpotHedgeManager` et `SchedulerManager` déclenchent tous deux des ordres PostOnly à partir des mêmes événements. Une répartition claire (scheduler = perp, hedge = spot avec paramètres distincts) éviterait les doubles créations d’ordre et faciliterait le suivi.
- `OrderMonitor` pourrait être partagé entre ces trois gestionnaires pour centraliser l’annulation, limiter la duplication de logique et mutualiser la surveillance des timeouts.
- `MetricsMonitor` est géré comme un service global mais lancé depuis deux endroits ; il devrait être orchestré uniquement par `BotLifecycleManager` et stoppé explicitement dans `ShutdownManager`.

### Paramètres dynamiques à surveiller
- `config/constants.py` : `DEFAULT_FUNDING_UPDATE_INTERVAL=5`, `DEFAULT_MAX_RETRIES=3`, `DEFAULT_ORDER_SIZE_USDT=10`. Exposer ces valeurs dans `parameters.yaml` simplifierait les expérimentations.
- `src/smart_order_placer.py` : `ORDER_REFRESH_INTERVAL=2`, `DEFAULT_MAX_RETRIES_PERP=3`, `DEFAULT_MAX_RETRIES_SPOT=8`, offsets `MAKER_OFFSET_LEVELS`. Revaloriser ces constantes selon la liquidité permettrait d’éviter les rafales d’annulations.
- `src/parameters.yaml` : `funding_threshold_minutes=218`, `auto_trading.order_offset_percent=0.01`, `auto_trading.maker.max_retries_perp=20`. Ces réglages très agressifs amplifient les rafraîchissements maker ; prévoir une plage recommandée (table ci-dessous) et valider à l’aide de métriques.

| Paramètre | Valeur actuelle | Risque | Plage recommandée |
|-----------|-----------------|--------|-------------------|
| `DEFAULT_FUNDING_UPDATE_INTERVAL` | 5 s | Polling REST intensif | 30–60 s conditionnel |
| `ORDER_REFRESH_INTERVAL` | 2 s | Rafales d’annulation | 3–5 s avec offset croissant |
| `auto_trading.maker.max_retries_perp` | 20 | Longs cycles PostOnly | 3–5 tentatives maximum |
| `funding_threshold_minutes` | 218 min (~3h38) | Alerts très tôt ⇒ bruit | 60–90 min |
| `spot_hedge.timeout_minutes` | 30 min | Hedging lent ⇒ exposition | 5–10 min |

### Flux d’ouverture / fermeture d’ordres
- **Ouverture maker** : le scheduler prend la première paire de la watchlist, calcule un prix PostOnly, puis passe la main à `SmartOrderPlacer`. Les symboles suivants attendent le cycle suivant ⇒ risque d’opportunités manquées.
- **Refresh maker** : `_wait_for_execution` annule l’ordre au bout de 2 s et redémarre un cycle complet avec `ThreadPoolExecutor`. Sur marché peu liquide, cela génère un ping-pong permanent.
- **Hedge spot** : `SpotHedgeManager` applique les mêmes offsets que le perp (0.01%). Sur symboles peu liquides, le hedge peut ne jamais se placer → envisager un offset plus large et un fallback join-quote.
- **Fermeture** : `FundingCloseManager` ajoute des symboles à `_monitored_positions` dès que `PositionEventHandler` reçoit l’ouverture, même si l’auto-close est désactivée. Le thread de polling les vérifie ensuite inutilement.
- **Frais taker** : en cas de fallback market (smart placer ou hedge), le code bascule en market immédiatement. Sans suivi global des ordres (perp + spot), il est difficile d’évaluer la proportion maker/taker.

### Synthèse performance (CPU / I/O)
- `SmartOrderPlacer` : création répétée d’exécuteurs, rafraîchissements rapides, multiples appels REST (orderbook + place_order) sur chaque tentative.
- `VolatilityScheduler` : thread daemon permanent, `asyncio` event loop dédié et calculs batch (k-lines) ; lorsque la watchlist est vide il continue néanmoins à s’exécuter.
- `FundingCloseManager._check_positions_periodically` : boucle intense (get_positions, get_open_orders, get_funding_rate) et `time.sleep()` courts. Sur testnet cela sature rapidement le quota.
- `bot_lifecycle_manager.keep_bot_alive` : `asyncio.sleep(1)` + logs d’état ⇒ consommation CPU inutile et bruit.
- `WebSocketManager.switch_to_single_symbol` : `await self.stop()` + recréation d’executor + `asyncio.sleep(0.5)` ; sur ouverture/fermeture fréquentes on observe un churn de threads.

## Recommandations concrètes

### Priorité 🔴 (stabilité immédiate)
- **Désactiver proprement les composants optionnels** : ne connecter `FundingCloseManager` (callbacks + thread) que si `auto_close_after_funding=true`.
- **Centraliser `MetricsMonitor`** : un seul démarrage dans `BotLifecycleManager`, stockage de l’instance dans l’orchestrateur, arrêt orchestré dans `ShutdownManager`.
- **Réduire la fréquence du polling REST** : remonter `DEFAULT_FUNDING_UPDATE_INTERVAL` ≥ 30 s, permettre à la boucle scheduler de traiter plusieurs symboles, augmenter `ORDER_REFRESH_INTERVAL`.
- **Rationaliser les exécuteurs** : partager un `ThreadPoolExecutor` dans `SmartOrderPlacer` (initialisé une fois, fermé par `ShutdownManager`) et supprimer les créations dans chaque retry.
- **Silencer `PERF-002`** : encapsuler toutes les interactions `BybitClient` dans `asyncio.to_thread` ou threads dédiés (scheduler, hedge, monitoring) pour éviter les warnings et bloquages.

### Priorité 🟠 (clarification et lisibilité)
- **Unifier la fermeture des positions** : définir un chemin unique (scheduler décide, funding close facultatif, hedge attaché aux événements) et mettre à jour `PositionEventHandler` en conséquence.
- **Revoir la verbosité des logs** : passer les boucles récurrentes en `debug`, regrouper les logs `FundingCloseManager`, écrire un résumé périodique plutôt qu’un message par tick.
- **Exposez les paramètres clés** : ajouter `funding_threshold_minutes`, `ORDER_REFRESH_INTERVAL`, offsets maker/spot et limites de retry dans `parameters.yaml` avec commentaire sur les plages recommandées.
- **Documenter les dépendances** : produire un diagramme (README ou `docs/`) décrivant le flux `Watchlist -> Scheduler -> SmartOrderPlacer -> PositionMonitor -> EventHandler`, utile pour les futures contributions.

### Priorité 🟢 (optimisations et confort)
- **Optimiser `switch_to_single_symbol`** : mémoriser l’executor existant, ne recréer les connexions que si l’allocation de symboles change réellement.
- **Mettre en place un cache orderbook partagé** : au lieu de recalculer l’orderbook via REST, capitaliser sur les tickers WebSocket et ne rafraîchir que si les données ne sont pas disponibles.
- **Auto-tuning des offsets** : adapter l’offset maker/spot selon la volatilité/spread observé (données déjà disponibles dans `SmartOrderPlacer`).
- **Monitoring enrichi** : utiliser `metrics_monitor` pour suivre la répartition maker/taker, l’évolution des retries et des annulations.

## Estimation de priorité

| Priorité | Sujet | Action principale |
|----------|-------|-------------------|
| 🔴 Urgent | Polling REST et exécuteurs redondants | Espacer les intervalles, mutualiser les `ThreadPoolExecutor`, désactiver les composants inutiles |
| 🔴 Urgent | Gestion `MetricsMonitor` | Un seul démarrage + arrêt garanti via `ShutdownManager` |
| 🔴 Urgent | Flux `FundingCloseManager` / `SpotHedgeManager` | Clarifier les responsabilités, couper les callbacks hors utilisation |
| 🟠 Moyen | Verbosité des logs | Réduire les messages périodiques, conserver uniquement les événements |
| 🟠 Moyen | Paramétrage dynamique | Exposer les constantes critiques dans `parameters.yaml` et documenter les plages |
| 🟢 Optionnel | Optimisations WebSocket | Réduire le churn de threads lors des bascules de symbole |
| 🟢 Optionnel | Cache orderbook | Limiter les appels REST et tirer profit des flux WS |

## Synthèse finale

1. **Stabiliser les composants optionnels** : ne laisser tourner que les gestionnaires réellement nécessaires (metrics, funding close, hedge) et documenter leur rôle.
2. **Réduire la charge API** : espacer les polling, mutualiser les exécuteurs et s’appuyer davantage sur les données WebSocket.
3. **Clarifier le pipeline d’ordres** : définir précisément qui ouvre, hedgé et ferme une position pour éviter les actions concurrentes.
4. **Nettoyer les logs** : concentrer les informations sur les événements clés pour faciliter le diagnostic.
5. **Préparer la configuration** : exposer les réglages critiques et proposer des valeurs cibles pour accélérer le tuning.

L’application de ces recommandations (en commençant par les priorités 🔴) permettra d’améliorer nettement la stabilité, la lisibilité du code et la maîtrise des coûts opérationnels avant toute refactorisation majeure.

