#!/usr/bin/env python3
"""WebSocket publique Bybit v5 - Client réutilisable avec reconnexion 
automatique."""

import json
import time
import websocket
from typing import Callable, List, Optional
from metrics import record_ws_connection, record_ws_error


class PublicWSClient:
    """
    Client WebSocket publique Bybit v5 réutilisable.

    Gère automatiquement la connexion, reconnexion, souscription aux symboles
    et le traitement des messages tickers.
    """

    def __init__(
        self,
        category: str,
        symbols: List[str],
        testnet: bool,
        logger,
        on_ticker_callback: Callable[[dict], None],
    ):
        """
        Initialise le client WebSocket publique.

        Args:
            category (str): Catégorie des symboles ("linear" ou "inverse")
            symbols (List[str]): Liste des symboles à suivre
            testnet (bool): Utiliser le testnet (True) ou le mainnet (False)
            logger: Instance du logger pour les messages
            on_ticker_callback (Callable): Fonction appelée pour chaque 
            ticker reçu
        """
        self.category = category
        self.symbols = symbols
        self.testnet = testnet
        self.logger = logger
        self.on_ticker_callback = on_ticker_callback
        self.ws: Optional[websocket.WebSocketApp] = None
        self.running = False

        # Configuration de reconnexion avec backoff progressif
        self.reconnect_delays = [1, 2, 5, 10, 30]  # secondes
        self.current_delay_index = 0

        # Callbacks optionnels pour événements de connexion
        self.on_open_callback: Optional[Callable] = None
        self.on_close_callback: Optional[Callable] = None
        self.on_error_callback: Optional[Callable] = None

    def _build_url(self) -> str:
        """Construit l'URL WebSocket selon la catégorie et l'environnement."""
        if self.category == "linear":
            return (
                "wss://stream-testnet.bybit.com/v5/public/linear"
                if self.testnet
                else "wss://stream.bybit.com/v5/public/linear"
            )
        else:
            return (
                "wss://stream-testnet.bybit.com/v5/public/inverse"
                if self.testnet
                else "wss://stream.bybit.com/v5/public/inverse"
            )

    def _on_open(self, ws):
        """Callback interne appelé à l'ouverture de la connexion."""
        # WebSocket ouverte

        # Enregistrer la connexion WebSocket
        record_ws_connection(connected=True)

        # Réinitialiser l'index de délai de reconnexion après une 
        # connexion réussie
        self.current_delay_index = 0

        # S'abonner aux tickers pour tous les symboles
        if self.symbols:
            subscribe_message = {
                "op": "subscribe",
                "args": [f"tickers.{symbol}" for symbol in self.symbols],
            }
            try:
                ws.send(json.dumps(subscribe_message))
                self.logger.info(
                    f"# Souscription tickers → {len(self.symbols)} symboles "
                    f"({self.category})"
                )
            except (json.JSONEncodeError, ConnectionError, OSError) as e:
                self.logger.error(
                    f"Erreur souscription WebSocket {self.category}: "
                    f"{type(e).__name__}: {e}"
                )
            except Exception as e:
                self.logger.warning(
                    f"⚠️ Erreur souscription {self.category}: {e}"
                )
        else:
            self.logger.warning(
                f"⚠️ Aucun symbole à suivre pour {self.category}"
            )

        # Appeler le callback externe si défini
        if self.on_open_callback:
            try:
                self.on_open_callback()
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur callback on_open: {e}")

    def _on_message(self, ws, message):
        """Callback interne appelé à chaque message reçu."""
        try:
            data = json.loads(message)
            if data.get("topic", "").startswith("tickers."):
                ticker_data = data.get("data", {})
                if ticker_data:
                    self.on_ticker_callback(ticker_data)
        except json.JSONDecodeError as e:
            self.logger.warning(f"⚠️ Erreur JSON ({self.category}): {e}")
        except (KeyError, TypeError, AttributeError) as e:
            self.logger.warning(
                f"⚠️ Erreur parsing données ({self.category}): "
                f"{type(e).__name__}: {e}"
            )
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur parsing ({self.category}): {e}")

    def _on_error(self, ws, error):
        """Callback interne appelé en cas d'erreur."""
        if self.running:
            self.logger.warning(f"⚠️ WS erreur ({self.category}) : {error}")
            record_ws_error()

            # Appeler le callback externe si défini
            if self.on_error_callback:
                try:
                    self.on_error_callback(error)
                except Exception as e:
                    self.logger.warning(f"⚠️ Erreur callback on_error: {e}")

    def _on_close(self, ws, close_status_code, close_msg):
        """Callback interne appelé à la fermeture."""
        if self.running:
            self.logger.info(
                f"🔌 WS fermée ({self.category}) "
                f"(code={close_status_code}, reason={close_msg})"
            )

            # Appeler le callback externe si défini
            if self.on_close_callback:
                try:
                    self.on_close_callback(close_status_code, close_msg)
                except Exception as e:
                    self.logger.warning(f"⚠️ Erreur callback on_close: {e}")

    def run(self):
        """
        Boucle principale avec reconnexion automatique et backoff progressif.

        Cette méthode bloque jusqu'à ce que close() soit appelé.
        """
        self.running = True

        while self.running:
            try:
                # Connexion à la WebSocket publique

                url = self._build_url()
                self.ws = websocket.WebSocketApp(
                    url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )

                self.ws.run_forever(
                    ping_interval=20, ping_timeout=15
                )  # Timeout ping augmenté de 10s à 15s

            except (ConnectionError, OSError, TimeoutError) as e:
                if self.running:
                    try:
                        self.logger.error(
                            f"Erreur connexion réseau WS publique "
                            f"({self.category}): "
                            f"{type(e).__name__}: {e}"
                        )
                    except Exception:
                        pass
            except Exception as e:
                if self.running:
                    try:
                        self.logger.error(
                            f"Erreur connexion WS publique "
                            f"({self.category}): {e}"
                        )
                    except Exception:
                        pass

            # Reconnexion avec backoff progressif
            if self.running:
                delay = self.reconnect_delays[
                    min(
                        self.current_delay_index,
                        len(self.reconnect_delays) - 1,
                    )
                ]
                try:
                    self.logger.warning(
                        f"🔁 WS publique ({self.category}) déconnectée "
                        f"→ reconnexion dans {delay}s"
                    )
                    record_ws_connection(
                        connected=False
                    )  # Enregistrer la reconnexion
                except Exception:
                    pass

                # Attendre le délai avec vérification périodique de l'arrêt
                # Utiliser time.sleep mais avec vérification plus fréquente
                # pour éviter les blocages
                for _ in range(delay * 10):  # 10 vérifications par seconde
                    if not self.running:
                        break
                    time.sleep(0.1)  # Vérification très fréquente (100ms)

                # Augmenter l'index de délai pour le prochain backoff
                # (jusqu'à la limite)
                if self.current_delay_index < len(self.reconnect_delays) - 1:
                    self.current_delay_index += 1
            else:
                break

    def close(self):
        """Ferme proprement la connexion WebSocket."""
        self.running = False

        # Fermer la WebSocket de manière plus agressive
        if self.ws:
            try:
                # Fermeture immédiate
                self.ws.close()
                # Attendre très peu pour que la fermeture se propage
                import time

                time.sleep(0.1)  # Augmenté pour permettre la fermeture
            except Exception:
                pass
            finally:
                # Forcer la fermeture si nécessaire
                try:
                    if hasattr(self.ws, "sock") and self.ws.sock:
                        self.ws.sock.close()
                except Exception:
                    pass

        # Nettoyer les références pour éviter les fuites mémoire
        self.ws = None
        self.on_ticker_callback = None
        self.on_open_callback = None
        self.on_close_callback = None
        self.on_error_callback = None

    def set_callbacks(
        self,
        on_open: Optional[Callable] = None,
        on_close: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ):
        """
        Définit des callbacks optionnels pour les événements de connexion.

        Args:
            on_open (Callable, optional): Appelé à l'ouverture de la connexion
            on_close (Callable, optional): Appelé à la fermeture (code, reason)
            on_error (Callable, optional): Appelé en cas d'erreur (error)
        """
        self.on_open_callback = on_open
        self.on_close_callback = on_close
        self.on_error_callback = on_error
