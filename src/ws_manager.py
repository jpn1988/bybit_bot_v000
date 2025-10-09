#!/usr/bin/env python3
"""
Gestionnaire WebSocket dédié pour les connexions publiques Bybit -
Version asynchrone.

Cette classe gère uniquement :
- La connexion WS publique
- La souscription aux symboles
- La réception et mise à jour des prix en temps réel
"""

import asyncio
import time
from typing import List, Callable, Optional, TYPE_CHECKING
from logging_setup import setup_logging
from ws_public import PublicWSClient

if TYPE_CHECKING:
    from unified_data_manager import UnifiedDataManager


class WebSocketManager:
    """
    Gestionnaire WebSocket pour les connexions publiques Bybit -
    Version asynchrone.

    Responsabilités :
    - Gestion des connexions WebSocket publiques (linear/inverse)
    - Souscription aux symboles pour les tickers
    - Réception et traitement des données de prix en temps réel
    - Callbacks vers l'application principale
    """

    def __init__(
        self, testnet: bool = True, data_manager: Optional["UnifiedDataManager"] = None, logger=None
    ):
        """
        Initialise le gestionnaire WebSocket.

        Args:
            testnet (bool): Utiliser le testnet (True) ou le marché réel
            (False)
            data_manager: Instance du gestionnaire de données unifié (injection de dépendances)
            logger: Logger pour les messages (optionnel)
        """
        self.testnet = testnet
        self.data_manager = data_manager
        self.logger = logger or setup_logging()
        self.running = False

        # Connexions WebSocket asynchrones
        self._ws_conns: List[PublicWSClient] = []
        self._ws_tasks: List[asyncio.Task] = []

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
        self, linear_symbols: List[str], inverse_symbols: List[str]
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
                self.data_manager.update_price_data(symbol, mark_val, last_val, time.time())

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
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, conn.run)
        except Exception as e:
            if self.running:
                self.logger.warning(f"⚠️ Erreur connexion WebSocket: {e}")

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
                            task, timeout=3.0
                        )  # Timeout réduit à 3s
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
                import time

                time.sleep(0.1)
            except Exception as e:
                self.logger.warning(
                    f"⚠️ Erreur fermeture connexion WebSocket: {e}"
                )

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
