#!/usr/bin/env python3
"""
Gestionnaire de positions pour le bot Bybit.

Ce module surveille les positions ouvertes/fermées via WebSocket privé
et notifie les autres composants via des callbacks.

Responsabilités :
- Surveillance des positions via WebSocket privé (topic "position")
- Détection d'ouverture/fermeture de positions
- Callbacks pour notifier les changements d'état
- Thread-safe avec gestion des erreurs
"""

import asyncio
import inspect
import threading
import time
from typing import Optional, Callable, Dict, Any
from logging_setup import setup_logging
from ws_private import PrivateWSClient
from config import get_settings


class PositionMonitor:
    """
    Gestionnaire de surveillance des positions via WebSocket privé.

    Ce composant surveille les positions en temps réel et notifie
    les changements d'état via des callbacks.
    """

    def __init__(
        self,
        testnet: bool = True,
        logger=None,
        on_position_opened: Optional[Callable[[str, Dict], None]] = None,
        on_position_closed: Optional[Callable[[str, Dict], None]] = None,
    ):
        """
        Initialise le moniteur de positions.

        Args:
            testnet: Utiliser le testnet (True) ou mainnet (False)
            logger: Logger pour les messages (optionnel)
            on_position_opened: Callback appelé lors de l'ouverture d'une position
            on_position_closed: Callback appelé lors de la fermeture d'une position
        """
        self.testnet = testnet
        self.logger = logger or setup_logging()

        # Callbacks
        self.on_position_opened = on_position_opened
        self.on_position_closed = on_position_closed

        # État du moniteur
        self._running = False
        self._ws_client = None
        self._ws_thread = None

        # Tracking des positions actuelles
        self._current_positions = {}  # {symbol: position_data}

        # Thread safety
        self._lock = threading.Lock()

        # Configuration des clés API
        settings = get_settings()
        self.api_key = settings.get("api_key")
        self.api_secret = settings.get("api_secret")

        if not self.api_key or not self.api_secret:
            self.logger.warning("[POSITION] ⚠️ Clés API manquantes - PositionMonitor désactivé")
            self._enabled = False
        else:
            self._enabled = True

    def start(self):
        """
        Démarre la surveillance des positions.

        Lance le WebSocket privé dans un thread séparé.
        """
        if not self._enabled:
            self.logger.warning("[POSITION] ⚠️ PositionMonitor désactivé - clés API manquantes")
            return

        if self._running:
            self.logger.warning("[POSITION] ⚠️ PositionMonitor déjà en cours d'exécution")
            return

        try:
            # Créer le client WebSocket privé
            self._ws_client = PrivateWSClient(
                testnet=self.testnet,
                api_key=self.api_key,
                api_secret=self.api_secret,
                channels=["position"],
                logger=self.logger,
            )

            # Configurer les callbacks
            self._ws_client.on_topic = self._handle_position_message
            self._ws_client.on_auth_success = self._on_auth_success
            self._ws_client.on_error = self._on_error
            self._ws_client.on_close = self._on_close

            # Démarrer dans un thread séparé
            self._ws_thread = threading.Thread(
                target=self._ws_runner,
                daemon=True,
                name="position_monitor_ws"
            )
            self._ws_thread.start()

            self._running = True
            self.logger.info("[POSITION] 🔍 PositionMonitor démarré")

        except Exception as e:
            self.logger.error(f"❌ Erreur démarrage PositionMonitor: {e}")
            self._running = False

    def stop(self):
        """
        Arrête la surveillance des positions.
        """
        if not self._running:
            return

        self._running = False

        # Arrêter le WebSocket
        if self._ws_client:
            try:
                self._ws_client.close()
            except Exception as e:
                self.logger.warning(f"[POSITION] ⚠️ Erreur fermeture WebSocket: {e}")

        # Attendre la fin du thread
        if self._ws_thread and self._ws_thread.is_alive():
            try:
                self._ws_thread.join(timeout=5)
            except Exception:
                pass

            self.logger.info("[POSITION] 🛑 PositionMonitor arrêté")

    def is_running(self) -> bool:
        """Retourne True si le moniteur est actif."""
        return self._running

    def has_open_positions(self) -> bool:
        """
        Vérifie s'il y a des positions ouvertes.

        Returns:
            True si au moins une position est ouverte
        """
        with self._lock:
            return any(
                pos.get("size", "0") != "0" and float(pos.get("size", "0")) > 0
                for pos in self._current_positions.values()
            )

    def get_open_positions(self) -> Dict[str, Dict]:
        """
        Retourne les positions ouvertes.

        Returns:
            Dict des positions ouvertes {symbol: position_data}
        """
        with self._lock:
            return {
                symbol: pos for symbol, pos in self._current_positions.items()
                if pos.get("size", "0") != "0" and float(pos.get("size", "0")) > 0
            }

    def _ws_runner(self):
        """Runner pour le WebSocket privé."""
        if self._ws_client:
            try:
                self._ws_client.run()
            except Exception as e:
                if self._running:
                    self.logger.warning(f"[POSITION] ⚠️ Erreur WebSocket PositionMonitor: {e}")

    def _handle_position_message(self, topic: str, data: Dict[str, Any]):
        """
        Gère les messages de position reçus.

        Args:
            topic: Topic du message ("position")
            data: Données de position
        """
        try:
            if topic != "position":
                return

            # Parser les données de position
            positions = data.get("data", [])
            if not positions:
                return

            for position in positions:
                self._process_position_update(position)

        except Exception as e:
            self.logger.warning(f"[POSITION] ⚠️ Erreur traitement position: {e}")

    def _process_position_update(self, position_data: Dict[str, Any]):
        """
        Traite une mise à jour de position.

        Args:
            position_data: Données de la position
        """
        try:
            symbol = position_data.get("symbol", "")
            size = position_data.get("size", "0")
            side = position_data.get("side", "")

            if not symbol:
                return

            # Convertir size en float pour comparaison
            try:
                size_float = float(size)
            except (ValueError, TypeError):
                size_float = 0.0

            with self._lock:
                # Mettre à jour le cache des positions
                self._current_positions[symbol] = position_data

                # Vérifier les changements d'état
                was_open = self._was_position_open(symbol)
                is_now_open = size_float > 0

                if not was_open and is_now_open:
                    # Position ouverte
                    self.logger.info(f"[POSITION] 📈 Position ouverte: {symbol} {side} {size}")
                    if self.on_position_opened:
                        try:
                            callback_result = self.on_position_opened(symbol, position_data)
                            if inspect.isawaitable(callback_result):
                                try:
                                    loop = asyncio.get_running_loop()
                                except RuntimeError:
                                    asyncio.run(callback_result)
                                else:
                                    loop.create_task(callback_result)
                        except Exception as e:
                            self.logger.warning(f"[POSITION] ⚠️ Erreur callback position ouverte: {e}")

                elif was_open and not is_now_open:
                    # Position fermée
                    self.logger.info(f"[POSITION] 📉 Position fermée: {symbol}")
                    if self.on_position_closed:
                        try:
                            self.on_position_closed(symbol, position_data)
                        except Exception as e:
                            self.logger.warning(f"[POSITION] ⚠️ Erreur callback position fermée: {e}")

                # Nettoyer les positions fermées du cache
                if not is_now_open and symbol in self._current_positions:
                    del self._current_positions[symbol]

        except Exception as e:
            self.logger.warning(f"[POSITION] ⚠️ Erreur traitement position {symbol}: {e}")

    def _was_position_open(self, symbol: str) -> bool:
        """
        Vérifie si une position était ouverte précédemment.

        Args:
            symbol: Symbole à vérifier

        Returns:
            True si la position était ouverte
        """
        if symbol not in self._current_positions:
            return False

        old_size = self._current_positions[symbol].get("size", "0")
        try:
            return float(old_size) > 0
        except (ValueError, TypeError):
            return False

    def _on_auth_success(self):
        """Callback d'authentification réussie."""
        self.logger.info("[POSITION] ✅ PositionMonitor authentifié")

    def _on_error(self, error):
        """Callback d'erreur WebSocket."""
        if self._running:
            self.logger.warning(f"[POSITION] ⚠️ Erreur WebSocket PositionMonitor: {error}")

    def _on_close(self, close_status_code, close_msg):
        """Callback de fermeture WebSocket."""
        if self._running:
            self.logger.info("[POSITION] 🔌 WebSocket PositionMonitor fermé")
