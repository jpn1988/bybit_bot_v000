#!/usr/bin/env python3
"""WebSocket privée Bybit v5 PRO - Runner persistant avec authentification et reconnexion."""

import os
import time
import json
import hmac
import hashlib
import threading
import signal
import websocket
from config import get_settings
from logging_setup import setup_logging


class PrivateWSRunner:
    """Runner WebSocket privée Bybit v5 avec authentification et reconnexion."""
    
    def __init__(self):
        self.logger = setup_logging()
        self.ws = None
        self.running = True
        self.connected = False
        self._authed = False
        self._auth_sent_at = 0
        
        # Configuration du signal handler pour Ctrl+C
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # Configuration
        settings = get_settings()
        self.testnet = settings['testnet']
        self.api_key = settings['api_key']
        self.api_secret = settings['api_secret']
        
        # Vérifier les clés API
        if not self.api_key or not self.api_secret:
            self.logger.error("⛔ Clés API manquantes : ajoute BYBIT_API_KEY et BYBIT_API_SECRET dans .env")
            exit(1)
        
        # Channels par défaut (configurable via env)
        default_channels = "wallet,order"
        env_channels = os.getenv("WS_PRIV_CHANNELS", default_channels)
        self.channels = [ch.strip() for ch in env_channels.split(",") if ch.strip()]
        
        # URL WebSocket
        if self.testnet:
            self.ws_url = "wss://stream-testnet.bybit.com/v5/private"
        else:
            self.ws_url = "wss://stream.bybit.com/v5/private"
        
        # Reconnexion
        self.reconnect_delays = [1, 2, 5, 10]  # secondes
        self.current_delay_index = 0
        
        self.logger.info("🚀 Démarrage WebSocket privée (runner)")
        self.logger.info(f"📂 Configuration chargée (testnet={self.testnet}, channels={self.channels})")
        self.logger.info(f"🔑 Clé API: {'présente' if self.api_key else 'absente'}")
    
    def _signal_handler(self, signum, frame):
        """Gestionnaire de signal pour Ctrl+C."""
        self.logger.info("🧹 Arrêt demandé par l'utilisateur (Ctrl+C)")
        self.close()
        exit(0)
    
    def _generate_ws_signature(self, expires_ms: int) -> str:
        """Génère la signature HMAC-SHA256 pour l'authentification WebSocket."""
        payload = f"GET/realtime{expires_ms}"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def on_open(self, ws):
        """Callback appelé à l'ouverture de la WebSocket."""
        self.logger.info(f"🌐 WS privée ouverte (testnet={self.testnet})")
        self.connected = True
        self._authed = False
        
        # Authentification immédiate avec signature WebSocket
        expires_ms = int((time.time() + 60) * 1000)  # 60s de marge
        signature = self._generate_ws_signature(expires_ms)
        
        auth_message = {
            "op": "auth",
            "args": [self.api_key, expires_ms, signature]
        }
        
        self.logger.info("🪪 Authentification en cours…")
        self.ws.send(json.dumps(auth_message))
        self._auth_sent_at = time.monotonic()
    
    def on_message(self, ws, message):
        """Callback appelé à chaque message reçu."""
        try:
            data = json.loads(message)
            
            # Gestion des pong
            if data.get("op") == "pong" or "pong" in str(data).lower():
                self.logger.info("↔️ Pong reçu")
                return
            
            # Gestion de l'authentification
            if data.get("op") == "auth":
                ret_code = data.get("retCode", -1)
                ret_msg = data.get("retMsg", "")
                success = data.get("success", False)
                
                if (success is True and data.get("op") == "auth") or (ret_code == 0 and data.get("op") == "auth"):
                    self.logger.info("✅ Authentification réussie")
                    self._authed = True
                    
                    # S'abonner aux channels
                    subscribe_message = {
                        "op": "subscribe",
                        "args": self.channels
                    }
                    self.ws.send(json.dumps(subscribe_message))
                    self.logger.info(f"🧭 Souscription privée → {self.channels}")
                else:
                    self.logger.error(f"⛔ Échec authentification WS : retCode={ret_code} retMsg=\"{ret_msg}\"")
                    self.ws.close()
                return
            
            # Gestion des souscriptions
            if data.get("op") == "subscribe" and data.get("success") is True:
                self.logger.info("✅ Souscription confirmée")
                return
            
            # Gestion des données de topics
            topic = data.get("topic", "")
            if topic == "wallet":
                self._handle_wallet_update(data)
            elif topic == "order":
                self._handle_order_update(data)
            else:
                # Message court pour debug
                message_preview = str(data)[:100] + "..." if len(str(data)) > 100 else str(data)
                self.logger.debug(f"ℹ️ Private msg: {message_preview}")
                
        except json.JSONDecodeError:
            self.logger.debug(f"Message brut reçu: {message[:100]}...")
        except Exception as e:
            self.logger.error(f"Erreur traitement message: {e}")
    
    def _handle_wallet_update(self, data):
        """Traite les mises à jour de wallet."""
        try:
            result = data.get("data", {})
            if isinstance(result, list) and result:
                account = result[0]
                total_equity = account.get("totalEquity", "N/A")
                total_wallet = account.get("totalWalletBalance", "N/A")
                self.logger.info(f"👛 Wallet update | totalEquity={total_equity} totalWalletBalance={total_wallet}")
        except Exception as e:
            self.logger.debug(f"Erreur parsing wallet: {e}")
    
    def _handle_order_update(self, data):
        """Traite les mises à jour d'ordre."""
        try:
            result = data.get("data", {})
            if isinstance(result, list) and result:
                order = result[0]
                symbol = order.get("symbol", "N/A")
                order_id = order.get("orderId", "N/A")
                status = order.get("orderStatus", "N/A")
                self.logger.info(f"📜 Order update | symbol={symbol} orderId={order_id} status={status}")
        except Exception as e:
            self.logger.debug(f"Erreur parsing order: {e}")
    
    def on_error(self, ws, error):
        """Callback appelé en cas d'erreur."""
        self.logger.error(f"Erreur WebSocket: {error}")
        self.connected = False
        self._authed = False
    
    def on_close(self, ws, close_status_code, close_msg):
        """Callback appelé à la fermeture."""
        self.logger.info("🔌 Connexion WebSocket fermée")
        self.connected = False
        self._authed = False
    
    def watchdog_loop(self):
        """Watchdog pour surveiller l'authentification."""
        while self.running:
            try:
                if (self.connected and not self._authed and 
                    time.monotonic() - self._auth_sent_at > 10):
                    self.logger.warning("⏳ Auth sans réponse (>10s) → redémarrage WS")
                    self.ws.close()
                
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Erreur watchdog: {e}")
                break
    
    def connect(self):
        """Se connecte à la WebSocket avec reconnexion automatique."""
        while self.running:
            try:
                self.logger.info("🔐 Connexion à la WebSocket privée…")
                
                # Créer la WebSocket
                self.ws = websocket.WebSocketApp(
                    self.ws_url,
                    on_open=self.on_open,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close
                )
                
                # Lancer la connexion avec heartbeat auto
                self.ws.run_forever(ping_interval=20, ping_timeout=10)
                
            except Exception as e:
                if self.running:  # Seulement logger si on n'est pas en train de s'arrêter
                    self.logger.error(f"Erreur connexion: {e}")
            
            # Reconnexion avec backoff seulement si on n'est pas en train de s'arrêter
            if self.running:
                delay = self.reconnect_delays[min(self.current_delay_index, len(self.reconnect_delays) - 1)]
                self.logger.warning(f"🔁 WS privée déconnectée → reconnexion dans {delay}s")
                
                # Attendre avec vérification périodique de self.running
                for _ in range(delay):
                    if not self.running:
                        break
                    time.sleep(1)
                
                # Augmenter le délai pour le prochain retry (max 10s)
                if self.current_delay_index < len(self.reconnect_delays) - 1:
                    self.current_delay_index += 1
            else:
                break
    
    def close(self):
        """Ferme proprement la WebSocket."""
        if self.running:  # Éviter les logs multiples
            self.logger.info("🧹 Arrêt demandé, fermeture de la WS…")
            self.running = False
            if self.ws:
                self.ws.close()
            self.logger.info("🏁 Runner WS privée arrêté")
    
    def run(self):
        """Lance le runner WebSocket."""
        try:
            # Lancer le watchdog en arrière-plan
            watchdog_thread = threading.Thread(target=self.watchdog_loop)
            watchdog_thread.daemon = True
            watchdog_thread.start()
            
            # Lancer la connexion (bloquant)
            self.connect()
            
        except Exception as e:
            if self.running:  # Seulement logger si on n'est pas en train de s'arrêter
                self.logger.error(f"Erreur runner: {e}")
                self.close()


def main():
    """Fonction principale."""
    runner = PrivateWSRunner()
    runner.run()


if __name__ == "__main__":
    main()
