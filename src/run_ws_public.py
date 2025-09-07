#!/usr/bin/env python3
"""Script de test pour la connexion WebSocket publique Bybit v5."""

import time
import signal
import sys
import json
import threading
import websocket
from config import get_settings
from logging_setup import setup_logging


class WebSocketTest:
    """Test de connexion WebSocket publique Bybit."""
    
    def __init__(self):
        self.logger = setup_logging()
        self.ws = None
        self.running = True
        self.connection_open = False
        
    def on_message(self, ws, message):
        """Callback appelé à chaque message reçu."""
        # Ignorer silencieusement les messages (ping/pong et autres)
        pass
    
    def on_error(self, ws, error):
        """Callback appelé en cas d'erreur."""
        self.logger.error(f"Erreur WebSocket: {error}")
        self.running = False
    
    def on_close(self, ws, close_status_code, close_msg):
        """Callback appelé à la fermeture."""
        self.logger.info("🔌 Connexion WebSocket fermée")
        self.connection_open = False
    
    def on_open(self, ws):
        """Callback appelé à l'ouverture."""
        self.logger.info(f"🌐 Connexion WebSocket publique ouverte (testnet={self.testnet}) - Ping/pong en place")
        self.connection_open = True
    
    def signal_handler(self, signum, frame):
        """Gestionnaire pour Ctrl+C."""
        self.logger.info("🧹 Arrêt demandé, fermeture…")
        self.running = False
        if self.ws:
            self.ws.close()
        sys.exit(0)
    
    def ping_loop(self):
        """Boucle de ping toutes les 15 secondes."""
        while self.running and self.connection_open:
            try:
                # Envoyer ping silencieusement
                ping_message = json.dumps({"op": "ping"})
                self.ws.send(ping_message)
                
                # Attendre 15 secondes
                for _ in range(15):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                self.logger.error(f"Erreur lors de l'envoi du ping: {e}")
                self.running = False
                break
    
    def run(self):
        """Lance le test WebSocket."""
        # Étape 1: Lancement
        self.logger.info("🚀 Lancement du test WebSocket (public)")
        
        # Étape 2: Configuration
        settings = get_settings()
        self.testnet = settings['testnet']
        
        # Déterminer l'URL selon l'environnement
        if self.testnet:
            url = "wss://stream-testnet.bybit.com/v5/public/linear"
        else:
            url = "wss://stream.bybit.com/v5/public/linear"
        
        self.logger.info(f"URL WebSocket: {url}")
        
        # Étape 3: Configuration du gestionnaire de signal
        signal.signal(signal.SIGINT, self.signal_handler)
        
        # Étape 4: Ouvrir la connexion
        try:
            self.ws = websocket.WebSocketApp(
                url,
                on_open=self.on_open,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close
            )
            
            # Lancer la connexion en arrière-plan
            ws_thread = threading.Thread(target=self.ws.run_forever)
            ws_thread.daemon = True
            ws_thread.start()
            
            # Attendre que la connexion soit ouverte
            time.sleep(2)
            
            # Lancer la boucle de ping
            self.ping_loop()
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'ouverture: {e}")
            return


def main():
    """Fonction principale."""
    test = WebSocketTest()
    test.run()


if __name__ == "__main__":
    main()
