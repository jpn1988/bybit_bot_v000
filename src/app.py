#!/usr/bin/env python3
# NOTE: orchestrateur principal = src/bot.py
"""Orchestrateur pro pour supervision des connexions Bybit (REST + WebSocket public + WebSocket privé)."""

import os
import time
import threading
import signal
import websocket
from config import get_settings
from logging_setup import setup_logging
from bybit_client import BybitClient, BybitPublicClient
from instruments import get_perp_symbols
from ws_private import PrivateWSClient, create_private_ws_client, PrivateWSManager
from ws_public import SimplePublicWSClient


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
        self.ws_public_client = None
        self.ws_private = None
        self.ws_private_client = None
        
        # Threads
        self.ws_public_thread = None
        self.ws_private_thread = None
        
        # Reconnexion
        self.reconnect_delays = [1, 2, 5, 10]  # secondes
        
        # Configuration du signal handler pour Ctrl+C
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # La configuration des channels sera gérée par create_private_ws_client()

        self.logger.info("🚀 Lancement orchestrateur (REST + WS public + WS privé)")
        self.logger.info(f"📂 Configuration chargée (testnet={self.testnet})")
    
    def _signal_handler(self, signum, frame):
        """Gestionnaire de signal pour Ctrl+C."""
        self.logger.info("🧹 Arrêt demandé, fermeture des connexions…")
        self.close()
        exit(0)
    
    
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
    
    def _on_ws_public_open(self):
        """Callback appelé à l'ouverture de la WebSocket publique."""
        self.logger.info("🌐 WS publique ouverte")
        self.ws_public_status = "CONNECTED"
    
    def _on_ws_public_error(self, error):
        """Callback appelé en cas d'erreur de la WebSocket publique."""
        self.logger.warning(f"⚠️ WS publique erreur : {error}")
        self.ws_public_status = "DISCONNECTED"
    
    def _on_ws_public_close(self, close_status_code, close_msg):
        """Callback appelé à la fermeture de la WebSocket publique."""
        self.logger.info(f"🔌 WS publique fermée (code={close_status_code}, reason={close_msg})")
        self.ws_public_status = "DISCONNECTED"
    
    def _on_ws_public_message(self, message):
        """Callback appelé pour chaque message de la WebSocket publique."""
        # Ignorer silencieusement les messages (ping/pong auto)
        pass
    
    
    def ws_public_runner(self):
        """Runner WebSocket publique utilisant la classe centralisée."""
        # Créer le client WebSocket publique centralisé
        self.ws_public_client = SimplePublicWSClient(
            testnet=self.testnet,
            logger=self.logger
        )
        
        # Configurer les callbacks pour suivre l'état
        self.ws_public_client.set_callbacks(
            on_open=self._on_ws_public_open,
            on_message=self._on_ws_public_message,
            on_close=self._on_ws_public_close,
            on_error=self._on_ws_public_error
        )
        
        # Lancer la connexion (bloquant avec reconnexion automatique)
        try:
            self.ws_public_client.connect(category="linear")
        except Exception as e:
            self.logger.error(f"Erreur WS publique: {e}")
            self.ws_public_status = "DISCONNECTED"
    
    def ws_private_runner(self):
        """Runner WebSocket privée via PrivateWSManager."""
        try:
            self.ws_private_client = PrivateWSManager(self.logger)
            
            # Configurer le callback de changement d'état
            def on_status_change(new_status):
                if new_status in ["CONNECTED", "AUTHENTICATED"]:
                    self.ws_private_status = "CONNECTED"
                else:
                    self.ws_private_status = "DISCONNECTED"
            
            self.ws_private_client.on_status_change = on_status_change
            self.ws_private_client.run()
        except RuntimeError as e:
            self.logger.error(f"⛔ Erreur WebSocket privée : {e}")
            self.ws_private_status = "DISCONNECTED"
    
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
            if self.ws_public_client:
                self.ws_public_client.close()
            if self.ws_private_client:
                self.ws_private_client.close()
            
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
