#!/usr/bin/env python3
"""
Gestionnaire WebSocket pour les connexions publiques Bybit avec gestion multi-thread.

╔═══════════════════════════════════════════════════════════════════╗
║                    📖 GUIDE DE LECTURE                            ║
╚═══════════════════════════════════════════════════════════════════╝

Ce fichier implémente un gestionnaire WebSocket qui peut gérer plusieurs
connexions simultanées (linear + inverse) en utilisant des threads séparés.

🔍 COMPRENDRE CE FICHIER EN 5 MINUTES :

1. ThreadPoolExecutor (lignes 59-62)
   └─> Gère 2 threads max pour les connexions WebSocket

2. Démarrage des connexions (lignes 80-116)
   └─> Décide du nombre de connexions (1 ou 2) selon les symboles

3. Gestion des threads (lignes 145-180)
   └─> Exécution des WebSockets dans des threads séparés

4. Arrêt propre (lignes 196-238)
   └─> Fermeture coordonnée de toutes les connexions

🧵 ARCHITECTURE DES THREADS :

Le WebSocketManager utilise un ThreadPoolExecutor pour exécuter les connexions
WebSocket dans des threads séparés. Cela permet de :
- ✅ Gérer plusieurs connexions simultanément (linear + inverse)
- ✅ Éviter que le blocage d'une connexion affecte l'autre
- ✅ Faciliter l'arrêt propre de toutes les connexions

Structure :
    Thread Principal (Bot)
        │
        ├─> Thread 1 (LinearWebSocket) ──> PublicWSClient("linear")
        │                                   └─> [BTCUSDT, ETHUSDT, ...]
        │
        └─> Thread 2 (InverseWebSocket) ──> PublicWSClient("inverse")
                                            └─> [BTCUSD, ETHUSD, ...]

🔄 STRATÉGIE DE CONNEXION :

Le manager choisit automatiquement la stratégie selon les symboles fournis :

Cas 1 : Symboles linear ET inverse
    → 2 connexions (1 thread pour linear, 1 thread pour inverse)
    
Cas 2 : Symboles linear uniquement
    → 1 connexion (thread linear seulement)
    
Cas 3 : Symboles inverse uniquement
    → 1 connexion (thread inverse seulement)

Pourquoi séparer linear et inverse ?
- ✅ Les endpoints WebSocket sont différents
- ✅ Résilience : Si linear déconnecte, inverse continue
- ✅ Performance : Répartition de la charge

⚡ ThreadPoolExecutor vs asyncio :

Bien que ce fichier utilise asyncio, les WebSockets sont exécutées dans
des threads via ThreadPoolExecutor car :
- websocket-client est bloquant (run_forever())
- asyncio ne peut pas gérer les opérations bloquantes directement
- Solution : loop.run_in_executor() pour exécuter dans un thread

Flux :
1. asyncio event loop (thread principal)
2. loop.run_in_executor() → délègue à ThreadPoolExecutor
3. Thread worker → exécute PublicWSClient.run()
4. PublicWSClient.run() bloque jusqu'à arrêt ou erreur

📚 EXEMPLE D'UTILISATION :

```python
from ws_manager import WebSocketManager

# Créer le manager
ws_manager = WebSocketManager(testnet=True)

# Définir le callback
def on_ticker(data):
    print(f"{data['symbol']}: ${data['lastPrice']}")

ws_manager.set_ticker_callback(on_ticker)

# Démarrer les connexions
await ws_manager.start_connections(
    linear_symbols=["BTCUSDT", "ETHUSDT"],
    inverse_symbols=["BTCUSD"]
)

# Attendre...
await asyncio.sleep(60)

# Arrêter proprement
await ws_manager.stop_connections()
```

🛑 ARRÊT PROPRE :

L'arrêt propre est critique pour éviter les fuites de threads :
1. Marquer running=False
2. Appeler close() sur chaque PublicWSClient
3. Attendre les threads avec timeout (5s)
4. Shutdown du ThreadPoolExecutor
5. Nettoyer les callbacks pour libérer la mémoire

📖 RÉFÉRENCES :
- concurrent.futures: https://docs.python.org/3/library/concurrent.futures.html
- asyncio.run_in_executor: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.run_in_executor
"""

import asyncio
import concurrent.futures
import time
from typing import List, Callable, Optional, TYPE_CHECKING, Dict, Any
from logging_setup import setup_logging
from ws_public import PublicWSClient
from config.timeouts import TimeoutConfig
from interfaces.websocket_manager_interface import WebSocketManagerInterface

if TYPE_CHECKING:
    from data_manager import DataManager


class WebSocketManager(WebSocketManagerInterface):
    """
    Gestionnaire WebSocket pour les connexions publiques Bybit avec gestion multi-thread.
    
    Ce gestionnaire orchestre plusieurs connexions WebSocket (linear/inverse) en
    utilisant un ThreadPoolExecutor pour exécuter chaque connexion dans un thread séparé.
    
    Architecture :
    - 1 ThreadPoolExecutor avec max 2 workers
    - 1 thread par catégorie (linear et/ou inverse)
    - Callbacks asynchrones pour les données reçues
    
    Responsabilités :
    - Créer et gérer les connexions WebSocket publiques
    - Exécuter les WebSockets dans des threads séparés
    - Router les données reçues vers les callbacks
    - Gérer l'arrêt propre de toutes les connexions
    
    Attributes:
        testnet (bool): Utiliser le testnet (True) ou mainnet (False)
        data_manager (DataManager): Instance du gestionnaire de données
        logger: Logger pour les messages
        running (bool): État du gestionnaire (True = actif)
        _executor (ThreadPoolExecutor): Pool de threads pour les WebSockets
        _ws_conns (List[PublicWSClient]): Liste des clients WebSocket actifs
        
    Example:
        ```python
        # Créer et démarrer le manager
        ws_manager = WebSocketManager(testnet=True)
        ws_manager.set_ticker_callback(lambda data: print(data))
        
        await ws_manager.start_connections(
            linear_symbols=["BTCUSDT"],
            inverse_symbols=[]
        )
        ```
        
    Note:
        - Le ThreadPoolExecutor est créé au __init__ et réutilisé
        - Chaque connexion WebSocket bloque son thread avec run_forever()
        - L'arrêt propre est essentiel pour éviter les fuites de threads
    """

    def __init__(
        self, testnet: bool = True, data_manager: Optional["DataManager"] = None, logger=None
    ):
        """
        Initialise le gestionnaire WebSocket avec ThreadPoolExecutor.
        
        Cette méthode crée un ThreadPoolExecutor dédié qui sera utilisé
        pour exécuter les connexions WebSocket dans des threads séparés.

        Args:
            testnet (bool): Environnement à utiliser
                          - True : Testnet (api-testnet.bybit.com)
                          - False : Mainnet (api.bybit.com)
            data_manager (DataManager): Instance du gestionnaire de données
                                       Utilisé pour stocker les prix reçus
            logger: Logger pour tracer les événements
                   Recommandé : logging.getLogger(__name__)
                   
        Note:
            - Le ThreadPoolExecutor est créé ici (pas à chaque start)
            - max_workers=2 car on ne gère que 2 catégories max (linear + inverse)
            - thread_name_prefix aide au debugging (voir les threads dans htop/ps)
        """
        self.testnet = testnet
        self.data_manager = data_manager
        self.logger = logger or setup_logging()
        self.running = False

        # Connexions WebSocket actives
        # Liste des clients WebSocket (PublicWSClient) créés et démarrés
        self._ws_conns: List[PublicWSClient] = []
        
        # Tâches asyncio (futures retournées par run_in_executor)
        # Ces tasks représentent l'exécution des WebSockets dans les threads
        self._ws_tasks: List[asyncio.Task] = []

        # ThreadPoolExecutor dédié pour exécuter les WebSockets dans des threads
        # POURQUOI UN THREADPOOLEXECUTOR ?
        # - PublicWSClient.run() est bloquant (run_forever())
        # - asyncio ne peut pas gérer les opérations bloquantes directement
        # - Solution : exécuter chaque WebSocket dans un thread worker séparé
        # 
        # CONFIGURATION :
        # - max_workers=2 : Maximum 2 threads simultanés (1 linear + 1 inverse)
        # - thread_name_prefix : Préfixe pour identifier les threads (debugging)
        #
        # CYCLE DE VIE :
        # - Créé au __init__ (une seule fois)
        # - Réutilisé pour chaque start_connections()
        # - Fermé au stop_connections() avec shutdown()
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=2,  # Max 2 connexions (linear + inverse)
            thread_name_prefix="ws_executor"  # Préfixe des threads
        )

        # Callbacks
        self._ticker_callback: Optional[Callable] = None

        # Symboles par catégorie
        self.linear_symbols: List[str] = []
        self.inverse_symbols: List[str] = []

    def set_ticker_callback(self, callback: Callable[[dict], None]):
        """
        Définit le callback à appeler lors de la réception de données ticker.

        Args:
            callback: Fonction à appeler avec les données ticker reçues
        """
        self._ticker_callback = callback

    async def start_connections(
        self,
        linear_symbols: List[str],
        inverse_symbols: List[str],
        on_ticker_callback: Optional[Callable] = None,
        on_orderbook_callback: Optional[Callable] = None
    ):
        """
        Démarre les connexions WebSocket pour les symboles donnés.

        Args:
            linear_symbols: Liste des symboles linear à suivre
            inverse_symbols: Liste des symboles inverse à suivre
        """
        if self.running:
            self.logger.warning(
                "⚠️ WebSocketManager déjà en cours d'exécution"
            )
            return

        self.linear_symbols = linear_symbols or []
        self.inverse_symbols = inverse_symbols or []
        self.running = True

        # Déterminer le type de connexions nécessaires
        if self.linear_symbols and self.inverse_symbols:
            # Démarrage des connexions WebSocket
            await self._start_dual_connections()
        elif self.linear_symbols:
            # Démarrage de la connexion WebSocket linear
            await self._start_single_connection("linear", self.linear_symbols)
        elif self.inverse_symbols:
            # Démarrage de la connexion WebSocket inverse
            await self._start_single_connection(
                "inverse", self.inverse_symbols
            )
        else:
            self.logger.warning(
                "⚠️ Aucun symbole fourni pour les connexions WebSocket"
            )

    def _handle_ticker(self, ticker_data: dict):
        """
        Gestionnaire interne pour les données ticker reçues.
        Met à jour le store de prix et appelle le callback externe.

        Args:
            ticker_data: Données ticker reçues via WebSocket
        """
        try:
            # Mettre à jour le store de prix via le data_manager injecté
            symbol = ticker_data.get("symbol", "")
            mark_price = ticker_data.get("markPrice")
            last_price = ticker_data.get("lastPrice")

            if symbol and mark_price is not None and last_price is not None and self.data_manager:
                mark_val = float(mark_price)
                last_val = float(last_price)
                self.data_manager.storage.update_price_data(symbol, mark_val, last_val, time.time())

            # Appeler le callback externe si défini
            if self._ticker_callback and symbol:
                self._ticker_callback(ticker_data)

        except Exception as e:
            self.logger.warning(f"⚠️ Erreur traitement ticker WebSocket: {e}")

    async def _start_single_connection(
        self, category: str, symbols: List[str]
    ):
        """
        Démarre une connexion WebSocket pour une seule catégorie.

        Args:
            category: Catégorie ("linear" ou "inverse")
            symbols: Liste des symboles à suivre
        """
        conn = PublicWSClient(
            category=category,
            symbols=symbols,
            testnet=self.testnet,
            logger=self.logger,
            on_ticker_callback=self._handle_ticker,
        )
        self._ws_conns = [conn]

        # Lancer la connexion dans une tâche asynchrone
        task = asyncio.create_task(self._run_websocket_connection(conn))
        self._ws_tasks = [task]

    async def _start_dual_connections(self):
        """
        Démarre deux connexions WebSocket isolées (linear et inverse).
        """
        # Créer les connexions isolées
        linear_conn = PublicWSClient(
            category="linear",
            symbols=self.linear_symbols,
            testnet=self.testnet,
            logger=self.logger,
            on_ticker_callback=self._handle_ticker,
        )
        inverse_conn = PublicWSClient(
            category="inverse",
            symbols=self.inverse_symbols,
            testnet=self.testnet,
            logger=self.logger,
            on_ticker_callback=self._handle_ticker,
        )

        self._ws_conns = [linear_conn, inverse_conn]

        # Lancer en parallèle dans des tâches asynchrones
        linear_task = asyncio.create_task(
            self._run_websocket_connection(linear_conn)
        )
        inverse_task = asyncio.create_task(
            self._run_websocket_connection(inverse_conn)
        )

        self._ws_tasks = [linear_task, inverse_task]

    async def _run_websocket_connection(self, conn: PublicWSClient):
        """
        Exécute une connexion WebSocket de manière asynchrone.

        Args:
            conn: Connexion WebSocket à exécuter
        """
        try:
            # Exécuter la connexion dans un thread séparé pour éviter de
            # bloquer l'event loop
            # CORRECTIF : Utiliser l'executor dédié au lieu de l'executor par défaut
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self._executor, conn.run)
        except Exception as e:
            if self.running:
                self.logger.warning(f"⚠️ Erreur connexion WebSocket: {e}")

    async def stop_connections(self) -> None:
        """
        Arrête toutes les connexions WebSocket (interface).
        """
        await self.stop()
    
    async def stop(self):
        """
        Arrête toutes les connexions WebSocket.
        """
        if not self.running:
            return

        # Arrêt des connexions WebSocket
        self.running = False

        # Nettoyer les callbacks pour éviter les fuites mémoire
        self._ticker_callback = None

        # Fermer toutes les connexions
        for conn in self._ws_conns:
            try:
                conn.close()
                # Attendre un peu pour que la fermeture se propage (asyncio-friendly)
                await asyncio.sleep(0.1)
            except Exception as e:
                self.logger.warning(
                    f"⚠️ Erreur fermeture connexion WebSocket: {e}"
                )

        # Annuler toutes les tâches asynchrones avec timeout
        for i, task in enumerate(self._ws_tasks):
            if not task.done():
                try:
                    task.cancel()
                    # Attendre l'annulation avec timeout
                    try:
                        await asyncio.wait_for(
                            task, timeout=TimeoutConfig.ASYNC_TASK_SHUTDOWN
                        )
                    except asyncio.TimeoutError:
                        self.logger.warning(
                            f"⚠️ Tâche WebSocket {i} n'a pas pu être "
                            f"annulée dans les temps"
                        )
                    except asyncio.CancelledError:
                        pass  # Annulation normale
                except Exception as e:
                    self.logger.warning(
                        f"⚠️ Erreur annulation tâche WebSocket {i}: {e}"
                    )

        # CORRECTIF ARCH-002: Shutdown avec timeout global forcé
        try:
            import threading
            import time
            
            # Timeout global d'arrêt (10 secondes max pour tout arrêter)
            GLOBAL_SHUTDOWN_TIMEOUT = 10
            start_time = time.time()
            
            # Shutdown avec wait=False pour éviter blocage
            self._executor.shutdown(wait=False)
            
            # Trouver et attendre les threads du pool
            ws_threads = [
                t for t in threading.enumerate() 
                if t.name.startswith("ws_executor")
            ]
            
            # Attendre les threads avec timeout global
            for thread in ws_threads:
                remaining = GLOBAL_SHUTDOWN_TIMEOUT - (time.time() - start_time)
                if remaining <= 0:
                    alive_count = len([t for t in ws_threads if t.is_alive()])
                    self.logger.error(f"⏱️ Timeout global atteint, {alive_count} threads orphelins")
                    break
                    
                thread.join(timeout=remaining)
                if thread.is_alive():
                    self.logger.warning(f"⚠️ Thread {thread.name} ne répond pas, abandonné")
            
            elapsed = time.time() - start_time
            if elapsed < GLOBAL_SHUTDOWN_TIMEOUT:
                self.logger.debug(f"✅ ThreadPoolExecutor arrêté proprement en {elapsed:.2f}s")
            else:
                self.logger.warning(f"⚠️ Arrêt ThreadPoolExecutor forcé après timeout {GLOBAL_SHUTDOWN_TIMEOUT}s")
                
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur arrêt executor: {e}")

        # Nettoyer les listes et références
        self._ws_conns.clear()
        self._ws_tasks.clear()
        self.linear_symbols.clear()
        self.inverse_symbols.clear()

    def stop_sync(self):
        """
        Arrête les connexions WebSocket de manière synchrone.
        """
        if not self.running:
            return

        self.running = False
        self._ticker_callback = None

        # Fermer toutes les connexions de manière synchrone
        for conn in self._ws_conns:
            try:
                conn.close()
                from config.timeouts import TimeoutConfig
                time.sleep(TimeoutConfig.SHORT_SLEEP)
            except Exception as e:
                self.logger.warning(
                    f"⚠️ Erreur fermeture connexion WebSocket: {e}"
                )

        # CORRECTIF ARCH-002: Shutdown avec timeout global forcé (mode synchrone)
        try:
            import threading
            import time
            
            # Timeout global d'arrêt (10 secondes max pour tout arrêter)
            GLOBAL_SHUTDOWN_TIMEOUT = 10
            start_time = time.time()
            
            # Shutdown avec wait=False pour éviter blocage infini
            self._executor.shutdown(wait=False)
            
            # Trouver et attendre les threads du pool
            ws_threads = [
                t for t in threading.enumerate() 
                if t.name.startswith("ws_executor")
            ]
            
            # Attendre les threads avec timeout global
            for thread in ws_threads:
                remaining = GLOBAL_SHUTDOWN_TIMEOUT - (time.time() - start_time)
                if remaining <= 0:
                    alive_count = len([t for t in ws_threads if t.is_alive()])
                    self.logger.error(f"⏱️ Timeout global atteint, {alive_count} threads orphelins")
                    break
                    
                thread.join(timeout=remaining)
                if thread.is_alive():
                    self.logger.warning(f"⚠️ Thread {thread.name} ne répond pas, abandonné")
            
            elapsed = time.time() - start_time
            if elapsed < GLOBAL_SHUTDOWN_TIMEOUT:
                self.logger.debug(f"✅ ThreadPoolExecutor arrêté proprement en {elapsed:.2f}s")
            else:
                self.logger.warning(f"⚠️ Arrêt ThreadPoolExecutor forcé après timeout {GLOBAL_SHUTDOWN_TIMEOUT}s")
                
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur arrêt executor: {e}")
            # Fallback: shutdown forcé en cas d'erreur
            try:
                self._executor.shutdown(wait=False)
            except Exception:
                pass

        # Nettoyer les références
        self._ws_conns.clear()
        self._ws_tasks.clear()
        self.linear_symbols.clear()
        self.inverse_symbols.clear()

    def is_running(self) -> bool:
        """
        Vérifie si le gestionnaire WebSocket est en cours d'exécution.

        Returns:
            bool: True si en cours d'exécution
        """
        return self.running

    def get_connected_symbols(self) -> dict:
        """
        Retourne les symboles actuellement connectés par catégorie.

        Returns:
            dict: {"linear": [...], "inverse": [...]}
        """
        return {
            "linear": self.linear_symbols.copy(),
            "inverse": self.inverse_symbols.copy(),
        }
    
    def is_connected(self) -> bool:
        """Vérifie si au moins une connexion WebSocket est active."""
        return any(conn.is_connected() for conn in self._ws_conns)
    
    def get_connection_status(self) -> Dict[str, bool]:
        """Retourne le statut de toutes les connexions."""
        status = {}
        for i, conn in enumerate(self._ws_conns):
            category = "linear" if i == 0 and self.linear_symbols else "inverse"
            status[f"{category}_connection"] = conn.is_connected()
        return status
    
    def add_symbols(self, category: str, symbols: List[str]) -> None:
        """Ajoute des symboles à une connexion existante."""
        if category == "linear":
            self.linear_symbols.extend(symbols)
        elif category == "inverse":
            self.inverse_symbols.extend(symbols)
        else:
            raise ValueError(f"Catégorie non supportée: {category}")
    
    def remove_symbols(self, category: str, symbols: List[str]) -> None:
        """Retire des symboles d'une connexion existante."""
        if category == "linear":
            for symbol in symbols:
                if symbol in self.linear_symbols:
                    self.linear_symbols.remove(symbol)
        elif category == "inverse":
            for symbol in symbols:
                if symbol in self.inverse_symbols:
                    self.inverse_symbols.remove(symbol)
        else:
            raise ValueError(f"Catégorie non supportée: {category}")
    
    def set_orderbook_callback(self, callback: Callable) -> None:
        """Définit le callback pour les orderbooks."""
        self.on_orderbook_callback = callback
    
    def get_reconnect_delays(self) -> List[int]:
        """Retourne la liste des délais de reconnexion."""
        return [1, 2, 5, 10, 30]  # Délais par défaut
    
    def set_reconnect_delays(self, delays: List[int]) -> None:
        """Définit les délais de reconnexion."""
        # Les délais sont gérés par les WebSocket clients individuels
        pass
    
    def get_reconnect_count(self) -> int:
        """Retourne le nombre de reconnexions effectuées."""
        return sum(conn.reconnect_count for conn in self._ws_conns)
    
    def reset_reconnect_count(self) -> None:
        """Remet à zéro le compteur de reconnexions."""
        for conn in self._ws_conns:
            conn.reconnect_count = 0
    
    def get_last_error(self) -> Optional[Exception]:
        """Retourne la dernière erreur rencontrée."""
        for conn in self._ws_conns:
            if hasattr(conn, 'last_error') and conn.last_error:
                return conn.last_error
        return None
    
    def clear_last_error(self) -> None:
        """Efface la dernière erreur."""
        for conn in self._ws_conns:
            if hasattr(conn, 'last_error'):
                conn.last_error = None
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de connexion."""
        stats = {
            "total_connections": len(self._ws_conns),
            "connected_count": sum(1 for conn in self._ws_conns if conn.is_connected()),
            "linear_symbols_count": len(self.linear_symbols),
            "inverse_symbols_count": len(self.inverse_symbols),
            "total_reconnects": self.get_reconnect_count(),
            "is_running": self.running
        }
        return stats
    
    def is_testnet(self) -> bool:
        """Indique si le gestionnaire utilise le testnet."""
        return self.testnet
    
    def get_data_manager(self):
        """Retourne le gestionnaire de données associé."""
        return self.data_manager
    
    def set_data_manager(self, data_manager) -> None:
        """Définit le gestionnaire de données."""
        self.data_manager = data_manager
    
    def start_watchdog(self) -> None:
        """Démarre le thread watchdog pour surveiller les connexions."""
        # Le watchdog est géré par les WebSocket clients individuels
        pass
    
    def stop_watchdog(self) -> None:
        """Arrête le thread watchdog."""
        # Le watchdog est géré par les WebSocket clients individuels
        pass
    
    def is_watchdog_running(self) -> bool:
        """Vérifie si le watchdog est en cours d'exécution."""
        return any(hasattr(conn, 'watchdog_running') and conn.watchdog_running for conn in self._ws_conns)
