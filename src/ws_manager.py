#!/usr/bin/env python3
"""
Gestionnaire WebSocket dédié pour les connexions publiques Bybit.

Cette classe gère uniquement :
- La connexion WS publique
- La souscription aux symboles  
- La réception et mise à jour des prix en temps réel
"""

import threading
import time
from typing import List, Callable, Optional
from logging_setup import setup_logging
from ws_public import PublicWSClient
from price_store import update


class WebSocketManager:
    """
    Gestionnaire WebSocket pour les connexions publiques Bybit.
    
    Responsabilités :
    - Gestion des connexions WebSocket publiques (linear/inverse)
    - Souscription aux symboles pour les tickers
    - Réception et traitement des données de prix en temps réel
    - Callbacks vers l'application principale
    """
    
    def __init__(self, testnet: bool = True, logger=None):
        """
        Initialise le gestionnaire WebSocket.
        
        Args:
            testnet (bool): Utiliser le testnet (True) ou le marché réel (False)
            logger: Logger pour les messages (optionnel)
        """
        self.testnet = testnet
        self.logger = logger or setup_logging()
        self.running = False
        
        # Connexions WebSocket
        self._ws_conns: List[PublicWSClient] = []
        self._ws_threads: List[threading.Thread] = []
        
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
    
    def start_connections(self, linear_symbols: List[str], inverse_symbols: List[str]):
        """
        Démarre les connexions WebSocket pour les symboles donnés.
        
        Args:
            linear_symbols: Liste des symboles linear à suivre
            inverse_symbols: Liste des symboles inverse à suivre
        """
        if self.running:
            self.logger.warning("⚠️ WebSocketManager déjà en cours d'exécution")
            return
        
        self.linear_symbols = linear_symbols or []
        self.inverse_symbols = inverse_symbols or []
        self.running = True
        
        # Déterminer le type de connexions nécessaires
        if self.linear_symbols and self.inverse_symbols:
            self.logger.info("🔄 Démarrage des connexions WebSocket pour linear et inverse")
            self._start_dual_connections()
        elif self.linear_symbols:
            self.logger.info("🔄 Démarrage de la connexion WebSocket linear")
            self._start_single_connection("linear", self.linear_symbols)
        elif self.inverse_symbols:
            self.logger.info("🔄 Démarrage de la connexion WebSocket inverse")
            self._start_single_connection("inverse", self.inverse_symbols)
        else:
            self.logger.warning("⚠️ Aucun symbole fourni pour les connexions WebSocket")
    
    def _handle_ticker(self, ticker_data: dict):
        """
        Gestionnaire interne pour les données ticker reçues.
        Met à jour le store de prix et appelle le callback externe.
        
        Args:
            ticker_data: Données ticker reçues via WebSocket
        """
        try:
            # Mettre à jour le store de prix global
            symbol = ticker_data.get("symbol", "")
            mark_price = ticker_data.get("markPrice")
            last_price = ticker_data.get("lastPrice")
            
            if symbol and mark_price is not None and last_price is not None:
                mark_val = float(mark_price)
                last_val = float(last_price)
                update(symbol, mark_val, last_val, time.time())
            
            # Appeler le callback externe si défini
            if self._ticker_callback and symbol:
                self._ticker_callback(ticker_data)
                
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur traitement ticker WebSocket: {e}")
    
    def _start_single_connection(self, category: str, symbols: List[str]):
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
            on_ticker_callback=self._handle_ticker
        )
        self._ws_conns = [conn]
        
        # Lancer la connexion (bloquant)
        conn.run()
    
    def _start_dual_connections(self):
        """
        Démarre deux connexions WebSocket isolées (linear et inverse).
        """
        # Créer les connexions isolées
        linear_conn = PublicWSClient(
            category="linear",
            symbols=self.linear_symbols,
            testnet=self.testnet,
            logger=self.logger,
            on_ticker_callback=self._handle_ticker
        )
        inverse_conn = PublicWSClient(
            category="inverse",
            symbols=self.inverse_symbols,
            testnet=self.testnet,
            logger=self.logger,
            on_ticker_callback=self._handle_ticker
        )
        
        self._ws_conns = [linear_conn, inverse_conn]
        
        # Lancer en parallèle dans des threads séparés
        linear_thread = threading.Thread(target=linear_conn.run)
        inverse_thread = threading.Thread(target=inverse_conn.run)
        linear_thread.daemon = True
        inverse_thread.daemon = True
        
        self._ws_threads = [linear_thread, inverse_thread]
        linear_thread.start()
        inverse_thread.start()
        
        # Bloquer le thread principal sur les deux connexions
        linear_thread.join()
        inverse_thread.join()
    
    def stop(self):
        """
        Arrête toutes les connexions WebSocket.
        """
        self.logger.info("🧹 Arrêt des connexions WebSocket...")
        self.running = False
        
        # Fermer toutes les connexions
        for conn in self._ws_conns:
            try:
                conn.close()
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur fermeture connexion WebSocket: {e}")
        
        # Attendre la fin des threads
        for thread in self._ws_threads:
            if thread.is_alive():
                try:
                    thread.join(timeout=5)
                except Exception as e:
                    self.logger.warning(f"⚠️ Erreur attente thread WebSocket: {e}")
        
        # Nettoyer les listes
        self._ws_conns.clear()
        self._ws_threads.clear()
    
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
            "inverse": self.inverse_symbols.copy()
        }
