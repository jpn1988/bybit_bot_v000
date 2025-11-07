#!/usr/bin/env python3
"""
Client WebSocket publique Bybit v5 avec reconnexion automatique.

╔═══════════════════════════════════════════════════════════════════╗
║                    📖 GUIDE DE LECTURE                            ║
╚═══════════════════════════════════════════════════════════════════╝

Ce fichier implémente un client WebSocket publique pour l'API Bybit v5 avec :
- Connexion automatique aux endpoints publics (tickers, orderbook, trades)
- Souscription automatique aux symboles
- Reconnexion avec backoff progressif
- Gestion des erreurs et timeouts
- Callbacks personnalisables

🔍 COMPRENDRE CE FICHIER EN 5 MINUTES :

1. Connexion et souscription (lignes 71-98)
   └─> Ouverture de la connexion et souscription aux tickers

2. Gestion des messages (lignes 146-203)
   └─> Parsing et dispatch des messages reçus

3. Reconnexion automatique (lignes 239-279)
   └─> Backoff progressif en cas d'erreur

4. Callbacks personnalisables (lignes 51-54)
   └─> Hooks pour événements (ouverture, fermeture, erreur)

📡 ENDPOINTS WEBSOCKET PUBLICS BYBIT V5 :

Format des URLs :
- Testnet linear: wss://stream-testnet.bybit.com/v5/public/linear
- Mainnet linear: wss://stream.bybit.com/v5/public/linear
- Testnet inverse: wss://stream-testnet.bybit.com/v5/public/inverse
- Mainnet inverse: wss://stream.bybit.com/v5/public/inverse

Topics disponibles :
- "tickers.{symbol}" : Prix en temps réel (lastPrice, bid1, ask1, volume24h)
- "orderbook.{depth}.{symbol}" : Carnet d'ordres (depth: 1, 50, 200, 500)
- "publicTrade.{symbol}" : Trades publics en temps réel
- "kline.{interval}.{symbol}" : Bougies (interval: 1, 3, 5, 15, 30, 60, etc.)

🔄 MÉCANISME DE RECONNEXION AVEC BACKOFF PROGRESSIF :

Le backoff progressif évite de surcharger le serveur en cas d'erreur.
Les délais augmentent à chaque tentative échouée :

- Tentative 1 : Délai = 1 seconde
- Tentative 2 : Délai = 2 secondes
- Tentative 3 : Délai = 5 secondes
- Tentative 4 : Délai = 10 secondes
- Tentative 5+ : Délai = 30 secondes (max)

Le délai est réinitialisé à 0 après une connexion réussie.

Pourquoi le backoff progressif ?
- ✅ Évite de spammer le serveur avec des reconnexions rapides
- ✅ Laisse le temps au serveur de se rétablir
- ✅ Réduit la charge réseau
- ✅ Augmente les chances de succès

📚 EXEMPLE D'UTILISATION :

```python
from ws_public import PublicWSClient

# Créer le client
def on_ticker(data):
    symbol = data.get("symbol")
    price = data.get("lastPrice")
    print(f"{symbol}: ${price}")

client = PublicWSClient(
    category="linear",
    symbols=["BTCUSDT", "ETHUSDT"],
    testnet=True,
    logger=my_logger,
    on_ticker_callback=on_ticker
)

# Démarrer (bloquant)
client.run()
```

📊 FORMAT DES MESSAGES REÇUS :

Message ticker :
```json
{
    "topic": "tickers.BTCUSDT",
    "type": "snapshot",
    "data": {
        "symbol": "BTCUSDT",
        "lastPrice": "43500.50",
        "bid1Price": "43500.00",
        "ask1Price": "43501.00",
        "volume24h": "12345.67",
        "turnover24h": "537000000"
    },
    "ts": 1712345678000
}
```

Message subscription confirmation :
```json
{
    "success": true,
    "ret_msg": "subscribe",
    "conn_id": "...",
    "op": "subscribe"
}
```

📖 RÉFÉRENCES :
- Documentation WebSocket Bybit v5: https://bybit-exchange.github.io/docs/v5/ws/connect
- Topics publics: https://bybit-exchange.github.io/docs/v5/ws/public/ticker
"""

import json
import time
import websocket
from typing import Callable, List, Optional
from enhanced_metrics import record_ws_connection, record_ws_error
from ws.public.subscriptions import SubscriptionBuilder
from ws.public.parser_router import PublicMessageRouter
from ws.public.transport import BackoffTransport


class PublicWSClient:
    """
    Client WebSocket publique Bybit v5 avec reconnexion automatique.

    Ce client gère automatiquement :
    - Connexion au serveur WebSocket Bybit
    - Souscription aux topics publics (tickers, orderbook, trades, klines)
    - Reconnexion automatique avec backoff progressif
    - Parsing et dispatch des messages reçus
    - Gestion des erreurs et timeouts

    Attributes:
        category (str): Catégorie des symboles ("linear" ou "inverse")
        symbols (List[str]): Liste des symboles à suivre
        testnet (bool): Utiliser le testnet (True) ou mainnet (False)
        logger: Instance du logger pour tracer les événements
        on_ticker_callback (Callable): Fonction appelée pour chaque ticker reçu
        ws (WebSocketApp): Instance WebSocket sous-jacente
        running (bool): État de la connexion
        reconnect_delays (List[int]): Délais de reconnexion progressifs [1, 2, 5, 10, 30]
        current_delay_index (int): Index du délai actuel (réinitialisé après succès)

    Example:
        ```python
        # Exemple simple : suivre 2 symboles
        def on_ticker(data):
            print(f"{data['symbol']}: ${data['lastPrice']}")

        client = PublicWSClient(
            category="linear",
            symbols=["BTCUSDT", "ETHUSDT"],
            testnet=True,
            logger=my_logger,
            on_ticker_callback=on_ticker
        )

        # Démarrer (bloquant)
        client.run()
        ```

    Note:
        - La méthode run() est bloquante (utiliser un thread si nécessaire)
        - Le backoff progressif évite de spammer le serveur
        - Les callbacks sont appelés dans le thread WebSocket
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
            category (str): Catégorie des symboles
                          - "linear" : Contrats USDT perpetual (BTCUSDT, ETHUSDT, etc.)
                          - "inverse" : Contrats inverse (BTCUSD, ETHUSD, etc.)
            symbols (List[str]): Liste des symboles à suivre en temps réel
                               Exemples: ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
                               Max recommandé: ~100 symboles par connexion
            testnet (bool): Environnement à utiliser
                          - True : Testnet (api-testnet.bybit.com)
                          - False : Mainnet (api.bybit.com)
            logger: Instance du logger pour tracer les événements
                   Recommandé: logging.getLogger(__name__)
            on_ticker_callback (Callable[[dict], None]): Fonction appelée pour chaque ticker
                                                        Signature: callback(ticker_data: dict) -> None

        Note:
            - Les symboles invalides seront ignorés par Bybit
            - Le callback doit être rapide (non-bloquant)
            - Pour des traitements lourds, utiliser une queue
        """
        self.category = category
        self.symbols = symbols
        self.testnet = testnet
        self.logger = logger
        self.on_ticker_callback = on_ticker_callback
        self.ws: Optional[websocket.WebSocketApp] = None
        self.running = False

        # Configuration de reconnexion avec backoff progressif
        # Les délais augmentent à chaque échec pour éviter de spammer le serveur
        # [1, 2, 5, 10, 30] signifie : 1s, puis 2s, puis 5s, puis 10s, puis 30s (max)
        # Le current_delay_index est réinitialisé à 0 après une connexion réussie
        self.reconnect_delays = [1, 2, 5, 10, 30]  # secondes
        self.current_delay_index = 0  # Commence au premier délai (1s)
        self._transport = BackoffTransport(self.reconnect_delays)
        self._router = PublicMessageRouter(on_ticker=self.on_ticker_callback)

        # Callbacks optionnels pour événements de connexion
        self.on_open_callback: Optional[Callable] = None
        self.on_close_callback: Optional[Callable] = None
        self.on_error_callback: Optional[Callable] = None

    def _build_url(self) -> str:
        """Construit l'URL WebSocket selon la catégorie et l'environnement."""
        from config.urls import URLConfig
        return URLConfig.get_websocket_url(self.category, self.testnet)

    def _on_open(self, ws):
        """
        Callback appelé automatiquement à l'ouverture de la connexion WebSocket.

        Cette méthode :
        1. Enregistre la connexion dans les métriques
        2. Réinitialise le backoff progressif (connexion réussie)
        3. Souscrit automatiquement aux topics tickers pour tous les symboles
        4. Appelle le callback personnalisé si défini

        Args:
            ws: Instance WebSocketApp (fournie automatiquement par websocket-client)
        """
        # Enregistrer la connexion réussie dans les métriques
        record_ws_connection(connected=True)

        # ✅ SUCCÈS : Réinitialiser le backoff progressif
        # Après une connexion réussie, on recommence avec le délai le plus court (1s)
        # Cela permet de réagir rapidement en cas de nouvelle déconnexion
        self.current_delay_index = 0

        # S'abonner aux tickers pour tous les symboles (via builder dédié)
        if self.symbols:
            subscribe_message = SubscriptionBuilder.tickers(self.symbols)
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
        # Déléguer parsing + dispatch au routeur
        self._router.route(message, self.logger, self.category)

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

        CORRECTIF : Entoure tout d'un try/finally pour garantir le nettoyage
        des callbacks même en cas d'exception.
        """
        self.running = True

        try:
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

                # ❌ ÉCHEC DE CONNEXION : Appliquer le backoff progressif via transport
                if self.running:
                    try:
                        self.logger.warning(
                            f"🔁 WS publique ({self.category}) déconnectée "
                            f"→ backoff (tentative #{self.current_delay_index + 1})"
                        )
                        record_ws_connection(connected=False)
                    except Exception:
                        pass

                    self.current_delay_index = self._transport.wait(
                        self.current_delay_index,
                        is_running_callable=lambda: self.running,
                    )
                else:
                    break
        finally:
            # CORRECTIF : Garantir le nettoyage même en cas d'exception
            self._cleanup()

    def _cleanup(self):
        """
        Nettoie toutes les ressources (WebSocket et callbacks).

        CORRECTIF : Méthode centralisée pour garantir le nettoyage
        même en cas d'exception dans run().
        """
        # Fermer la WebSocket si elle existe
        if self.ws:
            try:
                # Fermeture immédiate
                self.ws.close()
                # Attendre très peu pour que la fermeture se propage
                from config.timeouts import TimeoutConfig
                time.sleep(TimeoutConfig.SHORT_SLEEP)
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

    def close(self):
        """
        Ferme proprement la connexion WebSocket.

        CORRECTIF : Utilise _cleanup() pour garantir le nettoyage.
        """
        self.running = False
        self._cleanup()

