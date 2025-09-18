#!/usr/bin/env python3
"""
Client WebSocket privé Bybit v5 réutilisable.

Cette classe centralise la logique d'authentification, de souscription aux topics
privés, la gestion du ping/pong, le watchdog d'auth, et la reconnexion avec backoff.

Utilisation typique:
    client = PrivateWSClient(testnet, api_key, api_secret, channels, logger)
    # (optionnel) brancher des callbacks
    client.on_topic = lambda topic, data: ...
    client.run()
"""

import os
import time
import json
import hmac
import hashlib
import threading
import websocket


class PrivateWSClient:
    """Client WebSocket privée Bybit v5 avec authentification et reconnexion."""

    def __init__(
        self,
        *,
        testnet: bool,
        api_key: str,
        api_secret: str,
        channels: list[str] | None,
        logger,
        reconnect_delays: list[int] | None = None,
    ) -> None:
        self.logger = logger
        self.ws = None
        self.running = True
        self.connected = False
        self._authed = False
        self._auth_sent_at = 0.0

        self.testnet = bool(testnet)
        self.api_key = api_key
        self.api_secret = api_secret
        self.channels = channels or []

        self.ws_url = (
            "wss://stream-testnet.bybit.com/v5/private"
            if self.testnet
            else "wss://stream.bybit.com/v5/private"
        )

        self.reconnect_delays = reconnect_delays or [1, 2, 5, 10]
        self.current_delay_index = 0

        # Callbacks optionnels
        self.on_open_cb = None
        self.on_close_cb = None
        self.on_error_cb = None
        self.on_auth_success = None
        self.on_auth_failure = None
        self.on_topic = None  # (topic: str, data: dict)
        self.on_pong = None

    # ========================= Helpers =========================
    def _generate_ws_signature(self, expires_ms: int) -> str:
        payload = f"GET/realtime{expires_ms}"
        return hmac.new(
            self.api_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    # ========================= WebSocket callbacks =========================
    def _on_open(self, ws):
        try:
            self.logger.info(f"🌐 WS privée ouverte (testnet={self.testnet})")
        except Exception:
            pass
        self.connected = True
        self._authed = False

        # Authentification immédiate
        expires_ms = int((time.time() + 60) * 1000)
        signature = self._generate_ws_signature(expires_ms)
        auth_message = {"op": "auth", "args": [self.api_key, expires_ms, signature]}

        try:
            self.logger.info("🪪 Authentification en cours…")
        except Exception:
            pass
        self.ws.send(json.dumps(auth_message))
        self._auth_sent_at = time.monotonic()

        if callable(self.on_open_cb):
            try:
                self.on_open_cb()
            except Exception:
                pass

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)

            # Ping/Pong
            if data.get("op") == "pong" or "pong" in str(data).lower():
                # Bruit minimisé par défaut
                try:
                    self.logger.debug("pong")
                except Exception:
                    pass
                if callable(self.on_pong):
                    try:
                        self.on_pong()
                    except Exception:
                        pass
                return

            # Auth
            if data.get("op") == "auth":
                ret_code = data.get("retCode", -1)
                ret_msg = data.get("retMsg", "")
                success = data.get("success", False)

                if (success is True and data.get("op") == "auth") or (
                    ret_code == 0 and data.get("op") == "auth"
                ):
                    try:
                        self.logger.info("✅ Authentification réussie")
                    except Exception:
                        pass
                    self._authed = True
                    # Souscrire aux channels
                    if self.channels:
                        sub_msg = {"op": "subscribe", "args": self.channels}
                        try:
                            self.ws.send(json.dumps(sub_msg))
                            self.logger.info(f"🧭 Souscription privée → {self.channels}")
                        except Exception as e:
                            try:
                                self.logger.warning(f"⚠️ Échec souscription privée: {e}")
                            except Exception:
                                pass
                    if callable(self.on_auth_success):
                        try:
                            self.on_auth_success()
                        except Exception:
                            pass
                else:
                    try:
                        self.logger.error(
                            f"⛔ Échec authentification WS : retCode={ret_code} retMsg=\"{ret_msg}\""
                        )
                    except Exception:
                        pass
                    if callable(self.on_auth_failure):
                        try:
                            self.on_auth_failure(ret_code, ret_msg)
                        except Exception:
                            pass
                    self.ws.close()
                return

            # Souscriptions
            if data.get("op") == "subscribe" and data.get("success") is True:
                try:
                    self.logger.info("✅ Souscription confirmée")
                except Exception:
                    pass
                return

            # Topics
            topic = data.get("topic", "")
            if topic and callable(self.on_topic):
                try:
                    self.on_topic(topic, data)
                except Exception:
                    pass
            else:
                # Debug court
                message_preview = str(data)[:100] + "..." if len(str(data)) > 100 else str(data)
                try:
                    self.logger.debug(f"ℹ️ Private msg: {message_preview}")
                except Exception:
                    pass

        except json.JSONDecodeError:
            try:
                self.logger.debug(f"Message brut reçu: {message[:100]}...")
            except Exception:
                pass
        except Exception as e:
            try:
                self.logger.error(f"Erreur traitement message: {e}")
            except Exception:
                pass

    def _on_error(self, ws, error):
        try:
            self.logger.error(f"Erreur WebSocket: {error}")
        except Exception:
            pass
        self.connected = False
        self._authed = False
        if callable(self.on_error_cb):
            try:
                self.on_error_cb(error)
            except Exception:
                pass

    def _on_close(self, ws, close_status_code, close_msg):
        try:
            self.logger.info("🔌 Connexion WebSocket fermée")
        except Exception:
            pass
        self.connected = False
        self._authed = False
        if callable(self.on_close_cb):
            try:
                self.on_close_cb(close_status_code, close_msg)
            except Exception:
                pass

    # ========================= Watchdog & Run =========================
    def _watchdog_loop(self):
        while self.running:
            try:
                if self.connected and not self._authed and time.monotonic() - self._auth_sent_at > 10:
                    try:
                        self.logger.warning("⏳ Auth sans réponse (>10s) → redémarrage WS")
                    except Exception:
                        pass
                    try:
                        self.ws.close()
                    except Exception:
                        pass
                time.sleep(1)
            except Exception:
                # Ne pas tuer le watchdog, continuer
                time.sleep(1)

    def run(self):
        """Boucle principale avec reconnexion et watchdog."""
        watchdog_thread = threading.Thread(target=self._watchdog_loop)
        watchdog_thread.daemon = True
        watchdog_thread.start()

        while self.running:
            try:
                try:
                    self.logger.info("🔐 Connexion à la WebSocket privée…")
                except Exception:
                    pass

                self.ws = websocket.WebSocketApp(
                    self.ws_url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )

                self.ws.run_forever(ping_interval=20, ping_timeout=10)

            except Exception as e:
                if self.running:
                    try:
                        self.logger.error(f"Erreur connexion: {e}")
                    except Exception:
                        pass

            # Reconnexion avec backoff
            if self.running:
                delay = self.reconnect_delays[min(self.current_delay_index, len(self.reconnect_delays) - 1)]
                try:
                    self.logger.warning(f"🔁 WS privée déconnectée → reconnexion dans {delay}s")
                except Exception:
                    pass
                for _ in range(delay):
                    if not self.running:
                        break
                    time.sleep(1)
                if self.current_delay_index < len(self.reconnect_delays) - 1:
                    self.current_delay_index += 1
            else:
                break

    def close(self):
        """Ferme proprement la WebSocket."""
        if self.running:
            try:
                self.logger.info("🧹 Arrêt demandé, fermeture de la WS…")
            except Exception:
                pass
            self.running = False
            try:
                if self.ws:
                    self.ws.close()
            finally:
                try:
                    self.logger.info("🏁 WS privée arrêtée")
                except Exception:
                    pass


