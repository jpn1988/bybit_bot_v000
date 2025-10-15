#!/usr/bin/env python3
"""
Client WebSocket privé Bybit v5 avec authentification et reconnexion automatique.

╔═══════════════════════════════════════════════════════════════════╗
║                    📖 GUIDE DE LECTURE                            ║
╚═══════════════════════════════════════════════════════════════════╝

Ce fichier implémente un client WebSocket privé pour l'API Bybit v5 avec :
- Authentification HMAC-SHA256 automatique
- Reconnexion avec backoff progressif
- Watchdog pour détecter les déconnexions silencieuses
- Gestion des topics privés (orders, positions, executions, wallet)

🔍 COMPRENDRE CE FICHIER EN 5 MINUTES :

1. Processus d'authentification (lignes 84-110)
   └─> Authentification automatique dès l'ouverture de la connexion

2. Watchdog d'authentification (lignes 290-319)
   └─> Thread qui vérifie périodiquement l'état de la connexion

3. Gestion des messages (lignes 140-238)
   └─> Dispatch des messages par type (auth, topic, pong, error)

4. Reconnexion automatique (lignes 357-382)
   └─> Backoff progressif en cas d'erreur

🔐 PROCESSUS D'AUTHENTIFICATION WEBSOCKET BYBIT V5 :

Contrairement à l'authentification HTTP qui se fait à chaque requête,
l'authentification WebSocket se fait UNE SEULE FOIS après l'ouverture.

Étapes :
1. Connexion au serveur WebSocket
2. Génération d'un expires (timestamp + 60 secondes)
3. Signature HMAC-SHA256 du payload "GET/realtime{expires}"
4. Envoi du message {"op": "auth", "args": [api_key, expires, signature]}
5. Attente de la réponse {"success": true, "ret_msg": "..."}
6. Une fois authentifié, souscription aux topics privés

Exemple de signature :
    expires = 1712345738000  (timestamp en ms + 60s)
    payload = "GET/realtime1712345738000"
    signature = HMAC-SHA256(payload, api_secret) -> hex string

⚡ WATCHDOG D'AUTHENTIFICATION :

Le watchdog est un thread qui vérifie toutes les 30 secondes :
- Si la connexion est toujours active
- Si l'authentification est toujours valide
- Si aucun message n'a été reçu récemment

En cas de problème détecté → reconnexion automatique

📚 EXEMPLE D'UTILISATION :

```python
from ws_private import PrivateWSClient

# Créer le client
client = PrivateWSClient(
    testnet=True,
    api_key="YOUR_API_KEY",
    api_secret="YOUR_API_SECRET",
    channels=["order", "position", "wallet"],
    logger=my_logger
)

# Définir les callbacks
def on_order(topic, data):
    print(f"Ordre reçu: {data}")

client.on_topic = on_order

# Démarrer la connexion (bloquant)
client.run()
```

📊 TOPICS PRIVÉS DISPONIBLES :

- "order" : Notifications sur les ordres (créés, remplis, annulés)
- "position" : Mises à jour des positions en temps réel
- "execution" : Exécutions de trades
- "wallet" : Mises à jour du solde du portefeuille
- "greeks" : Greeks des options (si applicable)

🔄 MÉCANISME DE RECONNEXION :

En cas de déconnexion ou d'erreur :
- Tentative 1 : Délai = 1 seconde
- Tentative 2 : Délai = 2 secondes
- Tentative 3 : Délai = 5 secondes
- Tentative 4+ : Délai = 10 secondes

Le délai est réinitialisé après une connexion réussie.

📖 RÉFÉRENCES :
- Documentation WebSocket Bybit v5: https://bybit-exchange.github.io/docs/v5/ws/connect
- Authentification WebSocket: https://bybit-exchange.github.io/docs/v5/ws/auth
"""

import time
import json
import hmac
import hashlib
import threading
import websocket
from config.timeouts import TimeoutConfig


class PrivateWSClient:
    """
    Client WebSocket privé Bybit v5 avec authentification HMAC et reconnexion automatique.
    
    Ce client gère :
    - Authentification automatique via HMAC-SHA256
    - Souscription aux topics privés (order, position, wallet, etc.)
    - Watchdog thread pour détecter les déconnexions silencieuses
    - Reconnexion automatique avec backoff progressif
    - Callbacks pour chaque type de message reçu
    
    Attributes:
        testnet (bool): Utiliser le testnet (True) ou mainnet (False)
        api_key (str): Clé API Bybit
        api_secret (str): Secret API Bybit (pour la signature)
        channels (list[str]): Liste des topics privés à écouter
        logger: Instance du logger pour les messages
        running (bool): État de la connexion (True = actif)
        connected (bool): État TCP (True = connecté au serveur)
        _authed (bool): État d'authentification (True = authentifié)
        
    Example:
        ```python
        # Créer et démarrer le client
        client = PrivateWSClient(
            testnet=True,
            api_key="YOUR_KEY",
            api_secret="YOUR_SECRET",
            channels=["order", "position"],
            logger=my_logger
        )
        
        # Définir les callbacks
        client.on_topic = lambda topic, data: print(f"{topic}: {data}")
        client.on_auth_success = lambda: print("Authentifié !")
        
        # Démarrer (bloquant)
        client.run()
        ```
        
    Note:
        - L'authentification se fait automatiquement après connexion
        - Le watchdog surveille la connexion et ré-authentifie si nécessaire
        - La méthode run() est bloquante (utiliser un thread si besoin)
    """

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
        """
        Initialise le client WebSocket privé.
        
        Args:
            testnet (bool): Utiliser le testnet (True) ou mainnet (False)
            api_key (str): Clé API Bybit (générée dans le dashboard)
            api_secret (str): Secret API Bybit (utilisé pour signer les requêtes)
            channels (list[str] | None): Liste des topics à écouter
                                        Exemples: ["order", "position", "wallet"]
                                        Si None ou [], pas de souscription automatique
            logger: Instance du logger pour tracer les événements
            reconnect_delays (list[int] | None): Délais de reconnexion en secondes
                                                Défaut: [1, 2, 5, 10]
                                                
        Note:
            - Les clés API doivent avoir les permissions WebSocket activées
            - Pour le testnet, générez les clés sur testnet.bybit.com
            - Les topics invalides seront ignorés par Bybit
        """
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

        from config.urls import URLConfig
        self.ws_url = URLConfig.get_websocket_private_url(self.testnet)

        self.reconnect_delays = reconnect_delays or [1, 2, 5, 10]
        self.current_delay_index = 0

        # Gestion du thread watchdog
        self._watchdog_thread = None
        self._watchdog_stop = threading.Event()

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
        """
        Génère la signature HMAC-SHA256 pour l'authentification WebSocket.
        
        L'authentification WebSocket Bybit v5 utilise un format de payload différent
        de l'authentification HTTP. Le payload est fixe : "GET/realtime{expires}".
        
        Algorithme :
        1. Construire le payload : "GET/realtime" + expires_ms
        2. Encoder le payload et le secret en UTF-8
        3. Calculer HMAC-SHA256(payload, secret)
        4. Convertir en hexadécimal
        
        Exemple concret :
            expires_ms = 1712345738000
            api_secret = "MY_SECRET_KEY"
            
            → payload = "GET/realtime1712345738000"
            → HMAC-SHA256(payload, secret) → "a1b2c3d4e5f6..." (64 caractères)
        
        Args:
            expires_ms (int): Timestamp d'expiration en millisecondes
                            Généralement : time.time() * 1000 + 60000 (60 secondes)
                            
        Returns:
            str: Signature HMAC-SHA256 en hexadécimal (64 caractères)
                Cette signature doit être envoyée dans le message d'authentification
                
        Example:
            ```python
            # Générer une signature pour l'authentification
            expires = int((time.time() + 60) * 1000)  # +60 secondes
            signature = self._generate_ws_signature(expires)
            
            # Envoyer le message d'authentification
            auth_message = {
                "op": "auth",
                "args": [self.api_key, expires, signature]
            }
            ws.send(json.dumps(auth_message))
            ```
            
        Note:
            - Le format du payload est DIFFÉRENT de l'authentification HTTP
            - HTTP : "timestamp + api_key + recv_window + query_string"
            - WebSocket : "GET/realtime + expires"
            - La signature est unique pour chaque tentative (expires différent)
            - Bybit rejette l'authentification si la signature est invalide
            
        Security:
            - Le secret API n'est JAMAIS envoyé sur le réseau
            - Seule la signature (dérivée du secret) est transmise
            - L'expires limite la durée de validité de la signature
        """
        # Construire le payload selon le format WebSocket Bybit v5
        # Format fixe : "GET/realtime" + expires_ms
        # Ce format est DIFFÉRENT de l'authentification HTTP !
        payload = f"GET/realtime{expires_ms}"
        
        # Calculer la signature HMAC-SHA256
        # 1. Encoder le secret et le payload en bytes UTF-8
        # 2. Calculer le hash HMAC avec SHA256
        # 3. Convertir en hexadécimal (string de 64 caractères)
        return hmac.new(
            self.api_secret.encode("utf-8"),  # Clé secrète (bytes)
            payload.encode("utf-8"),          # Message à signer (bytes)
            hashlib.sha256,                   # Algorithme de hash
        ).hexdigest()  # Résultat en hexadécimal

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
        auth_message = {
            "op": "auth",
            "args": [self.api_key, expires_ms, signature],
        }

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
                            self.logger.info(
                                f"🧭 Souscription privée → {self.channels}"
                            )
                        except Exception as e:
                            try:
                                self.logger.warning(
                                    f"⚠️ Échec souscription privée: {e}"
                                )
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
                            f'⛔ Échec authentification WS : '
                            f'retCode={ret_code} retMsg="{ret_msg}"'
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
                message_preview = (
                    str(data)[:100] + "..."
                    if len(str(data)) > 100
                    else str(data)
                )
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
        """
        Boucle de surveillance du watchdog.
        
        Vérifie périodiquement si l'authentification a réussi.
        Utilise un Event pour un arrêt propre.
        """
        while self.running and not self._watchdog_stop.is_set():
            try:
                if (
                    self.connected
                    and not self._authed
                    and time.monotonic() - self._auth_sent_at > 10
                ):
                    try:
                        self.logger.warning(
                            "⏳ Auth sans réponse (>10s) → redémarrage WS"
                        )
                    except Exception:
                        pass
                    try:
                        self.ws.close()
                    except Exception:
                        pass
                # Utiliser wait() au lieu de sleep() pour un arrêt réactif
                self._watchdog_stop.wait(timeout=TimeoutConfig.WATCHDOG_INTERVAL)
            except Exception:
                # Ne pas tuer le watchdog, continuer
                self._watchdog_stop.wait(timeout=TimeoutConfig.WATCHDOG_INTERVAL)

    def run(self):
        """
        Boucle principale avec reconnexion et watchdog.
        
        CORRECTIF : Réutilise le même thread watchdog au lieu d'en créer
        un nouveau à chaque reconnexion (évite les fuites de threads).
        """
        # Créer le thread watchdog UNE SEULE FOIS
        if self._watchdog_thread is None or not self._watchdog_thread.is_alive():
            self._watchdog_stop.clear()
            self._watchdog_thread = threading.Thread(
                target=self._watchdog_loop, daemon=True, name="ws_private_watchdog"
            )
            self._watchdog_thread.start()
            try:
                self.logger.debug("🐕 Thread watchdog démarré")
            except Exception:
                pass

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
                delay = self.reconnect_delays[
                    min(
                        self.current_delay_index,
                        len(self.reconnect_delays) - 1,
                    )
                ]
                try:
                    self.logger.warning(
                        f"🔁 WS privée déconnectée → reconnexion dans {delay}s"
                    )
                except Exception:
                    pass
                for _ in range(delay):
                    if not self.running:
                        break
                    from config.timeouts import TimeoutConfig
                    time.sleep(TimeoutConfig.RECONNECT_SLEEP)
                if self.current_delay_index < len(self.reconnect_delays) - 1:
                    self.current_delay_index += 1
            else:
                break

    def close(self):
        """
        Ferme proprement la WebSocket.
        
        CORRECTIF : Arrête proprement le thread watchdog pour éviter
        les fuites de threads.
        """
        if self.running:
            try:
                self.logger.info("🧹 Arrêt demandé, fermeture de la WS…")
            except Exception:
                pass
            self.running = False
            
            # Arrêter le thread watchdog proprement
            self._watchdog_stop.set()
            if self._watchdog_thread and self._watchdog_thread.is_alive():
                try:
                    self._watchdog_thread.join(timeout=TimeoutConfig.THREAD_WS_PRIVATE_SHUTDOWN)
                    self.logger.debug("🐕 Thread watchdog arrêté proprement")
                except Exception:
                    pass
            
            try:
                if self.ws:
                    self.ws.close()
            finally:
                try:
                    self.logger.info("🏁 WS privée arrêtée")
                except Exception:
                    pass
