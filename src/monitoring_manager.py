#!/usr/bin/env python3
"""
Gestionnaire de surveillance pour le bot Bybit.

Cette classe gère uniquement :
- La surveillance continue du marché
- La détection de nouvelles opportunités
- La surveillance des symboles candidats
- L'intégration des nouvelles opportunités
"""

import time
import threading
from typing import List, Dict, Optional, Any, Callable
from logging_setup import setup_logging
from data_manager import DataManager
from bybit_client import BybitPublicClient
from instruments import get_perp_symbols, category_of_symbol
from watchlist_manager import WatchlistManager
from volatility_tracker import VolatilityTracker


class MonitoringManager:
    """
    Gestionnaire de surveillance pour le bot Bybit.
    
    Responsabilités :
    - Surveillance continue du marché
    - Détection de nouvelles opportunités
    - Surveillance des symboles candidats
    - Intégration des nouvelles opportunités
    """
    
    def __init__(self, data_manager: DataManager, testnet: bool = True, logger=None):
        """
        Initialise le gestionnaire de surveillance.
        
        Args:
            data_manager: Gestionnaire de données
            testnet: Utiliser le testnet (True) ou le marché réel (False)
            logger: Logger pour les messages (optionnel)
        """
        self.data_manager = data_manager
        self.testnet = testnet
        self.logger = logger or setup_logging()
        
        # État de surveillance
        self._running = False
        self._continuous_monitoring_thread: Optional[threading.Thread] = None
        self._candidate_ws_thread: Optional[threading.Thread] = None
        
        # Surveillance des candidats
        self.candidate_symbols: List[str] = []
        self.candidate_ws_client = None
        
        # Gestionnaires
        self.watchlist_manager: Optional[WatchlistManager] = None
        self.volatility_tracker: Optional[VolatilityTracker] = None
        
        # Callbacks
        self._on_new_opportunity_callback: Optional[Callable] = None
        self._on_candidate_ticker_callback: Optional[Callable] = None
    
    def set_watchlist_manager(self, watchlist_manager: WatchlistManager):
        """
        Définit le gestionnaire de watchlist.
        
        Args:
            watchlist_manager: Gestionnaire de watchlist
        """
        self.watchlist_manager = watchlist_manager
    
    def set_volatility_tracker(self, volatility_tracker: VolatilityTracker):
        """
        Définit le tracker de volatilité.
        
        Args:
            volatility_tracker: Tracker de volatilité
        """
        self.volatility_tracker = volatility_tracker
    
    def set_on_new_opportunity_callback(self, callback: Callable):
        """
        Définit le callback pour les nouvelles opportunités.
        
        Args:
            callback: Fonction à appeler lors de nouvelles opportunités
        """
        self._on_new_opportunity_callback = callback
    
    def set_on_candidate_ticker_callback(self, callback: Callable):
        """
        Définit le callback pour les tickers des candidats.
        
        Args:
            callback: Fonction à appeler pour chaque ticker candidat
        """
        self._on_candidate_ticker_callback = callback
    
    def start_continuous_monitoring(self, base_url: str, perp_data: Dict):
        """
        Démarre la surveillance continue du marché.
        
        Args:
            base_url: URL de base de l'API Bybit
            perp_data: Données des perpétuels
        """
        if self._continuous_monitoring_thread and self._continuous_monitoring_thread.is_alive():
            self.logger.warning("⚠️ Surveillance continue déjà active")
            return
        
        self._running = True
        self._continuous_monitoring_thread = threading.Thread(
            target=self._continuous_monitoring_loop, 
            args=(base_url, perp_data)
        )
        self._continuous_monitoring_thread.daemon = True
        self._continuous_monitoring_thread.start()
        
        self.logger.info("🔍 Surveillance continue démarrée")
    
    def stop_continuous_monitoring(self):
        """
        Arrête la surveillance continue.
        """
        self._running = False
        
        # Arrêter la surveillance des candidats
        if self.candidate_ws_client:
            try:
                self.candidate_ws_client.close()
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur fermeture WebSocket candidats: {e}")
        
        # Attendre la fin des threads
        if self._continuous_monitoring_thread and self._continuous_monitoring_thread.is_alive():
            try:
                self._continuous_monitoring_thread.join(timeout=5)
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur attente thread surveillance: {e}")
        
        if self._candidate_ws_thread and self._candidate_ws_thread.is_alive():
            try:
                self._candidate_ws_thread.join(timeout=5)
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur attente thread candidats: {e}")
        
        self.logger.info("🔍 Surveillance continue arrêtée")
    
    def _continuous_monitoring_loop(self, base_url: str, perp_data: Dict):
        """
        Boucle de surveillance continue qui re-scanne le marché périodiquement.
        
        Args:
            base_url: URL de base de l'API Bybit
            perp_data: Données des perpétuels
        """
        scan_interval = 60  # 1 minute entre chaque scan complet
        last_scan_time = 0
        
        while self._running:
            try:
                # Vérification immédiate pour arrêt rapide
                if not self._running:
                    self.logger.info("🛑 Arrêt de la surveillance continue demandé")
                    break
                
                current_time = time.time()
                
                # Effectuer un scan si l'intervalle est écoulé
                if self._should_perform_scan(current_time, last_scan_time, scan_interval):
                    self._perform_market_scan(base_url, perp_data)
                    last_scan_time = current_time
                    
                    # Vérifier après le scan pour arrêt rapide
                    if not self._running:
                        break
                
                # Attendre avec vérification d'interruption
                self._wait_with_interrupt_check(10)
                
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur dans la boucle de surveillance continue: {e}")
                if not self._running:
                    break
                time.sleep(10)
        
        # Boucle de surveillance continue arrêtée
    
    def _should_perform_scan(self, current_time: float, last_scan_time: float, interval: int) -> bool:
        """
        Vérifie s'il est temps d'effectuer un nouveau scan.
        
        Args:
            current_time: Temps actuel
            last_scan_time: Temps du dernier scan
            interval: Intervalle en secondes
            
        Returns:
            True si un scan doit être effectué
        """
        return self._running and (current_time - last_scan_time >= interval)
    
    def _perform_market_scan(self, base_url: str, perp_data: Dict):
        """
        Effectue un scan complet du marché pour détecter de nouvelles opportunités.
        
        Args:
            base_url: URL de base de l'API Bybit
            perp_data: Données des perpétuels
        """
        if not self._running:
            return
        
        try:
            # Construire la watchlist via le gestionnaire
            new_opportunities = self._scan_for_new_opportunities(base_url, perp_data)
            
            # Vérification après le scan qui peut être long
            if not self._running:
                return
            
            if new_opportunities and self._running:
                self._integrate_new_opportunities(new_opportunities)
                
        except Exception as e:
            # Ne pas logger si on est en train de s'arrêter
            if self._running:
                self.logger.warning(f"⚠️ Erreur lors du re-scan: {e}")
    
    def _scan_for_new_opportunities(self, base_url: str, perp_data: Dict) -> Optional[Dict]:
        """
        Scanne le marché pour trouver de nouvelles opportunités.
        
        Args:
            base_url: URL de base de l'API Bybit
            perp_data: Données des perpétuels
            
        Returns:
            Dict contenant linear_symbols, inverse_symbols et funding_data ou None
        """
        if not self._running:
            return None
        
        try:
            # Créer un nouveau client pour éviter les problèmes de futures
            client = BybitPublicClient(testnet=self.testnet, timeout=10)
            fresh_base_url = client.public_base_url()
            
            if not self._running:
                return None
            
            # Reconstruire la watchlist (peut prendre du temps)
            if not self.watchlist_manager or not self.volatility_tracker:
                return None
            
            linear_symbols, inverse_symbols, funding_data = self.watchlist_manager.build_watchlist(
                fresh_base_url, perp_data, self.volatility_tracker
            )
            
            # Vérification immédiate après l'opération longue
            if not self._running:
                return None
            
            if linear_symbols or inverse_symbols:
                return {
                    "linear": linear_symbols,
                    "inverse": inverse_symbols,
                    "funding_data": funding_data
                }
            
        except Exception as e:
            # Ne pas logger si on est en train de s'arrêter
            if self._running:
                self.logger.warning(f"⚠️ Erreur scan opportunités: {e}")
        
        return None
    
    def _integrate_new_opportunities(self, opportunities: Dict):
        """
        Intègre les nouvelles opportunités détectées dans la watchlist existante.
        
        Args:
            opportunities: Dict avec linear, inverse et funding_data
        """
        if not self._running:
            return
        
        linear_symbols = opportunities.get("linear", [])
        inverse_symbols = opportunities.get("inverse", [])
        funding_data = opportunities.get("funding_data", {})
        
        # Récupérer les symboles existants
        existing_linear = set(self.data_manager.get_linear_symbols())
        existing_inverse = set(self.data_manager.get_inverse_symbols())
        
        # Identifier les nouveaux symboles
        new_linear = set(linear_symbols) - existing_linear
        new_inverse = set(inverse_symbols) - existing_inverse
        
        if new_linear or new_inverse:
            if not self._running:
                return
            
            # Mettre à jour les listes de symboles
            self._update_symbol_lists(linear_symbols, inverse_symbols, existing_linear, existing_inverse)
            
            if not self._running:
                return
            
            # Mettre à jour les données de funding
            self._update_funding_data(funding_data)
            
            if not self._running:
                return
            
            # Notifier les nouvelles opportunités
            if self._on_new_opportunity_callback:
                try:
                    self._on_new_opportunity_callback(linear_symbols, inverse_symbols)
                except Exception as e:
                    self.logger.warning(f"⚠️ Erreur callback nouvelles opportunités: {e}")
    
    def _update_symbol_lists(self, linear_symbols: List[str], inverse_symbols: List[str], 
                            existing_linear: set, existing_inverse: set):
        """
        Met à jour les listes de symboles avec les nouvelles opportunités.
        
        Args:
            linear_symbols: Nouveaux symboles linear
            inverse_symbols: Nouveaux symboles inverse
            existing_linear: Symboles linear existants
            existing_inverse: Symboles inverse existants
        """
        # Fusionner les listes
        all_linear = list(existing_linear | set(linear_symbols))
        all_inverse = list(existing_inverse | set(inverse_symbols))
        
        # Mettre à jour dans le data manager
        self.data_manager.set_symbol_lists(all_linear, all_inverse)
    
    def _update_funding_data(self, new_funding_data: Dict):
        """
        Met à jour les données de funding avec les nouvelles opportunités.
        
        Args:
            new_funding_data: Nouvelles données de funding
        """
        # Mettre à jour chaque symbole dans le data manager
        for symbol, data in new_funding_data.items():
            if isinstance(data, (list, tuple)) and len(data) >= 4:
                funding, volume, funding_time, spread = data[:4]
                volatility = data[4] if len(data) > 4 else None
                self.data_manager.update_funding_data(symbol, funding, volume, funding_time, spread, volatility)
            elif isinstance(data, dict):
                # Si c'est un dictionnaire, extraire les valeurs
                funding = data.get('funding', 0.0)
                volume = data.get('volume', 0.0)
                funding_time = data.get('funding_time_remaining', '-')
                spread = data.get('spread_pct', 0.0)
                volatility = data.get('volatility_pct', None)
                self.data_manager.update_funding_data(symbol, funding, volume, funding_time, spread, volatility)
        
        # Mettre à jour les données originales si disponible
        if self.watchlist_manager:
            try:
                original_data = self.watchlist_manager.get_original_funding_data()
                for symbol, next_funding_time in original_data.items():
                    self.data_manager.update_original_funding_data(symbol, next_funding_time)
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur mise à jour données originales: {e}")
    
    def _wait_with_interrupt_check(self, seconds: int):
        """
        Attend pendant le nombre de secondes spécifié avec vérification d'interruption.
        
        Args:
            seconds: Nombre de secondes à attendre
        """
        for _ in range(seconds):
            if not self._running:
                break
            time.sleep(1)
    
    def setup_candidate_monitoring(self, base_url: str, perp_data: Dict):
        """
        Configure la surveillance des symboles candidats.
        
        Args:
            base_url: URL de base de l'API Bybit
            perp_data: Données des perpétuels
        """
        try:
            if not self.watchlist_manager:
                return
            
            # Détecter les candidats
            self.candidate_symbols = self.watchlist_manager.find_candidate_symbols(base_url, perp_data)
            
            if not self.candidate_symbols:
                return
            
            # Séparer les candidats par catégorie
            linear_candidates = []
            inverse_candidates = []
            
            symbol_categories = self.data_manager.symbol_categories
            
            for symbol in self.candidate_symbols:
                category = category_of_symbol(symbol, symbol_categories)
                if category == "linear":
                    linear_candidates.append(symbol)
                elif category == "inverse":
                    inverse_candidates.append(symbol)
            
            # Démarrer la surveillance WebSocket des candidats
            if linear_candidates or inverse_candidates:
                self._start_candidate_websocket_monitoring(linear_candidates, inverse_candidates)
                
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur configuration surveillance candidats: {e}")
    
    def _start_candidate_websocket_monitoring(self, linear_candidates: List[str], inverse_candidates: List[str]):
        """
        Démarre la surveillance WebSocket des candidats.
        
        Args:
            linear_candidates: Candidats linear
            inverse_candidates: Candidats inverse
        """
        try:
            from ws_public import PublicWSClient
            
            # Créer une connexion WebSocket pour les candidats
            if linear_candidates and inverse_candidates:
                # Si on a les deux catégories, utiliser linear (plus courant)
                symbols_to_monitor = linear_candidates + inverse_candidates
                category = "linear"
            elif linear_candidates:
                symbols_to_monitor = linear_candidates
                category = "linear"
            elif inverse_candidates:
                symbols_to_monitor = inverse_candidates
                category = "inverse"
            else:
                return
            
            self.candidate_ws_client = PublicWSClient(
                category=category,
                symbols=symbols_to_monitor,
                testnet=self.testnet,
                logger=self.logger,
                on_ticker_callback=self._on_candidate_ticker
            )
            
            # Lancer la surveillance dans un thread séparé
            self._candidate_ws_thread = threading.Thread(target=self._candidate_ws_runner)
            self._candidate_ws_thread.daemon = True
            self._candidate_ws_thread.start()
            
        except Exception as e:
            self.logger.error(f"❌ Erreur démarrage surveillance candidats: {e}")
    
    def _candidate_ws_runner(self):
        """
        Runner pour la WebSocket des candidats.
        """
        if self.candidate_ws_client:
            try:
                self.candidate_ws_client.run()
            except Exception as e:
                if self._running:
                    self.logger.warning(f"⚠️ Erreur WebSocket candidats: {e}")
    
    def _on_candidate_ticker(self, ticker_data: dict):
        """
        Callback appelé pour chaque ticker des candidats.
        
        Args:
            ticker_data: Données du ticker reçues via WebSocket
        """
        try:
            symbol = ticker_data.get("symbol", "")
            if not symbol:
                return
            
            # Vérifier si le candidat passe maintenant les filtres
            if self.watchlist_manager and self.watchlist_manager.check_if_symbol_now_passes_filters(symbol, ticker_data):
                # 🎯 NOUVELLE OPPORTUNITÉ DÉTECTÉE !
                self.logger.info(f"🎯 Nouvelle opportunité détectée: {symbol}")
                
                # Appeler le callback externe si défini
                if self._on_candidate_ticker_callback:
                    try:
                        self._on_candidate_ticker_callback(symbol, ticker_data)
                    except Exception as e:
                        self.logger.warning(f"⚠️ Erreur callback candidat: {e}")
                
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur traitement candidat {symbol}: {e}")
    
    def is_running(self) -> bool:
        """
        Vérifie si le gestionnaire de surveillance est en cours d'exécution.
        
        Returns:
            True si en cours d'exécution
        """
        return self._running and self._continuous_monitoring_thread and self._continuous_monitoring_thread.is_alive()
