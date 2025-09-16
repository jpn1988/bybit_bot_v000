#!/usr/bin/env python3
# NOTE: orchestrateur principal = src/bot.py
"""Orchestrateur pro pour supervision des connexions Bybit (REST + WebSocket public + WebSocket privé)."""

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
from bybit_client import BybitClient, BybitPublicClient
from instruments import get_perp_symbols


class Orchestrator:
    """Orchestrateur pour supervision des connexions Bybit."""
    
    def __init__(self):
        self.logger = setup_logging()
        self.running = True
        
        # Configuration
        settings = get_settings()
        self.testnet = settings['testnet']
        self.api_key = settings['api_key']
        self.api_secret = settings['api_secret']
        
        # États des connexions
        self.rest_status = "UNKNOWN"
        self.ws_public_status = "DISCONNECTED"
        self.ws_private_status = "DISCONNECTED"
        
        # États précédents pour détecter les changements
        self.prev_rest_status = "UNKNOWN"
        self.prev_ws_public_status = "DISCONNECTED"
        self.prev_ws_private_status = "DISCONNECTED"
        
        # WebSocket instances
        self.ws_public = None
        self.ws_private = None
        
        # Threads
        self.ws_public_thread = None
        self.ws_private_thread = None
        
        # Reconnexion
        self.reconnect_delays = [1, 2, 5, 10]  # secondes
        
        # Configuration du signal handler pour Ctrl+C
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # Channels privés par défaut (configurable via env WS_PRIV_CHANNELS)
        import os
        default_channels = "wallet,order"
        env_channels = os.getenv("WS_PRIV_CHANNELS", default_channels)
        self.ws_private_channels = [ch.strip() for ch in env_channels.split(",") if ch.strip()]

        self.logger.info("🚀 Lancement orchestrateur (REST + WS public + WS privé)")
        self.logger.info(f"📂 Configuration chargée (testnet={self.testnet})")
    
    def _signal_handler(self, signum, frame):
        """Gestionnaire de signal pour Ctrl+C."""
        self.logger.info("🧹 Arrêt demandé, fermeture des connexions…")
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
    
    def check_rest_private(self):
        """Vérifie la connexion REST privée."""
        if not self.api_key or not self.api_secret:
            self.logger.warning("⛔ Clés API manquantes pour REST privé")
            self.rest_status = "KO"
            return
        
        try:
            client = BybitClient(
                testnet=self.testnet,
                timeout=10,
                api_key=self.api_key,
                api_secret=self.api_secret
            )
            
            # Test simple d'authentification
            client.get_wallet_balance("UNIFIED")
            self.logger.info("✅ REST privé OK (auth valide)")
            self.rest_status = "OK"
            
        except Exception as e:
            error_msg = str(e)[:100] + "..." if len(str(e)) > 100 else str(e)
            self.logger.error(f"⛔ REST privé KO : {error_msg}")
            self.rest_status = "KO"
    
    def ws_public_on_open(self, ws):
        """Callback ouverture WebSocket publique."""
        self.logger.info("🌐 WS publique ouverte")
        self.ws_public_status = "CONNECTED"
    
    def ws_public_on_message(self, ws, message):
        """Callback message WebSocket publique."""
        # Ignorer silencieusement les messages (ping/pong auto)
        pass
    
    def ws_public_on_error(self, ws, error):
        """Callback erreur WebSocket publique."""
        self.logger.warning(f"⚠️ WS publique erreur : {error}")
        self.ws_public_status = "DISCONNECTED"
    
    def ws_public_on_close(self, ws, close_status_code, close_msg):
        """Callback fermeture WebSocket publique."""
        self.logger.info(f"🔌 WS publique fermée (code={close_status_code}, reason={close_msg})")
        self.ws_public_status = "DISCONNECTED"
    
    def ws_private_on_open(self, ws):
        """Callback ouverture WebSocket privée."""
        self.logger.info("🌐 WS privée ouverte")
        self.ws_private_status = "CONNECTED"
        
        # Authentification immédiate
        expires_ms = int((time.time() + 60) * 1000)
        signature = self._generate_ws_signature(expires_ms)
        
        auth_message = {
            "op": "auth",
            "args": [self.api_key, expires_ms, signature]
        }
        
        self.logger.info("🪪 Authentification en cours…")
        ws.send(json.dumps(auth_message))
    
    def ws_private_on_message(self, ws, message):
        """Callback message WebSocket privée."""
        try:
            data = json.loads(message)
            
            # Gestion de l'authentification
            if data.get("op") == "auth":
                ret_code = data.get("retCode", -1)
                ret_msg = data.get("retMsg", "")
                success = data.get("success", False)
                
                if (success is True and data.get("op") == "auth") or (ret_code == 0 and data.get("op") == "auth"):
                    self.logger.info("✅ Authentification WS privée réussie")
                    # Resubscribe automatique aux topics privés configurés
                    if self.ws_private_channels:
                        sub_msg = {"op": "subscribe", "args": self.ws_private_channels}
                        try:
                            ws.send(json.dumps(sub_msg))
                            self.logger.info(f"🧭 Souscription privée → {self.ws_private_channels}")
                        except Exception as e:
                            self.logger.warning(f"⚠️ Échec souscription privée: {e}")
                else:
                    self.logger.error(f"⛔ Auth WS privée échouée : retCode={ret_code} retMsg=\"{ret_msg}\"")
                    ws.close()
            
            # Gestion des pong
            elif data.get("op") == "pong":
                self.logger.info("↔️ Pong reçu (privé)")
            
            # Autres messages
            else:
                message_preview = str(data)[:50] + "..." if len(str(data)) > 50 else str(data)
                self.logger.debug(f"WS privée: {message_preview}")
                
        except json.JSONDecodeError:
            self.logger.debug(f"Message brut WS privée: {message[:50]}...")
        except Exception as e:
            self.logger.debug(f"Erreur parsing WS privée: {e}")
    
    def ws_private_on_error(self, ws, error):
        """Callback erreur WebSocket privée."""
        self.logger.warning(f"⚠️ WS privée erreur : {error}")
        self.ws_private_status = "DISCONNECTED"
    
    def ws_private_on_close(self, ws, close_status_code, close_msg):
        """Callback fermeture WebSocket privée."""
        self.logger.info(f"🔌 WS privée fermée (code={close_status_code}, reason={close_msg})")
        self.ws_private_status = "DISCONNECTED"
    
    def ws_public_runner(self):
        """Runner WebSocket publique avec reconnexion."""
        url = "wss://stream-testnet.bybit.com/v5/public/linear" if self.testnet else "wss://stream.bybit.com/v5/public/linear"
        delay_index = 0
        
        while self.running:
            try:
                self.ws_public = websocket.WebSocketApp(
                    url,
                    on_open=self.ws_public_on_open,
                    on_message=self.ws_public_on_message,
                    on_error=self.ws_public_on_error,
                    on_close=self.ws_public_on_close
                )
                
                self.ws_public.run_forever(ping_interval=20, ping_timeout=10)
                
            except Exception as e:
                if self.running:
                    self.logger.error(f"Erreur WS publique: {e}")
            
            # Reconnexion avec backoff
            if self.running:
                delay = self.reconnect_delays[min(delay_index, len(self.reconnect_delays) - 1)]
                self.logger.warning(f"🔁 WS publique déconnectée → reconnexion dans {delay}s")
                
                for _ in range(delay):
                    if not self.running:
                        break
                    time.sleep(1)
                
                if delay_index < len(self.reconnect_delays) - 1:
                    delay_index += 1
            else:
                break
    
    def ws_private_runner(self):
        """Runner WebSocket privée avec reconnexion."""
        url = "wss://stream-testnet.bybit.com/v5/private" if self.testnet else "wss://stream.bybit.com/v5/private"
        delay_index = 0
        
        while self.running:
            try:
                self.ws_private = websocket.WebSocketApp(
                    url,
                    on_open=self.ws_private_on_open,
                    on_message=self.ws_private_on_message,
                    on_error=self.ws_private_on_error,
                    on_close=self.ws_private_on_close
                )
                
                self.ws_private.run_forever(ping_interval=20, ping_timeout=10)
                
            except Exception as e:
                if self.running:
                    self.logger.error(f"Erreur WS privée: {e}")
            
            # Reconnexion avec backoff
            if self.running:
                delay = self.reconnect_delays[min(delay_index, len(self.reconnect_delays) - 1)]
                self.logger.warning(f"🔁 WS privée déconnectée → reconnexion dans {delay}s")
                
                for _ in range(delay):
                    if not self.running:
                        break
                    time.sleep(1)
                
                if delay_index < len(self.reconnect_delays) - 1:
                    delay_index += 1
            else:
                break
    
    def health_check_loop(self):
        """Boucle de health-check périodique."""
        while self.running:
            # Vérifier s'il y a des changements d'état
            rest_changed = self.rest_status != self.prev_rest_status
            ws_public_changed = self.ws_public_status != self.prev_ws_public_status
            ws_private_changed = self.ws_private_status != self.prev_ws_private_status
            
            # Afficher seulement s'il y a des changements
            if rest_changed or ws_public_changed or ws_private_changed:
                self.logger.info(f"🩺 Health | REST={self.rest_status} | WS_publique={self.ws_public_status} | WS_privée={self.ws_private_status}")
                
                # Mettre à jour les états précédents
                self.prev_rest_status = self.rest_status
                self.prev_ws_public_status = self.ws_public_status
                self.prev_ws_private_status = self.ws_private_status
            
            # Attendre 5 minutes (300 secondes)
            for _ in range(300):
                if not self.running:
                    break
                time.sleep(1)
    
    def start(self):
        """Démarre l'orchestrateur."""
        # 1. Vérification REST privé
        self.check_rest_private()
        
        # 2. Détection de l'univers perp
        try:
            # Créer un client PUBLIC pour récupérer l'URL publique (aucune clé requise)
            temp_client = BybitPublicClient(
                testnet=self.testnet,
                timeout=10,
            )
            base_url = temp_client.public_base_url()
            
            self.logger.info("🗺️ Détection de l'univers perp en cours…")
            data = get_perp_symbols(base_url, timeout=10)
            
            self.logger.info(f"✅ Perp USDT (linear) détectés : {len(data['linear'])}")
            self.logger.info(f"✅ Perp coin-margined (inverse) détectés : {len(data['inverse'])}")
            self.logger.info(f"📊 Univers perp total : {data['total']}")
            
        except Exception as err:
            self.logger.warning(f"⚠️ Impossible de détecter l'univers perp (on continue) : {err}")
        
        # 3. Démarrage WebSocket publique
        self.logger.info("🔌 Démarrage WS publique…")
        self.ws_public_thread = threading.Thread(target=self.ws_public_runner)
        self.ws_public_thread.daemon = True
        self.ws_public_thread.start()
        
        # 4. Démarrage WebSocket privée
        self.logger.info("🔌 Démarrage WS privée…")
        self.ws_private_thread = threading.Thread(target=self.ws_private_runner)
        self.ws_private_thread.daemon = True
        self.ws_private_thread.start()
        
        # 5. Attendre un peu pour que les connexions s'établissent
        time.sleep(3)
        
        # 6. Afficher l'état initial
        self.logger.info(f"🩺 Health | REST={self.rest_status} | WS_publique={self.ws_public_status} | WS_privée={self.ws_private_status}")
        self.prev_rest_status = self.rest_status
        self.prev_ws_public_status = self.ws_public_status
        self.prev_ws_private_status = self.ws_private_status
        
        # 7. Health-check dans le thread principal
        self.health_check_loop()
    
    def close(self):
        """Ferme proprement toutes les connexions."""
        if self.running:
            self.running = False
            
            # Fermer les WebSockets
            if self.ws_public:
                self.ws_public.close()
            if self.ws_private:
                self.ws_private.close()
            
            self.logger.info("🏁 Orchestrateur arrêté")


def main():
    """Fonction principale."""
    orchestrator = Orchestrator()
    try:
        orchestrator.start()
    except Exception as e:
        orchestrator.logger.error(f"Erreur orchestrateur: {e}")
        orchestrator.close()


if __name__ == "__main__":
    main()
