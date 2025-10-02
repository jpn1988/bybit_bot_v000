#!/usr/bin/env python3
"""
Orchestrateur principal du bot Bybit - Version asynchrone.

Cette classe coordonne les différents managers :
- DataManager : Gestion des données
- DisplayManager : Gestion de l'affichage
- MonitoringManager : Surveillance continue
- WebSocketManager : Connexions WebSocket
- VolatilityTracker : Calcul de volatilité
- WatchlistManager : Gestion de la watchlist
"""

import asyncio
import time
import signal
import atexit
from typing import List, Dict, Optional
from logging_setup import setup_logging, log_startup_summary, log_shutdown_summary
from config import get_settings
from bybit_client import BybitPublicClient
from instruments import get_perp_symbols, category_of_symbol
from volatility_tracker import VolatilityTracker
from watchlist_manager import WatchlistManager
from ws_manager import WebSocketManager
from data_manager import DataManager
from display_manager import DisplayManager
from monitoring_manager import MonitoringManager
from metrics_monitor import start_metrics_monitoring
from http_client_manager import close_all_http_clients
from callback_manager import CallbackManager
from opportunity_manager import OpportunityManager


class BotInitializer:
    """
    Initialiseur du bot Bybit.
    
    Responsabilités :
    - Initialisation des managers principaux
    - Configuration des gestionnaires spécialisés
    - Configuration des callbacks entre managers
    """
    
    def __init__(self, testnet: bool, logger):
        """Initialise l'initialiseur du bot."""
        self.testnet = testnet
        self.logger = logger
        
        # Managers principaux
        self.data_manager = None
        self.display_manager = None
        self.monitoring_manager = None
        self.ws_manager = None
        self.volatility_tracker = None
        self.watchlist_manager = None
        
        # Gestionnaires spécialisés
        self.callback_manager = None
        self.opportunity_manager = None
    
    def initialize_managers(self):
        """Initialise les managers principaux."""
        # Initialiser le gestionnaire de données
        self.data_manager = DataManager(logger=self.logger)
        
        # Initialiser le gestionnaire d'affichage
        self.display_manager = DisplayManager(self.data_manager, logger=self.logger)
        
        # Initialiser le gestionnaire de surveillance
        self.monitoring_manager = MonitoringManager(self.data_manager, testnet=self.testnet, logger=self.logger)
        
        # Gestionnaire WebSocket dédié
        self.ws_manager = WebSocketManager(testnet=self.testnet, logger=self.logger)
        
        # Gestionnaire de volatilité dédié
        self.volatility_tracker = VolatilityTracker(testnet=self.testnet, logger=self.logger)
        
        # Gestionnaire de watchlist dédié
        self.watchlist_manager = WatchlistManager(testnet=self.testnet, logger=self.logger)
    
    def initialize_specialized_managers(self):
        """Initialise les gestionnaires spécialisés."""
        # Gestionnaire de callbacks
        self.callback_manager = CallbackManager(logger=self.logger)
        
        # Gestionnaire d'opportunités
        self.opportunity_manager = OpportunityManager(self.data_manager, logger=self.logger)
    
    def setup_manager_callbacks(self):
        """Configure les callbacks entre les différents managers."""
        # Configurer les callbacks via le callback manager
        self.callback_manager.setup_manager_callbacks(
            self.display_manager,
            self.monitoring_manager,
            self.volatility_tracker,
            self.ws_manager,
            self.data_manager
        )
        
        # Configurer les callbacks WebSocket
        self.callback_manager.setup_ws_callbacks(self.ws_manager, self.data_manager)
        
        # Configurer les callbacks de volatilité
        self.callback_manager.setup_volatility_callbacks(self.volatility_tracker, self.data_manager)
        
        # Callbacks pour le monitoring manager
        self.monitoring_manager.set_watchlist_manager(self.watchlist_manager)
        self.monitoring_manager.set_volatility_tracker(self.volatility_tracker)
        self.monitoring_manager.set_ws_manager(self.ws_manager)  # Passer la référence au WebSocket
        self.monitoring_manager.set_on_new_opportunity_callback(
            lambda linear, inverse: self.opportunity_manager.on_new_opportunity(
                linear, inverse, self.ws_manager, self.watchlist_manager
            )
        )
        self.monitoring_manager.set_on_candidate_ticker_callback(
            lambda symbol, ticker_data: self.opportunity_manager.on_candidate_ticker(
                symbol, ticker_data, self.watchlist_manager
            )
        )


class BotConfigurator:
    """
    Configurateur du bot Bybit.
    
    Responsabilités :
    - Chargement et validation de la configuration
    - Configuration des paramètres des managers
    - Gestion des données de marché initiales
    """
    
    def __init__(self, testnet: bool, logger):
        """Initialise le configurateur du bot."""
        self.testnet = testnet
        self.logger = logger
    
    def load_and_validate_config(self, watchlist_manager: WatchlistManager) -> Dict:
        """
        Charge et valide la configuration.
        
        Args:
            watchlist_manager: Gestionnaire de watchlist
            
        Returns:
            Configuration validée
            
        Raises:
            ValueError: Si la configuration est invalide
        """
        try:
            config = watchlist_manager.load_and_validate_config()
        except ValueError as e:
            self.logger.error(f"❌ Erreur de configuration : {e}")
            self.logger.error("💡 Corrigez les paramètres dans src/parameters.yaml ou les variables d'environnement")
            raise
        return config
    
    def get_market_data(self) -> tuple[str, Dict]:
        """
        Récupère les données de marché initiales.
        
        Returns:
            Tuple (base_url, perp_data)
        """
        # Créer un client PUBLIC pour récupérer l'URL publique (aucune clé requise)
        client = BybitPublicClient(testnet=self.testnet, timeout=10)
        base_url = client.public_base_url()
        
        # Récupérer l'univers perp
        perp_data = get_perp_symbols(base_url, timeout=10)
        
        return base_url, perp_data
    
    def configure_managers(self, config: Dict, perp_data: Dict, data_manager: DataManager, 
                          volatility_tracker: VolatilityTracker, watchlist_manager: WatchlistManager,
                          display_manager: DisplayManager):
        """
        Configure les managers avec les paramètres.
        
        Args:
            config: Configuration validée
            perp_data: Données des perpétuels
            data_manager: Gestionnaire de données
            volatility_tracker: Tracker de volatilité
            watchlist_manager: Gestionnaire de watchlist
            display_manager: Gestionnaire d'affichage
        """
        # Stocker le mapping officiel des catégories
        symbol_categories = perp_data.get("categories", {}) or {}
        data_manager.set_symbol_categories(symbol_categories)
        
        # Configurer les gestionnaires avec les catégories
        volatility_tracker.set_symbol_categories(symbol_categories)
        watchlist_manager.symbol_categories = symbol_categories
        
        # Configurer le tracker de volatilité
        volatility_ttl_sec = int(config.get("volatility_ttl_sec", 120) or 120)
        volatility_tracker.ttl_seconds = volatility_ttl_sec
        
        # Configurer l'intervalle d'affichage
        display_interval = int(config.get("display_interval_seconds", 10) or 10)
        display_manager.set_display_interval(display_interval)
        display_manager.set_price_ttl(120)


class BotDataLoader:
    """
    Chargeur de données du bot Bybit.
    
    Responsabilités :
    - Construction de la watchlist
    - Chargement des données de funding
    - Gestion des erreurs de chargement
    """
    
    def __init__(self, logger):
        """Initialise le chargeur de données."""
        self.logger = logger
    
    def load_watchlist_data(self, base_url: str, perp_data: Dict, watchlist_manager: WatchlistManager,
                           volatility_tracker: VolatilityTracker, data_manager: DataManager) -> bool:
        """
        Charge les données de la watchlist.
        
        Args:
            base_url: URL de base de l'API
            perp_data: Données des perpétuels
            watchlist_manager: Gestionnaire de watchlist
            volatility_tracker: Tracker de volatilité
            data_manager: Gestionnaire de données
            
        Returns:
            True si le chargement a réussi, False sinon
        """
        try:
            linear_symbols, inverse_symbols, funding_data = watchlist_manager.build_watchlist(
                base_url, perp_data, volatility_tracker
            )
            
            # Mettre à jour le DataManager avec les données initiales
            data_manager.set_symbol_lists(linear_symbols, inverse_symbols)
            
            # Mettre à jour les données de funding
            self._update_funding_data(funding_data, data_manager)
            
            # Mettre à jour les données originales
            original_funding_data = watchlist_manager.get_original_funding_data()
            for symbol, next_funding_time in original_funding_data.items():
                data_manager.update_original_funding_data(symbol, next_funding_time)
            
            return True
                
        except Exception as e:
            if "Aucun symbole" in str(e) or "Aucun funding" in str(e):
                # Ne pas lever d'exception, continuer en mode surveillance
                self.logger.info("ℹ️ Aucune opportunité initiale détectée, mode surveillance activé")
                return True
            else:
                raise
    
    def _update_funding_data(self, funding_data: Dict, data_manager: DataManager):
        """Met à jour les données de funding dans le data manager."""
        for symbol, data in funding_data.items():
            if isinstance(data, (list, tuple)) and len(data) >= 4:
                funding, volume, funding_time, spread = data[:4]
                volatility = data[4] if len(data) > 4 else None
                data_manager.update_funding_data(symbol, funding, volume, funding_time, spread, volatility)
            elif isinstance(data, dict):
                # Si c'est un dictionnaire, extraire les valeurs
                funding = data.get('funding', 0.0)
                volume = data.get('volume', 0.0)
                funding_time = data.get('funding_time_remaining', '-')
                spread = data.get('spread_pct', 0.0)
                volatility = data.get('volatility_pct', None)
                data_manager.update_funding_data(symbol, funding, volume, funding_time, spread, volatility)


class BotStarter:
    """
    Démarreur du bot Bybit.
    
    Responsabilités :
    - Démarrage des composants du bot
    - Configuration de la surveillance
    - Gestion du résumé de démarrage
    """
    
    def __init__(self, testnet: bool, logger):
        """Initialise le démarreur du bot."""
        self.testnet = testnet
        self.logger = logger
    
    async def start_bot_components(self, volatility_tracker: VolatilityTracker, display_manager: DisplayManager,
                           ws_manager: WebSocketManager, data_manager: DataManager,
                           monitoring_manager: MonitoringManager, base_url: str, perp_data: Dict):
        """
        Démarre tous les composants du bot.
        
        Args:
            volatility_tracker: Tracker de volatilité
            display_manager: Gestionnaire d'affichage
            ws_manager: Gestionnaire WebSocket
            data_manager: Gestionnaire de données
            monitoring_manager: Gestionnaire de surveillance
            base_url: URL de base de l'API
            perp_data: Données des perpétuels
        """
        # Démarrer le tracker de volatilité (arrière-plan)
        volatility_tracker.start_refresh_task()
        
        # Démarrer l'affichage
        await display_manager.start_display_loop()

        # Démarrer les connexions WebSocket via le gestionnaire dédié
        linear_symbols = data_manager.get_linear_symbols()
        inverse_symbols = data_manager.get_inverse_symbols()
        if linear_symbols or inverse_symbols:
            await ws_manager.start_connections(linear_symbols, inverse_symbols)
        
        # Configurer la surveillance des candidats (en arrière-plan)
        monitoring_manager.setup_candidate_monitoring(base_url, perp_data)
        
        # Démarrer le mode surveillance continue
        await monitoring_manager.start_continuous_monitoring(base_url, perp_data)
    
    def display_startup_summary(self, config: Dict, perp_data: Dict, data_manager: DataManager):
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
        linear_count = len(data_manager.get_linear_symbols())
        inverse_count = len(data_manager.get_inverse_symbols())
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


class BotOrchestrator:
    """
    Orchestrateur principal du bot Bybit - Version refactorisée.
    
    Cette classe coordonne les différents composants spécialisés :
    - BotInitializer : Initialisation des managers
    - BotConfigurator : Configuration du bot
    - BotDataLoader : Chargement des données
    - BotStarter : Démarrage des composants
    """
    
    def __init__(self):
        self.logger = setup_logging()
        self.running = True
        
        # S'assurer que les clients HTTP sont fermés à l'arrêt
        atexit.register(close_all_http_clients)
        
        # Configuration
        settings = get_settings()
        self.testnet = settings['testnet']
        
        # Initialiser les composants spécialisés
        self._initializer = BotInitializer(self.testnet, self.logger)
        self._configurator = BotConfigurator(self.testnet, self.logger)
        self._data_loader = BotDataLoader(self.logger)
        self._starter = BotStarter(self.testnet, self.logger)
        
        # Initialiser les managers via l'initialiseur
        self._initializer.initialize_managers()
        self._initializer.initialize_specialized_managers()
        self._initializer.setup_manager_callbacks()
        
        # Récupérer les managers depuis l'initialiseur
        self.data_manager = self._initializer.data_manager
        self.display_manager = self._initializer.display_manager
        self.monitoring_manager = self._initializer.monitoring_manager
        self.ws_manager = self._initializer.ws_manager
        self.volatility_tracker = self._initializer.volatility_tracker
        self.watchlist_manager = self._initializer.watchlist_manager
        self.callback_manager = self._initializer.callback_manager
        self.opportunity_manager = self._initializer.opportunity_manager
        
        # Configuration du signal handler pour Ctrl+C
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # Initialiser le temps de démarrage pour l'uptime
        self.start_time = time.time()
        
        # Démarrer le monitoring des métriques
        start_metrics_monitoring(interval_minutes=5)
    
    def _signal_handler(self, signum, frame):
        """Gestionnaire de signal pour Ctrl+C."""
        # Éviter les appels multiples
        if not self.running:
            return
            
        self.logger.info("🛑 Signal d'arrêt reçu (Ctrl+C)...")
        self.running = False
        
        # Essayer un arrêt propre avec timeout
        try:
            # Utiliser une approche synchrone pour éviter les conflits de boucle d'événements
            self._stop_all_managers_sync()
            
            # Calculer l'uptime
            uptime_seconds = time.time() - self.start_time
            
            # Récupérer les derniers candidats surveillés
            last_candidates = getattr(self.monitoring_manager, 'candidate_symbols', [])
            
            # Afficher le résumé d'arrêt professionnel
            log_shutdown_summary(self.logger, last_candidates, uptime_seconds)
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur lors de l'arrêt propre: {e}")
        
        return
    
    async def _stop_all_managers_quick(self):
        """Arrêt rapide des managers avec timeout court."""
        managers_to_stop = [
            ("WebSocket", lambda: self.ws_manager.stop()),
            ("Display", lambda: self.display_manager.stop_display_loop()),
            ("Monitoring", lambda: self.monitoring_manager.stop_continuous_monitoring()),
            ("Volatility", lambda: self.volatility_tracker.stop_refresh_task())
        ]
        
        for name, stop_func in managers_to_stop:
            try:
                if asyncio.iscoroutinefunction(stop_func):
                    await stop_func()
                else:
                    stop_func()
                self.logger.debug(f"✅ {name} manager arrêté")
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur arrêt {name} manager: {e}")
        
        # Nettoyage des ressources
        self._cleanup_resources()
        
        # Attendre très peu pour que les tâches se terminent
        await asyncio.sleep(0.2)
    
    def _stop_all_managers_sync(self):
        """Arrêt rapide des managers avec timeout court (version synchrone)."""
        # Arrêt direct des managers sans coroutines pour éviter les conflits
        try:
            # WebSocket - arrêt forcé et nettoyage complet
            if hasattr(self.ws_manager, 'stop_sync'):
                self.ws_manager.stop_sync()
            else:
                # Arrêt forcé des WebSockets
                self.ws_manager.running = False
                
            # Nettoyage supplémentaire des WebSockets
            if hasattr(self.ws_manager, 'ws_public'):
                try:
                    self.ws_manager.ws_public.close()
                except:
                    pass
            if hasattr(self.ws_manager, 'ws_private'):
                try:
                    self.ws_manager.ws_private.close()
                except:
                    pass
                    
            self.logger.debug("✅ WebSocket manager arrêté")
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur arrêt WebSocket manager: {e}")
        
        try:
            # Display - arrêt forcé
            if hasattr(self.display_manager, 'display_running'):
                self.display_manager.display_running = False
            self.logger.debug("✅ Display manager arrêté")
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur arrêt Display manager: {e}")
        
        try:
            # Monitoring - utiliser la méthode synchrone si disponible
            if hasattr(self.monitoring_manager, 'stop_monitoring'):
                self.monitoring_manager.stop_monitoring()
            elif hasattr(self.monitoring_manager, 'stop_candidate_monitoring'):
                self.monitoring_manager.stop_candidate_monitoring()
            else:
                # Arrêt forcé
                if hasattr(self.monitoring_manager, '_running'):
                    self.monitoring_manager._running = False
            self.logger.debug("✅ Monitoring manager arrêté")
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur arrêt Monitoring manager: {e}")
        
        try:
            # Volatility - arrêt direct (synchrone)
            self.volatility_tracker.stop_refresh_task()
            self.logger.debug("✅ Volatility manager arrêté")
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur arrêt Volatility manager: {e}")
        
        # Nettoyage des ressources
        self._cleanup_resources()
        
        # Nettoyage agressif des connexions réseau
        self._force_close_network_connections()
        
        # Nettoyage agressif des threads et processus
        self._force_cleanup_threads()
        
        # Attendre très peu pour que les tâches se terminent
        time.sleep(0.2)
    
    def _force_cleanup_threads(self):
        """Nettoyage agressif des threads et processus pour éviter le blocage du terminal."""
        import threading
        import sys
        import gc
        import time
        
        try:
            # Arrêter spécifiquement les threads problématiques
            self._stop_specific_threads()
            
            # Arrêter tous les threads actifs de manière plus agressive
            for thread in threading.enumerate():
                if thread != threading.current_thread() and thread.is_alive():
                    try:
                        # Marquer le thread pour arrêt
                        if hasattr(thread, '_stop'):
                            thread._stop()
                        elif hasattr(thread, 'stop'):
                            thread.stop()
                        elif hasattr(thread, 'running'):
                            thread.running = False
                        elif hasattr(thread, '_running'):
                            thread._running = False
                    except:
                        pass
            
            # Nettoyer les buffers de sortie
            sys.stdout.flush()
            sys.stderr.flush()
            
            # Forcer le garbage collection
            gc.collect()
            
            # Attendre plus longtemps pour que les threads se terminent
            time.sleep(0.5)
            
            # Forcer l'arrêt des threads qui ne se sont pas arrêtés
            for thread in threading.enumerate():
                if thread != threading.current_thread() and thread.is_alive():
                    try:
                        # Forcer l'arrêt du thread
                        if hasattr(thread, 'daemon'):
                            thread.daemon = True
                    except:
                        pass
            
            self.logger.debug("✅ Nettoyage agressif des threads terminé")
            
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur nettoyage threads: {e}")
    
    def _stop_specific_threads(self):
        """Arrête spécifiquement les threads connus pour causer des problèmes."""
        try:
            # Arrêter le thread de volatilité
            if hasattr(self, 'volatility_tracker') and hasattr(self.volatility_tracker, '_refresh_thread'):
                if self.volatility_tracker._refresh_thread and self.volatility_tracker._refresh_thread.is_alive():
                    self.volatility_tracker._refresh_thread._stop()
                    self.logger.debug("✅ Thread volatilité forcé à s'arrêter")
            
            # Arrêter le thread de monitoring
            if hasattr(self, 'monitoring_manager') and hasattr(self.monitoring_manager, '_candidate_ws_thread'):
                if self.monitoring_manager._candidate_ws_thread and self.monitoring_manager._candidate_ws_thread.is_alive():
                    self.monitoring_manager._candidate_ws_thread._stop()
                    self.logger.debug("✅ Thread monitoring forcé à s'arrêter")
            
            # Arrêter le thread de métriques
            if hasattr(self, 'metrics_monitor') and hasattr(self.metrics_monitor, 'monitor_thread'):
                if self.metrics_monitor.monitor_thread and self.metrics_monitor.monitor_thread.is_alive():
                    self.metrics_monitor.monitor_thread._stop()
                    self.logger.debug("✅ Thread métriques forcé à s'arrêter")
                    
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur arrêt threads spécifiques: {e}")
    
    def _force_close_network_connections(self):
        """Force la fermeture de toutes les connexions réseau pour éviter le blocage."""
        try:
            # Fermer les clients HTTP
            if hasattr(self, 'http_client_manager'):
                self.http_client_manager.close_all()
                self.logger.debug("✅ Clients HTTP fermés")
            
            # Fermer les WebSockets de manière plus agressive
            if hasattr(self, 'ws_manager'):
                # Fermer toutes les connexions WebSocket
                if hasattr(self.ws_manager, '_ws_conns'):
                    for conn in self.ws_manager._ws_conns:
                        try:
                            conn.close()
                        except:
                            pass
                    self.ws_manager._ws_conns.clear()
                
                # Annuler toutes les tâches WebSocket
                if hasattr(self.ws_manager, '_ws_tasks'):
                    for task in self.ws_manager._ws_tasks:
                        try:
                            if not task.done():
                                task.cancel()
                        except:
                            pass
                    self.ws_manager._ws_tasks.clear()
                
                self.logger.debug("✅ Connexions WebSocket fermées")
            
            # Fermer les connexions de monitoring
            if hasattr(self, 'monitoring_manager'):
                if hasattr(self.monitoring_manager, 'candidate_ws_client'):
                    try:
                        self.monitoring_manager.candidate_ws_client.close()
                    except:
                        pass
                self.logger.debug("✅ Connexions monitoring fermées")
                
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur fermeture connexions réseau: {e}")
    
    def _stop_all_managers(self):
        """Arrête tous les managers avec timeout."""
        managers_to_stop = [
            ("WebSocket", lambda: self.ws_manager.stop()),
            ("Display", lambda: self.display_manager.stop_display_loop()),
            ("Monitoring", lambda: self.monitoring_manager.stop_continuous_monitoring()),
            ("Volatility", lambda: self.volatility_tracker.stop_refresh_task())
        ]
        
        for name, stop_func in managers_to_stop:
            try:
                stop_func()
                self.logger.debug(f"✅ {name} manager arrêté")
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur arrêt {name} manager: {e}")
        
        # Attendre que les threads se terminent
        import threading
        for thread in threading.enumerate():
            if thread != threading.current_thread() and thread.is_alive():
                if hasattr(thread, 'daemon') and thread.daemon:
                    thread.join(timeout=1)
        
        # Attendre un peu pour que les threads se terminent
        time.sleep(0.5)
    
    async def start(self):
        """Démarre le suivi des prix avec filtrage par funding."""
        try:
            # 1. Charger et valider la configuration
            config = self._configurator.load_and_validate_config(self.watchlist_manager)
        except ValueError:
            return  # Arrêt propre sans sys.exit
        
        try:
            # 2. Récupérer les données de marché
            base_url, perp_data = self._configurator.get_market_data()
        except Exception as e:
            self.logger.error(f"❌ Erreur récupération données marché : {e}")
            return
        
        # 3. Configurer les managers
        self._configurator.configure_managers(
            config, perp_data, self.data_manager, self.volatility_tracker, 
            self.watchlist_manager, self.display_manager
        )
        
        # 4. Charger les données de la watchlist
        if not self._data_loader.load_watchlist_data(
            base_url, perp_data, self.watchlist_manager, 
            self.volatility_tracker, self.data_manager
        ):
            return
        
        # 5. Afficher le résumé de démarrage
        self._starter.display_startup_summary(config, perp_data, self.data_manager)
        
        # 6. Démarrer tous les composants
        await self._starter.start_bot_components(
            self.volatility_tracker, self.display_manager, self.ws_manager,
            self.data_manager, self.monitoring_manager, base_url, perp_data
        )
        
        # 7. Maintenir le bot en vie avec une boucle d'attente
        await self._keep_bot_alive()
    
    async def _keep_bot_alive(self):
        """Maintient le bot en vie avec une boucle d'attente."""
        self.logger.info("🔄 Bot en mode surveillance continue...")
        
        try:
            while self.running:
                # Vérifier que tous les composants principaux sont toujours actifs
                if not self._check_components_health():
                    self.logger.warning("⚠️ Un composant critique s'est arrêté, redémarrage...")
                    # Optionnel: redémarrer les composants défaillants
                
                # Attendre avec vérification d'interruption
                await asyncio.sleep(1.0)
                    
        except asyncio.CancelledError:
            self.logger.info("🛑 Arrêt demandé par l'utilisateur")
            self.running = False
        except Exception as e:
            self.logger.error(f"❌ Erreur dans la boucle principale: {e}")
            self.running = False
    
    def _check_components_health(self) -> bool:
        """Vérifie que tous les composants critiques sont actifs."""
        try:
            # Vérifier que le monitoring continue fonctionne
            if not self.monitoring_manager.is_running():
                self.logger.warning("⚠️ Monitoring manager arrêté")
                return False
            
            # Vérifier que le display manager fonctionne
            if not self.display_manager._running:
                self.logger.warning("⚠️ Display manager arrêté")
                return False
            
            # Vérifier que le volatility tracker fonctionne
            if not self.volatility_tracker.is_running():
                self.logger.warning("⚠️ Volatility tracker arrêté")
                return False
            
            return True
            
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur vérification santé composants: {e}")
            return False
    
    def _cleanup_resources(self):
        """
        Nettoie toutes les ressources pour éviter les fuites mémoire.
        """
        try:
            # Nettoyer les références des managers
            if hasattr(self, 'data_manager'):
                # Nettoyer le cache de volatilité
                if hasattr(self.data_manager, 'volatility_cache'):
                    self.data_manager.volatility_cache.clear_all_cache()
            
            # Nettoyer les callbacks dans les managers
            if hasattr(self, 'ws_manager'):
                self.ws_manager._ticker_callback = None
            
            if hasattr(self, 'monitoring_manager'):
                self.monitoring_manager._on_new_opportunity_callback = None
                self.monitoring_manager._on_candidate_ticker_callback = None
            
            # Nettoyer les références des composants
            if hasattr(self, '_initializer'):
                self._initializer = None
            if hasattr(self, '_configurator'):
                self._configurator = None
            if hasattr(self, '_data_loader'):
                self._data_loader = None
            if hasattr(self, '_starter'):
                self._starter = None
            
            self.logger.debug("🧹 Ressources nettoyées avec succès")
            
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur nettoyage ressources: {e}")
    
