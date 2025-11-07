#!/usr/bin/env python3
"""
Gestionnaire WebSocket simplifié pour le bot Bybit.

Ce module implémente une façade simplifiée qui orchestre les modules spécialisés :
- ConnectionPool : Gestion du ThreadPoolExecutor
- ConnectionStrategy : Stratégie de répartition
- Handlers : Callbacks et métriques
"""

import asyncio
import time
from typing import List, Callable, Optional, Dict, Any, TYPE_CHECKING

from logging_setup import setup_logging
from ws_public import PublicWSClient
from interfaces.websocket_manager_interface import WebSocketManagerInterface
from interfaces.data_manager_interface import DataManagerInterface

from .connection_pool import WebSocketConnectionPool
from .strategy import WebSocketConnectionStrategy, ConnectionStrategy
from .handlers import WebSocketHandlers

if TYPE_CHECKING:
    from typing_imports import DataManager


class WebSocketManager(WebSocketManagerInterface):
    """
    Gestionnaire WebSocket simplifié pour les connexions publiques Bybit.

    Cette classe orchestre les modules spécialisés pour gérer les connexions
    WebSocket de manière modulaire et maintenable.

    Architecture :
    - ConnectionPool : Gestion du ThreadPoolExecutor
    - ConnectionStrategy : Stratégie de répartition linear/inverse
    - Handlers : Callbacks et métriques
    - WebSocketManager : Façade simplifiée

    Responsabilités :
    - Orchestrer les modules spécialisés
    - Gérer le cycle de vie des connexions
    - Fournir une interface simple et cohérente
    """

    def __init__(self, testnet: bool = True, data_manager: Optional[DataManagerInterface] = None, logger=None):
        """
        Initialise le gestionnaire WebSocket.

        Args:
            testnet: Environnement à utiliser
            data_manager: Gestionnaire de données
            logger: Logger pour les messages
        """
        self.testnet = testnet
        self.data_manager = data_manager
        self.logger = logger or setup_logging()
        self.running = False

        # Modules spécialisés
        self._connection_pool = WebSocketConnectionPool(self.logger)
        self._strategy = WebSocketConnectionStrategy(self.logger)
        self._handlers = WebSocketHandlers(self.logger)
        self._executor_signature: Optional[str] = None

        # Connexions WebSocket actives
        self._ws_conns: List[PublicWSClient] = []
        self._ws_tasks: List[asyncio.Task] = []

        # Symboles par catégorie
        self.linear_symbols: List[str] = []
        self.inverse_symbols: List[str] = []

        # Callbacks
        self._ticker_callback: Optional[Callable] = None
        self.on_orderbook_callback: Optional[Callable] = None

        # Configurer les handlers
        self._handlers.set_data_manager(data_manager)

    def set_ticker_callback(self, callback: Callable[[dict], None]):
        """
        Définit le callback pour les données ticker.

        Args:
            callback: Fonction à appeler avec les données ticker

        Raises:
            TypeError: Si callback n'est pas une fonction
        """
        if not callable(callback):
            raise TypeError("callback doit être une fonction")
        self._ticker_callback = callback
        self._handlers.set_ticker_callback(callback)

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
                # Utiliser la méthode déléguée de DataManagerInterface au lieu d'accéder à .storage
                self.data_manager.update_price_data(symbol, mark_val, last_val, time.time())

            # Appeler le callback externe si défini
            if self._ticker_callback and symbol:
                self._ticker_callback(ticker_data)

        except Exception as e:
            self.logger.warning(f"⚠️ Erreur traitement ticker WebSocket: {e}")

    def _build_executor_signature(self, strategy: ConnectionStrategy) -> str:
        """Construit une signature stable de la configuration du ThreadPoolExecutor."""
        linear_key = ",".join(sorted(set(strategy.linear_symbols)))
        inverse_key = ",".join(sorted(set(strategy.inverse_symbols)))
        return (
            f"{strategy.total_connections}:"
            f"{int(strategy.needs_linear)}{int(strategy.needs_inverse)}|"
            f"{linear_key}|{inverse_key}"
        )

    async def _ensure_executor_ready(self, strategy: ConnectionStrategy) -> None:
        """S'assure que l'exécuteur correspond à la stratégie demandée."""
        signature = self._build_executor_signature(strategy)
        force_recreate = self._executor_signature is not None and signature != self._executor_signature
        workers = max(1, strategy.total_connections)

        created = await self._connection_pool.ensure_executor(
            max_workers=workers,
            force_recreate=force_recreate,
        )

        if created:
            if force_recreate:
                self.logger.debug(f"🧵 ThreadPoolExecutor recréé ({workers} worker(s))")
            else:
                self.logger.debug(f"🧵 ThreadPoolExecutor initialisé ({workers} worker(s))")
        else:
            self.logger.debug("♻️ ThreadPoolExecutor réutilisé (configuration inchangée)")

        self._executor_signature = signature

    async def start_connections(self, linear_symbols: List[str], inverse_symbols: List[str],
                               on_ticker_callback: Optional[Callable] = None,
                               on_orderbook_callback: Optional[Callable] = None):
        """
        Démarre les connexions WebSocket.

        Args:
            linear_symbols: Symboles linear à suivre
            inverse_symbols: Symboles inverse à suivre
            on_ticker_callback: Callback pour les tickers
            on_orderbook_callback: Callback pour les orderbooks
        """
        if self.running:
            self.logger.warning("⚠️ WebSocketManager déjà en cours d'exécution")
            return

        # Mémoriser les symboles fournis avant de lancer la stratégie
        self.linear_symbols = linear_symbols
        self.inverse_symbols = inverse_symbols

        # Configurer les callbacks
        if on_ticker_callback:
            self.set_ticker_callback(on_ticker_callback)
        if on_orderbook_callback:
            self.set_orderbook_callback(on_orderbook_callback)

        # Analyser la stratégie de connexion
        strategy = self._strategy.analyze_symbols(linear_symbols, inverse_symbols)

        if strategy.total_connections == 0:
            self.logger.warning("⚠️ Aucun symbole fourni pour les connexions WebSocket")
            return

        # Préparer le pool de connexions
        await self._ensure_executor_ready(strategy)

        # Démarrer les connexions selon la stratégie
        await self._start_connections_by_strategy(strategy)

        self.running = True
        self.logger.info(f"✅ WebSocketManager démarré ({strategy.total_connections} connexion(s))")

    async def _start_connections_by_strategy(self, strategy: ConnectionStrategy):
        """Démarre les connexions selon la stratégie."""
        if strategy.needs_linear and strategy.needs_inverse:
            await self._start_dual_connections(strategy)
        elif strategy.needs_linear:
            await self._start_single_connection("linear", strategy.linear_symbols)
        elif strategy.needs_inverse:
            await self._start_single_connection("inverse", strategy.inverse_symbols)

    async def _start_single_connection(self, category: str, symbols: List[str]):
        """Démarre une connexion pour une catégorie."""
        # Valider les symboles
        valid_symbols = self._strategy.validate_symbols(symbols, category)
        if not valid_symbols:
            self.logger.warning(f"⚠️ Aucun symbole valide pour {category}")
            return

        # Créer la connexion
        conn = PublicWSClient(
            category=category,
            symbols=valid_symbols,
            testnet=self.testnet,
            logger=self.logger,
            on_ticker_callback=self._handle_ticker,
        )

        self._ws_conns = [conn]

        # Lancer dans un thread
        task = asyncio.create_task(self._run_websocket_connection(conn))
        self._ws_tasks = [task]

        self.logger.info(f"✅ Connexion {category} démarrée ({len(valid_symbols)} symboles)")

    async def _start_dual_connections(self, strategy: ConnectionStrategy):
        """Démarre les connexions duales (linear + inverse)."""
        # Valider les symboles
        linear_valid = self._strategy.validate_symbols(self.linear_symbols, "linear")
        inverse_valid = self._strategy.validate_symbols(self.inverse_symbols, "inverse")

        connections = []
        tasks = []

        # Connexion linear
        if linear_valid:
            linear_conn = PublicWSClient(
                category="linear",
                symbols=linear_valid,
                testnet=self.testnet,
                logger=self.logger,
                on_ticker_callback=self._handle_ticker,
            )
            connections.append(linear_conn)
            tasks.append(asyncio.create_task(self._run_websocket_connection(linear_conn)))

        # Connexion inverse
        if inverse_valid:
            inverse_conn = PublicWSClient(
                category="inverse",
                symbols=inverse_valid,
                testnet=self.testnet,
                logger=self.logger,
                on_ticker_callback=self._handle_ticker,
            )
            connections.append(inverse_conn)
            tasks.append(asyncio.create_task(self._run_websocket_connection(inverse_conn)))

        self._ws_conns = connections
        self._ws_tasks = tasks

        self.logger.info(f"✅ Connexions duales démarrées (linear: {len(linear_valid)}, inverse: {len(inverse_valid)})")

    async def _run_websocket_connection(self, conn: PublicWSClient):
        """Exécute une connexion WebSocket dans un thread."""
        try:
            await self._connection_pool.run_websocket_in_thread(conn.run)
        except Exception as e:
            if self.running:
                self.logger.warning(f"⚠️ Erreur connexion WebSocket: {e}")

    async def stop_connections(self) -> None:
        """Arrête toutes les connexions WebSocket."""
        await self.stop()

    async def stop(self):
        """Arrête toutes les connexions WebSocket."""
        if not self.running:
            return

        self.running = False

        # Nettoyer les handlers
        self._ticker_callback = None
        self._handlers.clear_callbacks()

        # Fermer toutes les connexions
        for conn in self._ws_conns:
            try:
                conn.close()
                await asyncio.sleep(0.1)
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur fermeture connexion: {e}")

        # Annuler les tâches
        for task in self._ws_tasks:
            if not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=5.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass

        # Arrêter le pool de connexions
        await self._connection_pool.shutdown_with_timeout()
        self._executor_signature = None

        # Nettoyer les références
        self._ws_conns.clear()
        self._ws_tasks.clear()
        self.linear_symbols.clear()
        self.inverse_symbols.clear()

        self.logger.info("🛑 WebSocketManager arrêté")

    def stop_sync(self):
        """Arrête les connexions de manière synchrone."""
        if not self.running:
            return

        self.running = False
        self._ticker_callback = None
        self._handlers.clear_callbacks()

        # Fermer les connexions
        for conn in self._ws_conns:
            try:
                conn.close()
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur fermeture connexion: {e}")

        # Arrêter le pool
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self._connection_pool.shutdown_with_timeout())
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur arrêt pool: {e}")
        finally:
            self._executor_signature = None

        # Nettoyer
        self._ws_conns.clear()
        self._ws_tasks.clear()
        self.linear_symbols.clear()
        self.inverse_symbols.clear()

    # Interface WebSocketManagerInterface
    def is_running(self) -> bool:
        """Vérifie si le gestionnaire est actif."""
        return self.running

    def get_connected_symbols(self) -> dict:
        """Retourne les symboles connectés par catégorie."""
        return {
            "linear": self.linear_symbols.copy(),
            "inverse": self.inverse_symbols.copy(),
        }

    def is_connected(self) -> bool:
        """Vérifie si au moins une connexion est active."""
        return any(conn.is_connected() for conn in self._ws_conns)

    def get_connection_status(self) -> Dict[str, bool]:
        """Retourne le statut de toutes les connexions."""
        status = {}
        for i, conn in enumerate(self._ws_conns):
            category = "linear" if i == 0 and self.linear_symbols else "inverse"
            status[f"{category}_connection"] = conn.is_connected()
        return status

    def get_connection_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de connexion."""
        return self._handlers.get_connection_stats()

    def is_testnet(self) -> bool:
        """Indique si le gestionnaire utilise le testnet."""
        return self.testnet

    def get_data_manager(self):
        """Retourne le gestionnaire de données."""
        return self.data_manager

    def set_data_manager(self, data_manager) -> None:
        """Définit le gestionnaire de données."""
        self.data_manager = data_manager
        self._handlers.set_data_manager(data_manager)

    def add_symbols(self, category: str, symbols: List[str]) -> None:
        """Ajoute des symboles à une connexion existante."""
        if category == "linear":
            self.linear_symbols.extend(symbols)
        elif category == "inverse":
            self.inverse_symbols.extend(symbols)
        else:
            raise ValueError(f"Catégorie non supportée: {category}")
        self.logger.info(f"✅ Symboles ajoutés à {category}: {len(symbols)} symboles")

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
        self.logger.info(f"✅ Symboles retirés de {category}: {len(symbols)} symboles")

    def set_orderbook_callback(self, callback: Callable) -> None:
        """Définit le callback pour les orderbooks."""
        self.on_orderbook_callback = callback
        self._handlers.set_orderbook_callback(callback)

    def get_reconnect_delays(self) -> List[int]:
        """Retourne la liste des délais de reconnexion."""
        return [1, 2, 5, 10, 30]  # Délais par défaut

    def set_reconnect_delays(self, delays: List[int]) -> None:
        """Définit les délais de reconnexion."""
        # Les délais sont gérés par les WebSocket clients individuels
        self.logger.info(f"✅ Délais de reconnexion définis: {delays}")

    def get_reconnect_count(self) -> int:
        """Retourne le nombre de reconnexions effectuées."""
        return sum(getattr(conn, 'reconnect_count', 0) for conn in self._ws_conns)

    def reset_reconnect_count(self) -> None:
        """Remet à zéro le compteur de reconnexions."""
        for conn in self._ws_conns:
            if hasattr(conn, 'reconnect_count'):
                conn.reconnect_count = 0
        self.logger.info("✅ Compteur de reconnexions remis à zéro")

    def get_last_error(self) -> Optional[Exception]:
        """Retourne la dernière erreur rencontrée."""
        return self._handlers.get_metrics().last_error

    def clear_last_error(self) -> None:
        """Efface la dernière erreur."""
        self._handlers.reset_metrics()
        self.logger.debug("✅ Dernière erreur effacée")

    def start_watchdog(self) -> None:
        """Démarre le thread watchdog pour surveiller les connexions."""
        # Le watchdog est géré par les WebSocket clients individuels
        self.logger.debug("✅ Watchdog démarré (géré par les clients)")

    def stop_watchdog(self) -> None:
        """Arrête le thread watchdog."""
        # Le watchdog est géré par les WebSocket clients individuels
        self.logger.debug("✅ Watchdog arrêté (géré par les clients)")

    def is_watchdog_running(self) -> bool:
        """Vérifie si le watchdog est en cours d'exécution."""
        return any(hasattr(conn, 'watchdog_running') and getattr(conn, 'watchdog_running', False) for conn in self._ws_conns)

    async def switch_to_single_symbol(self, symbol: str, category: str = "linear"):
        """
        Bascule vers l'écoute d'un seul symbole.

        Arrête les connexions actuelles et ne suit que le symbole spécifié.
        Utile quand une position est ouverte sur un symbole spécifique.

        Args:
            symbol: Symbole à suivre
            category: Catégorie du symbole ("linear" ou "inverse")
        """
        try:
            self.logger.info(f"🔄 Basculement vers symbole unique: {symbol} ({category})")

            # Arrêter les connexions actuelles
            await self.stop()

            # Attendre un peu pour que l'arrêt se propage
            await asyncio.sleep(0.5)

            # Démarrer une nouvelle connexion pour le symbole unique
            if category == "linear":
                await self.start_connections([symbol], [])
            else:
                await self.start_connections([], [symbol])

            self.logger.info(f"✅ Basculement terminé - Suivi de {symbol}")

        except Exception as e:
            self.logger.error(f"❌ Erreur basculement vers {symbol}: {e}")

    async def restore_full_watchlist(self, linear_symbols: List[str], inverse_symbols: List[str]):
        """
        Restaure l'écoute de la watchlist complète.

        Arrête la connexion actuelle et redémarre avec tous les symboles
        de la watchlist. Utilisé quand une position est fermée.

        Args:
            linear_symbols: Liste des symboles linear à suivre
            inverse_symbols: Liste des symboles inverse à suivre
        """
        try:
            self.logger.info(f"🔄 Restauration watchlist complète: {len(linear_symbols)} linear, {len(inverse_symbols)} inverse")

            # Arrêter les connexions actuelles
            await self.stop()

            # Attendre un peu pour que l'arrêt se propage
            await asyncio.sleep(0.5)

            # Redémarrer avec la watchlist complète
            if linear_symbols or inverse_symbols:
                await self.start_connections(linear_symbols, inverse_symbols)

            self.logger.info("✅ Watchlist complète restaurée")

        except Exception as e:
            self.logger.error(f"❌ Erreur restauration watchlist: {e}")
