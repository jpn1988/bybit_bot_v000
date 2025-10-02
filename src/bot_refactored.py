#!/usr/bin/env python3
"""
🚀 Orchestrateur du bot (filters + WebSocket prix) - VERSION REFACTORISÉE

Script pour filtrer les contrats perpétuels par funding ET suivre leurs prix en temps réel.

Architecture modulaire :
- WatchlistManager : Gestion des filtres et sélection de symboles
- WebSocketManager : Gestion des connexions WebSocket publiques  
- VolatilityTracker : Calcul et cache de volatilité
- DataManager : Gestion des données en temps réel
- DisplayManager : Gestion de l'affichage
- MonitoringManager : Surveillance continue du marché
- PriceTracker : Orchestration principale (refactorisée)

Usage:
    python src/bot_refactored.py
"""

import os
import time
import signal
import threading
import atexit
from typing import List, Dict, Optional
from logging_setup import setup_logging, log_startup_summary, log_shutdown_summary
from config import get_settings
from bybit_client import BybitPublicClient
from instruments import get_perp_symbols, category_of_symbol
from price_store import get_snapshot, purge_expired
from volatility_tracker import VolatilityTracker
from watchlist_manager import WatchlistManager
from ws_manager import WebSocketManager
from data_manager import DataManager
from display_manager import DisplayManager
from monitoring_manager import MonitoringManager
from errors import NoSymbolsError
from metrics_monitor import start_metrics_monitoring
from http_client_manager import close_all_http_clients


class PriceTracker:
    """
    Orchestrateur principal du bot Bybit - Version refactorisée.
    
    Cette classe coordonne les différents managers :
    - DataManager : Gestion des données
    - DisplayManager : Gestion de l'affichage
    - MonitoringManager : Surveillance continue
    - WebSocketManager : Connexions WebSocket
    - VolatilityTracker : Calcul de volatilité
    - WatchlistManager : Gestion de la watchlist
    """
    
    def __init__(self):
        self.logger = setup_logging()
        self.running = True
        
        # S'assurer que les clients HTTP sont fermés à l'arrêt
        atexit.register(close_all_http_clients)
        
        # Configuration
        settings = get_settings()
        self.testnet = settings['testnet']
        
        # Initialiser le gestionnaire de données
        self.data_manager = DataManager(logger=self.logger)
        
        # Initialiser le gestionnaire d'affichage
        self.display_manager = DisplayManager(self.data_manager, logger=self.logger)
        
        # Initialiser le gestionnaire de surveillance
        self.monitoring_manager = MonitoringManager(self.data_manager, testnet=self.testnet, logger=self.logger)
        
        # Gestionnaire WebSocket dédié
        self.ws_manager = WebSocketManager(testnet=self.testnet, logger=self.logger)
        self.ws_manager.set_ticker_callback(self._update_realtime_data_from_ticker)
        
        # Gestionnaire de volatilité dédié
        self.volatility_tracker = VolatilityTracker(testnet=self.testnet, logger=self.logger)
        self.volatility_tracker.set_active_symbols_callback(self._get_active_symbols)
        
        # Gestionnaire de watchlist dédié
        self.watchlist_manager = WatchlistManager(testnet=self.testnet, logger=self.logger)
        
        # Configurer les callbacks entre managers
        self._setup_manager_callbacks()
        
        # Configuration du signal handler pour Ctrl+C
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # Initialiser le temps de démarrage pour l'uptime
        self.start_time = time.time()
        
        # Démarrer le monitoring des métriques
        start_metrics_monitoring(interval_minutes=5)
    
    def _setup_manager_callbacks(self):
        """Configure les callbacks entre les différents managers."""
        # Callback pour la volatilité dans le display manager
        self.display_manager.set_volatility_callback(self.volatility_tracker.get_cached_volatility)
        
        # Callbacks pour le monitoring manager
        self.monitoring_manager.set_watchlist_manager(self.watchlist_manager)
        self.monitoring_manager.set_volatility_tracker(self.volatility_tracker)
        self.monitoring_manager.set_on_new_opportunity_callback(self._on_new_opportunity)
        self.monitoring_manager.set_on_candidate_ticker_callback(self._on_candidate_ticker)
    
    def _signal_handler(self, signum, frame):
        """Gestionnaire de signal pour Ctrl+C."""
        self.logger.info("🛑 Signal d'arrêt reçu (Ctrl+C)...")
        self.running = False
        
        # Arrêter tous les managers
        try:
            self.ws_manager.stop()
        except Exception:
            pass
        
        try:
            self.display_manager.stop_display_loop()
        except Exception:
            pass
        
        try:
            self.monitoring_manager.stop_continuous_monitoring()
        except Exception:
            pass
        
        try:
            self.volatility_tracker.stop_refresh_task()
        except Exception:
            pass
        
        # Calculer l'uptime
        uptime_seconds = time.time() - self.start_time
        
        # Récupérer les derniers candidats surveillés
        last_candidates = self.monitoring_manager.candidate_symbols
        
        # Afficher le résumé d'arrêt professionnel
        log_shutdown_summary(self.logger, last_candidates, uptime_seconds)
        return
    
    def _update_realtime_data_from_ticker(self, ticker_data: dict):
        """
        Met à jour les données en temps réel à partir des données ticker WebSocket.
        Callback appelé par WebSocketManager.
        
        Args:
            ticker_data (dict): Données du ticker reçues via WebSocket
        """
        symbol = ticker_data.get("symbol", "")
        if not symbol:
            return
        
        # Déléguer au DataManager
        self.data_manager.update_realtime_data(symbol, ticker_data)
    
    def _on_new_opportunity(self, linear_symbols: List[str], inverse_symbols: List[str]):
        """
        Callback appelé lors de nouvelles opportunités détectées.
        
        Args:
            linear_symbols: Nouveaux symboles linear
            inverse_symbols: Nouveaux symboles inverse
        """
        try:
            # Démarrer les connexions WebSocket pour les nouvelles opportunités
            self.ws_manager.start_connections(linear_symbols, inverse_symbols)
            self.logger.info(f"🎯 Nouvelles opportunités intégrées: {len(linear_symbols)} linear, {len(inverse_symbols)} inverse")
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur intégration nouvelles opportunités: {e}")
    
    def _on_candidate_ticker(self, symbol: str, ticker_data: dict):
        """
        Callback appelé pour les tickers des candidats.
        
        Args:
            symbol: Symbole candidat
            ticker_data: Données du ticker
        """
        try:
            # Ajouter le symbole à la watchlist principale
            self._add_symbol_to_main_watchlist(symbol, ticker_data)
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur traitement candidat {symbol}: {e}")
    
    def _add_symbol_to_main_watchlist(self, symbol: str, ticker_data: dict):
        """
        Ajoute un symbole à la watchlist principale.
        
        Args:
            symbol: Symbole à ajouter
            ticker_data: Données du ticker
        """
        try:
            # Vérifier que le symbole n'est pas déjà dans la watchlist
            if self.data_manager.get_funding_data(symbol):
                return  # Déjà présent
            
            # Construire les données du symbole
            funding_rate = ticker_data.get("fundingRate")
            volume24h = ticker_data.get("volume24h")
            next_funding_time = ticker_data.get("nextFundingTime")
            
            if funding_rate is not None:
                funding = float(funding_rate)
                volume = float(volume24h) if volume24h is not None else 0.0
                funding_time_remaining = self.watchlist_manager.calculate_funding_time_remaining(next_funding_time)
                
                # Calculer le spread si disponible
                spread_pct = 0.0
                bid1_price = ticker_data.get("bid1Price")
                ask1_price = ticker_data.get("ask1Price")
                if bid1_price and ask1_price:
                    try:
                        bid = float(bid1_price)
                        ask = float(ask1_price)
                        if bid > 0 and ask > 0:
                            mid = (ask + bid) / 2
                            if mid > 0:
                                spread_pct = (ask - bid) / mid
                    except (ValueError, TypeError):
                        pass
                
                # Ajouter à la watchlist via le DataManager
                self.data_manager.update_funding_data(symbol, funding, volume, funding_time_remaining, spread_pct, None)
                
                # Ajouter aux listes par catégorie
                category = category_of_symbol(symbol, self.data_manager.symbol_categories)
                self.data_manager.add_symbol_to_category(symbol, category)
                
                # Mettre à jour les données originales
                if next_funding_time:
                    self.data_manager.update_original_funding_data(symbol, next_funding_time)
                
                self.logger.info(f"✅ Symbole {symbol} ajouté à la watchlist principale")
                
        except Exception as e:
            self.logger.error(f"❌ Erreur ajout symbole {symbol}: {e}")
    
    def start(self):
        """Démarre le suivi des prix avec filtrage par funding."""
        # Charger et valider la configuration via le watchlist manager
        try:
            config = self.watchlist_manager.load_and_validate_config()
        except ValueError as e:
            self.logger.error(f"❌ Erreur de configuration : {e}")
            self.logger.error("💡 Corrigez les paramètres dans src/parameters.yaml ou les variables d'environnement")
            return  # Arrêt propre sans sys.exit
        
        # Créer un client PUBLIC pour récupérer l'URL publique (aucune clé requise)
        client = BybitPublicClient(testnet=self.testnet, timeout=10)
        base_url = client.public_base_url()
        
        # Récupérer l'univers perp
        perp_data = get_perp_symbols(base_url, timeout=10)
        
        # Stocker le mapping officiel des catégories
        symbol_categories = perp_data.get("categories", {}) or {}
        self.data_manager.set_symbol_categories(symbol_categories)
        
        # Configurer les gestionnaires avec les catégories
        self.volatility_tracker.set_symbol_categories(symbol_categories)
        self.watchlist_manager.symbol_categories = symbol_categories
        
        # Configurer le tracker de volatilité
        volatility_ttl_sec = int(config.get("volatility_ttl_sec", 120) or 120)
        self.volatility_tracker.ttl_seconds = volatility_ttl_sec
        
        # Configurer l'intervalle d'affichage
        display_interval = int(config.get("display_interval_seconds", 10) or 10)
        self.display_manager.set_display_interval(display_interval)
        self.display_manager.set_price_ttl(120)
        
        # Construire la watchlist via le gestionnaire dédié
        try:
            linear_symbols, inverse_symbols, funding_data = self.watchlist_manager.build_watchlist(
                base_url, perp_data, self.volatility_tracker
            )
            
            # Mettre à jour le DataManager avec les données initiales
            self.data_manager.set_symbol_lists(linear_symbols, inverse_symbols)
            
            # Mettre à jour les données de funding
            for symbol, data in funding_data.items():
                if len(data) >= 4:
                    funding, volume, funding_time, spread = data[:4]
                    volatility = data[4] if len(data) > 4 else None
                    self.data_manager.update_funding_data(symbol, funding, volume, funding_time, spread, volatility)
            
            # Mettre à jour les données originales
            original_funding_data = self.watchlist_manager.get_original_funding_data()
            for symbol, next_funding_time in original_funding_data.items():
                self.data_manager.update_original_funding_data(symbol, next_funding_time)
                
        except Exception as e:
            if "Aucun symbole" in str(e) or "Aucun funding" in str(e):
                # Ne pas lever d'exception, continuer en mode surveillance
                self.logger.info("ℹ️ Aucune opportunité initiale détectée, mode surveillance activé")
            else:
                raise
        
        # Afficher le résumé de démarrage structuré
        self._display_startup_summary(config, perp_data)
        
        # Démarrer le tracker de volatilité (arrière-plan)
        self.volatility_tracker.start_refresh_task()
        
        # Démarrer l'affichage
        self.display_manager.start_display_loop()

        # Démarrer les connexions WebSocket via le gestionnaire dédié
        linear_symbols = self.data_manager.get_linear_symbols()
        inverse_symbols = self.data_manager.get_inverse_symbols()
        if linear_symbols or inverse_symbols:
            self.ws_manager.start_connections(linear_symbols, inverse_symbols)
        
        # Configurer la surveillance des candidats (en arrière-plan)
        self.monitoring_manager.setup_candidate_monitoring(base_url, perp_data)
        
        # Démarrer le mode surveillance continue
        self.monitoring_manager.start_continuous_monitoring(base_url, perp_data)
    
    def _get_active_symbols(self) -> List[str]:
        """Retourne la liste des symboles actuellement actifs."""
        return self.data_manager.get_all_symbols()
    
    def _display_startup_summary(self, config: Dict, perp_data: Dict):
        """Affiche le résumé de démarrage structuré."""
        # Informations du bot
        bot_info = {
            'name': 'BYBIT BOT',
            'version': '0.9.0',
            'environment': 'Testnet' if self.testnet else 'Mainnet',
            'mode': 'Funding Sniping'
        }
        
        # Statistiques de filtrage
        total_symbols = perp_data.get('total', 0)
        linear_count = len(self.data_manager.get_linear_symbols())
        inverse_count = len(self.data_manager.get_inverse_symbols())
        final_count = linear_count + inverse_count
        
        filter_results = {
            'stats': {
                'total_symbols': total_symbols,
                'after_funding_volume': final_count,
                'after_spread': final_count,
                'after_volatility': final_count,
                'final_count': final_count
            }
        }
        
        # Statut WebSocket
        ws_status = {
            'connected': bool(linear_count or inverse_count),
            'symbols_count': final_count,
            'category': config.get('categorie', 'linear')
        }
        
        # Ajouter l'intervalle de métriques à la config
        config['metrics_interval'] = 5
        
        # Afficher le résumé structuré
        log_startup_summary(self.logger, bot_info, config, filter_results, ws_status)


def main():
    """Fonction principale."""
    tracker = PriceTracker()
    try:
        tracker.start()
        
        # Boucle d'attente pour maintenir le bot actif
        while tracker.running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        tracker.logger.info("🛑 Arrêt demandé par l'utilisateur")
        tracker.running = False
        # Forcer l'arrêt de tous les threads
        tracker._signal_handler(signal.SIGINT, None)
    except Exception as e:
        tracker.logger.error(f"❌ Erreur : {e}")
        tracker.running = False
        # Forcer l'arrêt de tous les threads
        tracker._signal_handler(signal.SIGINT, None)
        # Laisser le code appelant décider (ne pas sys.exit ici)


if __name__ == "__main__":
    main()
