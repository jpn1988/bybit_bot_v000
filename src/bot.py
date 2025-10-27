#!/usr/bin/env python3
"""
Orchestrateur principal du bot Bybit - Version refactorisée.

╔═══════════════════════════════════════════════════════════════════╗
║                    📖 GUIDE DE LECTURE                            ║
╚═══════════════════════════════════════════════════════════════════╝

Ce fichier est l'ORCHESTRATEUR PRINCIPAL du bot. Il coordonne tous
les composants spécialisés pour démarrer et maintenir le bot en vie.

🔍 COMPRENDRE CE FICHIER EN 5 MINUTES :

1. __init__() (lignes 52-91) : Initialise tous les managers
   └─> Crée les helpers : initializer, configurator, starter, etc.

2. start() (lignes 110-163) : Séquence de démarrage en 7 étapes
   ├─> Charge la configuration (parameters.yaml + ENV)
   ├─> Récupère les données de marché via API
   ├─> Configure les managers
   ├─> Construit la watchlist (avec filtres)
   ├─> Affiche le résumé
   ├─> Démarre les composants (WebSocket, monitoring, affichage)
   └─> Entre dans la boucle de surveillance

3. _keep_bot_alive() (lignes 165-195) : Boucle principale
   └─> Vérifie la santé des composants toutes les secondes

4. stop() (lignes 218-242) : Arrêt propre du bot
   └─> Utilise ShutdownManager pour tout arrêter proprement

📚 FLUX DÉTAILLÉ : Consultez GUIDE_DEMARRAGE_BOT.md pour comprendre
   chaque étape en détail avec des diagrammes et explications.

🎯 COMPOSANTS UTILISÉS :
- BotInitializer : Initialisation des managers
- BotConfigurator : Configuration du bot
- DataManager : Gestion des données
- BotStarter : Démarrage des composants
- BotHealthMonitor : Surveillance de la santé
- ShutdownManager : Gestion de l'arrêt
- ThreadManager : Gestion des threads
- BotLifecycleManager : Gestion du cycle de vie
- PositionEventHandler : Gestion des événements de position
- FallbackDataManager : Gestion du fallback des données
"""

# ============================================================================
# IMPORTS STANDARD LIBRARY
# ============================================================================
import asyncio
import atexit
import signal
import sys
import time
from typing import Dict, Any, Optional, Tuple, Union, List, Callable

# ============================================================================
# IMPORTS CONFIGURATION ET UTILITAIRES
# ============================================================================
from config import get_settings
from config.constants import DEFAULT_FUNDING_UPDATE_INTERVAL
from config.urls import URLConfig
from logging_setup import setup_logging

# ============================================================================
# IMPORTS CLIENTS ET SERVICES EXTERNES
# ============================================================================
from bybit_client import BybitClient
from http_client_manager import close_all_http_clients
from metrics_monitor import start_metrics_monitoring

# ============================================================================
# IMPORTS COMPOSANTS CORE DU BOT
# ============================================================================
# Initialisation et configuration
from bot_initializer import BotInitializer
from bot_configurator import BotConfigurator
from bot_starter import BotStarter

# Gestion des données
from data_manager import DataManager

# Monitoring et santé
from bot_health_monitor import BotHealthMonitor
from position_monitor import PositionMonitor

# Gestion du cycle de vie
from shutdown_manager import ShutdownManager
from thread_manager import ThreadManager
from scheduler_manager import SchedulerManager
from funding_close_manager import FundingCloseManager

# Gestion des exceptions
from thread_exception_handler import (
    install_global_exception_handlers,
    install_asyncio_handler_if_needed
)

# ============================================================================
# IMPORTS COMPOSANTS REFACTORISÉS (NOUVEAUX)
# ============================================================================
from bot_lifecycle_manager import BotLifecycleManager
from position_event_handler import PositionEventHandler
from fallback_data_manager import FallbackDataManager


class BotOrchestrator:
    """
    Orchestrateur principal du bot Bybit - Version refactorisée.

    Cette classe coordonne les différents composants spécialisés :
    - BotInitializer : Initialisation des managers
    - BotConfigurator : Configuration du bot
    - DataManager : Gestion des données
    - BotStarter : Démarrage des composants
    - BotHealthMonitor : Surveillance de la santé
    - ShutdownManager : Gestion de l'arrêt
    - ThreadManager : Gestion des threads
    - BotLifecycleManager : Gestion du cycle de vie
    - PositionEventHandler : Gestion des événements de position
    - FallbackDataManager : Gestion du fallback des données
    """

    def __init__(
        self,
        logger=None,
        initializer=None,
        configurator=None,
        data_loader=None,
        starter=None,
        health_monitor=None,
        shutdown_manager=None,
        thread_manager=None,
        components_bundle=None,  # NOUVEAU: Support du mode factory
    ):
        """
        Initialise l'orchestrateur du bot.
        
        Args:
            logger: Logger pour les messages (optionnel)
            initializer: Initialiseur du bot (optionnel, créé automatiquement si non fourni)
            configurator: Configurateur du bot (optionnel, créé automatiquement si non fourni)
            data_loader: Gestionnaire de données (optionnel, créé automatiquement si non fourni)
            starter: Démarreur du bot (optionnel, créé automatiquement si non fourni)
            health_monitor: Moniteur de santé (optionnel, créé automatiquement si non fourni)
            shutdown_manager: Gestionnaire d'arrêt (optionnel, créé automatiquement si non fourni)
            thread_manager: Gestionnaire de threads (optionnel, créé automatiquement si non fourni)
            components_bundle: Bundle de composants pré-créés (optionnel, nouveau mode factory)
                              Si fourni, utilise les composants du bundle au lieu de créer de nouveaux
        """
        self.logger = logger or setup_logging()
        self.running = True

        # Installer les handlers globaux pour exceptions non capturées
        # IMPORTANT : À faire avant de créer des threads ou tâches asyncio
        install_global_exception_handlers(self.logger)

        # S'assurer que les clients HTTP sont fermés à l'arrêt
        atexit.register(close_all_http_clients)

        # NOUVEAU: Détecter le mode factory
        self._use_factory_mode = components_bundle is not None
        self.components_bundle = components_bundle  # Stocker pour utilisation dans start()

        # Configuration
        settings = get_settings()
        self.testnet = settings["testnet"]
        
        # Test de connexion Bybit authentifiée (exécuté dans un thread dédié pour éviter PERF-002)
        # Uniquement en mode legacy (mode factory l'a déjà fait)
        if not self._use_factory_mode:
            self._test_bybit_auth_connection_sync()

        # Initialiser les composants spécialisés (injection avec fallback)
        self._initializer = initializer or BotInitializer(self.testnet, self.logger)
        self._configurator = configurator or BotConfigurator(self.testnet, self.logger)
        self._data_loader = data_loader or DataManager(self.testnet, self.logger)
        self._starter = starter or BotStarter(self.testnet, self.logger)
        self._health_monitor = health_monitor or BotHealthMonitor(self.logger)

        # Initialiser les nouveaux managers
        self._shutdown_manager = shutdown_manager or ShutdownManager(self.logger)
        self._thread_manager = thread_manager or ThreadManager(self.logger)
        
        # Initialiser les nouveaux composants refactorisés
        self._lifecycle_manager = BotLifecycleManager(
            testnet=self.testnet,
            logger=self.logger,
            health_monitor=self._health_monitor,
            shutdown_manager=self._shutdown_manager,
            thread_manager=self._thread_manager,
        )
        
        self._position_event_handler = PositionEventHandler(
            testnet=self.testnet,
            logger=self.logger,
        )
        
        self._fallback_data_manager = FallbackDataManager(
            testnet=self.testnet,
            logger=self.logger,
        )
        
        # Scheduler sera initialisé avec la configuration dans start()
        self.scheduler = None
        
        # PositionMonitor pour surveiller les positions
        self.position_monitor = None
        self.funding_close_manager = None

        # Initialiser les managers via l'initialiseur
        self._initialize_components()

        # Configuration du signal handler pour Ctrl+C via ShutdownManager
        self._shutdown_manager.setup_signal_handler(self)

        # Initialiser le temps de démarrage pour l'uptime
        self.start_time = time.time()

        # Démarrer le monitoring des métriques
        start_metrics_monitoring(interval_minutes=5)

        # Stocker la référence au moniteur de métriques pour l'arrêt
        # Import ici pour éviter les imports circulaires
        try:
            from metrics_monitor import metrics_monitor
            self.metrics_monitor = metrics_monitor
        except ImportError:
            self.metrics_monitor = None
            self.logger.warning("⚠️ metrics_monitor non disponible - monitoring des métriques désactivé")

    # ============================================================================
    # MÉTHODES D'INITIALISATION
    # ============================================================================

    def _initialize_components(self):
        """
        Initialise tous les composants du bot.
        
        Cette méthode détermine le mode d'initialisation (factory ou legacy)
        et délègue l'initialisation appropriée.
        
        Side effects:
            - Initialise les managers principaux
            - Configure les relations entre composants
            - Met à jour self._use_factory_mode
        """
        if self._use_factory_mode:
            # NOUVEAU MODE: Utiliser les composants du bundle
            self._initialize_from_bundle()
        else:
            # ANCIEN MODE: Créer les composants comme avant (rétro-compatibilité)
            self._initialize_from_legacy()
    
    def _initialize_from_legacy(self):
        """
        Ancien mode: Initialise les composants comme avant.
        
        Cette méthode utilise l'approche legacy pour créer et configurer
        tous les managers du bot. Elle est maintenue pour la rétro-compatibilité.
        
        Side effects:
            - Crée tous les managers via BotInitializer
            - Configure les callbacks entre managers
            - Assigne les managers aux attributs de l'instance
        """
        # Initialiser les managers
        self._initializer.initialize_managers()
        self._initializer.initialize_specialized_managers()
        self._initializer.setup_manager_callbacks()

        # Récupérer les managers depuis l'initialiseur
        managers = self._initializer.get_managers()
        self.data_manager = managers["data_manager"]
        self.display_manager = managers["display_manager"]
        self.monitoring_manager = managers["monitoring_manager"]
        self.ws_manager = managers["ws_manager"]
        self.volatility_tracker = managers["volatility_tracker"]
        self.watchlist_manager = managers["watchlist_manager"]
        self.callback_manager = managers["callback_manager"]
        self.opportunity_manager = managers["opportunity_manager"]

        # Passer le bybit_client au monitoring_manager pour la vérification des positions
        if hasattr(self, 'bybit_client') and self.bybit_client:
            self.monitoring_manager.set_bybit_client(self.bybit_client)
        
        # Configurer les nouveaux composants refactorisés
        self._position_event_handler.set_monitoring_manager(self.monitoring_manager)
        self._position_event_handler.set_ws_manager(self.ws_manager)
        self._position_event_handler.set_display_manager(self.display_manager)
        self._position_event_handler.set_data_manager(self.data_manager)
        
        self._fallback_data_manager.set_data_manager(self.data_manager)
        self._fallback_data_manager.set_watchlist_manager(self.watchlist_manager)
        
        # Configurer le callback de mise à jour des funding
        self._lifecycle_manager.set_on_funding_update_callback(
            self._fallback_data_manager.update_funding_data_periodically
        )
    
    def _initialize_from_bundle(self):
        """
        Nouveau mode: Initialise depuis le bundle de composants.
        
        Cette méthode utilise les composants pré-créés par BotFactory
        et les assigne aux attributs de l'instance. C'est l'approche recommandée.
        
        Side effects:
            - Assigne tous les composants depuis le bundle
            - Configure les relations entre composants
            - Met à jour self.bybit_client
        """
        self.logger.debug("🔄 Initialisation en mode factory depuis le bundle (composants: %d managers)", 
                          len(self.components_bundle.get_all_managers()))
        
        # Utiliser les composants du bundle
        bundle = self.components_bundle
        
        # Assigner les helpers
        self._initializer = bundle.initializer
        self._configurator = bundle.configurator
        self._data_loader = bundle.data_loader
        self._starter = bundle.starter
        self._health_monitor = bundle.health_monitor
        self._shutdown_manager = bundle.shutdown_manager
        self._thread_manager = bundle.thread_manager
        
        # Assigner les managers principaux
        self.data_manager = bundle.data_manager
        self.display_manager = bundle.display_manager
        self.monitoring_manager = bundle.monitoring_manager
        self.ws_manager = bundle.ws_manager
        self.watchlist_manager = bundle.watchlist_manager
        self.callback_manager = bundle.callback_manager
        self.opportunity_manager = bundle.opportunity_manager
        self.volatility_tracker = bundle.volatility_tracker
        
        # Assigner les composants de lifecycle
        self._lifecycle_manager = bundle.lifecycle_manager
        self._position_event_handler = bundle.position_event_handler
        self._fallback_data_manager = bundle.fallback_data_manager
        
        # Assigner le client Bybit
        self.bybit_client = bundle.bybit_client
        
        self.logger.debug("✅ Composants initialisés depuis le bundle (bybit_client: {})", 
                          "connecté" if self.bybit_client else "non configuré")

    def _test_bybit_auth_connection_sync(self) -> bool:
        """
        Teste la connexion à l'API Bybit avec authentification complète.
        Vérifie les clés BYBIT_API_KEY/BYBIT_API_SECRET depuis .env
        et log le statut de la connexion.
        
        Utilise concurrent.futures.ThreadPoolExecutor pour exécuter dans un thread dédié
        et supprimer le warning PERF-002.
        """
        settings = get_settings()
        testnet = settings.get("testnet", True)
        
        # Gérer les cas où les clés ne sont pas configurées (tests, mode non-auth, etc.)
        api_key = settings.get("api_key")
        api_secret = settings.get("api_secret")

        if not api_key or not api_secret:
            self.logger.warning("🔒 Clés API non configurées : connexion authentifiée désactivée (mode lecture seule)")
            return False

        try:
            # Exécuter la logique synchrone dans un thread dédié pour éviter PERF-002
            def _sync_connection_test():
                """
                Teste la connexion Bybit de manière synchrone.
                
                Cette fonction interne teste la connexion à l'API Bybit
                et récupère le solde du portefeuille. Elle est exécutée
                dans un thread dédié pour éviter les problèmes d'event loop.
                
                Returns:
                    dict: Réponse de l'API get_wallet_balance
                """
                self.bybit_client = BybitClient(
                    testnet=testnet,
                    timeout=settings["timeout"],
                    api_key=api_key,
                    api_secret=api_secret,
                )
                return self.bybit_client.get_wallet_balance(account_type="UNIFIED")
            
            # Utiliser concurrent.futures pour éviter les problèmes d'event loop
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(_sync_connection_test)
                result = future.result()
            
            balance = self._extract_usdt_balance(result)
            self.logger.info("✅ Bybit connecté ({}) en mode authentifié - Balance: {} USDT", 
                            'testnet' if testnet else 'mainnet', balance)
            return True
        except Exception as e:
            self.logger.error("❌ Vérification Bybit authentifiée échouée : {} (type: {})", 
                             str(e), type(e).__name__)
            return False

    def _extract_usdt_balance(self, wallet_response: dict) -> str:
        """
        Extrait le solde USDT de la réponse de l'API Bybit.
        
        Args:
            wallet_response: Réponse brute de l'API get_wallet_balance
            
        Returns:
            str: Solde USDT formaté ou "N/A" si non trouvé
        """
        try:
            # Structure réelle: list[0].totalWalletBalance ou list[0].coin[].walletBalance
            # L'API Bybit retourne directement { "list": [...] } sans wrapper "result"
            account_list = wallet_response.get("list", [])
            
            if not account_list:
                return "N/A"
            
            # Prendre le premier compte (généralement UNIFIED)
            account = account_list[0]
            
            # Essayer d'abord totalWalletBalance (solde total du portefeuille)
            total_balance = account.get("totalWalletBalance")
            
            if total_balance and total_balance != "0":
                return f"{float(total_balance):.2f}"
            
            # Sinon, chercher dans le tableau coin pour USDT
            coins = account.get("coin", [])
            
            for coin in coins:
                if coin.get("coin") == "USDT":
                    usdt_balance = coin.get("walletBalance", "0")
                    return f"{float(usdt_balance):.2f}"
            
            # Si aucun USDT trouvé, retourner le solde total
            return f"{float(total_balance or 0):.2f}"
            
        except (ValueError, TypeError, KeyError, IndexError) as e:
            self.logger.debug("Erreur extraction solde USDT: {} (données: {})", 
                             str(e), str(wallet_response)[:100])
            return "N/A"

    # ============================================================================
    # MÉTHODES DE DÉMARRAGE
    # ============================================================================

    async def start(self) -> None:
        """
        Démarre le suivi des prix avec filtrage par funding.
        
        Cette méthode orchestre le démarrage complet du bot en divisant
        le processus en étapes logiques distinctes pour une meilleure
        lisibilité et maintenabilité.
        """
        # Installer le handler asyncio pour la boucle événementielle actuelle
        install_asyncio_handler_if_needed()
        
        # 1. Configuration et validation
        config, base_url, perp_data = await self._initialize_and_validate_config()
        if not config:
            return

        # 2. Configuration des managers et chargement des données
        if not await self._configure_managers_and_load_data(config, base_url, perp_data):
            return

        # 3. Démarrer les composants principaux
        await self._start_main_components(base_url, perp_data)

        # 4. Initialiser les composants spécialisés
        self._initialize_specialized_components(config)

        # 5. Configurer les callbacks
        self._configure_specialized_callbacks()

        # 6. Démarrer le cycle de vie du bot
        await self._start_lifecycle()

    async def _initialize_and_validate_config(self) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[Dict[str, Any]]]:
        """
        Initialise et valide la configuration du bot.
        
        Cette méthode charge la configuration, la valide et récupère
        les données de marché nécessaires au démarrage.
        
        Returns:
            Tuple[Optional[Dict[str, Any]], Optional[str], Optional[Dict[str, Any]]]: 
                (config, base_url, perp_data) ou (None, None, None) si erreur
        """
        try:
            # 1. Charger et valider la configuration
            config = self._configurator.load_and_validate_config(
                self.watchlist_manager.config_manager
            )
        except ValueError:
            return None, None, None  # Arrêt propre sans sys.exit

        try:
            # 2. Récupérer les données de marché
            base_url, perp_data = self._configurator.get_market_data()
            return config, base_url, perp_data
        except Exception as e:
            self.logger.error("❌ Erreur récupération données marché : {} (étape: configuration)", 
                             str(e))
            return None, None, None

    async def _configure_managers_and_load_data(self, config: Dict[str, Any], base_url: str, perp_data: Dict[str, Any]) -> bool:
        """
        Configure les managers et charge les données nécessaires.
        
        Cette méthode configure tous les managers avec la configuration
        et charge les données de la watchlist.
        
        Args:
            config: Configuration du bot
            base_url: URL de base de l'API
            perp_data: Données des instruments perpétuels
            
        Returns:
            bool: True si la configuration et le chargement ont réussi
        """
        # 3. Configurer les managers
        self._configurator.configure_managers(
            config,
            perp_data,
            self.data_manager,
            self.volatility_tracker,
            self.watchlist_manager,
            self.display_manager,
        )

        # 4. Charger les données de la watchlist
        if not self._data_loader.load_watchlist_data(
            base_url,
            perp_data,
            self.watchlist_manager,
            self.volatility_tracker,
        ):
            return False

        # 5. Afficher le résumé de démarrage
        self._starter.display_startup_summary(
            config, perp_data, self.data_manager
        )
        
        return True

    async def _start_main_components(self, base_url: str, perp_data: Dict[str, Any]) -> None:
        """
        Démarre tous les composants principaux du bot.
        
        Cette méthode démarre les composants de base nécessaires
        au fonctionnement du bot (volatility_tracker, display_manager, etc.).
        
        Args:
            base_url: URL de base de l'API
            perp_data: Données des instruments perpétuels
        """
        await self._starter.start_bot_components(
            self.volatility_tracker,
            self.display_manager,
            self.ws_manager,
            self.data_manager,
            self.monitoring_manager,
            base_url,
            perp_data,
        )

    def _initialize_specialized_components(self, config: Dict[str, Any]) -> None:
        """
        Initialise les composants spécialisés du bot.
        
        Cette méthode initialise les composants spécialisés comme
        le Scheduler, PositionMonitor et FundingCloseManager.
        
        Args:
            config: Configuration du bot
        """
        # 7. Initialiser et démarrer le Scheduler pour la surveillance du funding
        self._initialize_scheduler(config)

        # 8. Initialiser le PositionMonitor
        self._initialize_position_monitor()
        
        # 9. Initialiser le FundingCloseManager
        self._initialize_funding_close_manager()

    def _configure_specialized_callbacks(self) -> None:
        """
        Configure les callbacks des composants spécialisés.
        
        Cette méthode configure les callbacks entre les composants
        spécialisés pour assurer la communication entre eux.
        """
        # Note: Le bundle étant immutable, on configure directement les callbacks
        if self.scheduler and self._position_event_handler:
            self.scheduler.on_position_opened_callback = self._position_event_handler.on_position_opened

        if self.position_monitor and self._position_event_handler:
            self.position_monitor.on_position_opened = self._position_event_handler.on_position_opened
            self.position_monitor.on_position_closed = self._position_event_handler.on_position_closed

        if self.funding_close_manager and self._position_event_handler:
            self.funding_close_manager.on_position_closed = self._position_event_handler.on_position_closed
            self._position_event_handler.set_funding_close_manager(self.funding_close_manager)

    async def _start_lifecycle(self) -> None:
        """
        Démarre le cycle de vie du bot.
        
        Cette méthode démarre le cycle de vie du bot et maintient
        le bot en vie avec une boucle d'attente.
        """
        self.logger.info("🔄 Démarrage du cycle de vie du bot...")
        components = {
            "monitoring_manager": self.monitoring_manager,
            "display_manager": self.display_manager,
            "ws_manager": self.ws_manager,
            "volatility_tracker": self.volatility_tracker,
            "metrics_monitor": self.metrics_monitor,
        }
        self.logger.info(f"🔍 Composants à démarrer: {list(components.keys())}")
        
        await self._lifecycle_manager.start_lifecycle(components)
        self.logger.info("✅ Cycle de vie démarré, démarrage de la boucle principale...")

        # Maintenir le bot en vie avec une boucle d'attente
        await self._lifecycle_manager.keep_bot_alive(components)

    def _initialize_scheduler(self, config):
        """
        Initialise le SchedulerManager pour la surveillance du funding.
        
        Cette méthode crée et configure le SchedulerManager qui surveille
        les positions et déclenche des actions basées sur les données de funding.
        
        Args:
            config: Configuration du bot contenant les paramètres de funding
            
        Side effects:
            - Crée self.scheduler
            - Lance une tâche asyncio pour la surveillance
        """
        funding_threshold = config.get('funding_threshold_minutes', 60)
        auto_trading_config = config.get('auto_trading', {})
        self.scheduler = SchedulerManager(
            self.logger, 
            funding_threshold, 
            bybit_client=self.bybit_client,
            auto_trading_config=auto_trading_config,
            on_position_opened_callback=None  # Sera défini après
        )
        # Passer une fonction callback pour récupérer les données à jour
        asyncio.create_task(self.scheduler.run_with_callback(self._get_funding_data_for_scheduler))

    def _initialize_position_monitor(self):
        """
        Initialise le PositionMonitor avec les callbacks appropriés.
        
        Cette méthode crée et démarre le PositionMonitor qui surveille
        les positions ouvertes/fermées et déclenche les callbacks appropriés.
        
        Side effects:
            - Crée self.position_monitor
            - Démarre la surveillance des positions
            - Configure les callbacks d'ouverture/fermeture
        """
        try:
            self.position_monitor = PositionMonitor(
                testnet=self.testnet,
                logger=self.logger,
                on_position_opened=self._on_position_opened,
                on_position_closed=self._on_position_closed
            )
            
            # Démarrer le PositionMonitor
            self.position_monitor.start()
            
            self.logger.info("🔍 PositionMonitor initialisé (testnet: {})", self.testnet)
            
        except Exception as e:
            self.logger.error("❌ Erreur initialisation PositionMonitor: {} (composant: surveillance positions)", 
                             str(e))
            self.position_monitor = None

    def _initialize_funding_close_manager(self):
        """
        Initialise le FundingCloseManager pour fermeture automatique après funding.
        
        Cette méthode crée et démarre le FundingCloseManager qui surveille
        les positions et les ferme automatiquement après un événement de funding.
        
        Side effects:
            - Crée self.funding_close_manager
            - Démarre la surveillance des funding
            - Configure les callbacks de fermeture
        """
        try:
            self.funding_close_manager = FundingCloseManager(
                testnet=self.testnet,
                logger=self.logger,
                bybit_client=self.bybit_client,
                on_position_closed=self._on_position_closed
            )
            self.funding_close_manager.start()
            self.logger.info("💰 FundingCloseManager initialisé (testnet: {}, client: {})", 
                            self.testnet, "configuré" if self.bybit_client else "non configuré")
        except Exception as e:
            self.logger.error("❌ Erreur initialisation FundingCloseManager: {} (composant: fermeture automatique)", 
                             str(e))
            self.funding_close_manager = None

    # ============================================================================
    # MÉTHODES DE CALLBACK POUR LES POSITIONS (DÉLÉGUÉES)
    # ============================================================================

    def _on_position_opened(self, symbol: str, position_data: Dict[str, Any]) -> None:
        """
        Callback appelé lors de l'ouverture d'une position.
        
        Cette méthode délègue le traitement de l'ouverture de position
        au PositionEventHandler qui gère la logique métier.
        
        Args:
            symbol: Symbole de la position ouverte (ex: "BTCUSDT")
            position_data: Données de la position (taille, prix, etc.)
            
        Side effects:
            - Déclenche le callback du PositionEventHandler
            - Peut modifier l'état des managers
        """
        self._position_event_handler.on_position_opened(symbol, position_data)

    def _on_position_closed(self, symbol: str, position_data: Dict[str, Any]) -> None:
        """
        Callback appelé lors de la fermeture d'une position.
        
        Cette méthode délègue le traitement de la fermeture de position
        au PositionEventHandler et retire la position du scheduler.
        
        Args:
            symbol: Symbole de la position fermée (ex: "BTCUSDT")
            position_data: Données de la position (P&L, etc.)
            
        Side effects:
            - Retire la position du scheduler
            - Déclenche le callback du PositionEventHandler
            - Peut modifier l'état des managers
        """
        # Retirer aussi du scheduler
        if self.scheduler:
            self._position_event_handler.remove_position_from_scheduler(symbol, self.scheduler)
        
        self._position_event_handler.on_position_closed(symbol, position_data)

    # ============================================================================
    # MÉTHODES DE DONNÉES ET MONITORING
    # ============================================================================

    def _get_funding_data_for_scheduler(self) -> Dict[str, Dict[str, Any]]:
        """
        Récupère les données de funding formatées pour le Scheduler.
        
        Cette méthode délègue la récupération des données de funding
        au FallbackDataManager qui gère le cache et les sources de données.
        
        Returns:
            Dict[str, Dict[str, Any]]: Données de funding formatées
                - Clé: Symbole (ex: "BTCUSDT")
                - Valeur: Dict avec funding_rate, funding_time, etc.
        """
        return self._fallback_data_manager.get_funding_data_for_scheduler()


    # ============================================================================
    # MÉTHODES DE STATUT ET ARRÊT
    # ============================================================================

    def get_status(self) -> Dict[str, Any]:
        """
        Retourne le statut actuel du bot.

        Returns:
            Dictionnaire contenant le statut du bot
        """
        return {
            "running": self.running,
            "uptime_seconds": self._lifecycle_manager.get_uptime(),
            "testnet": self.testnet,
            "health_status": self._health_monitor.get_health_status(
                self.monitoring_manager,
                self.display_manager,
                self.volatility_tracker,
            ),
            "startup_stats": self._starter.get_startup_stats(
                self.data_manager
            ),
            "lifecycle_status": {
                "is_running": self._lifecycle_manager.is_running(),
                "fallback_summary": self._fallback_data_manager.get_fallback_summary(),
            },
        }

    async def stop(self) -> None:
        """Arrête le bot de manière propre via ShutdownManager."""
        self.logger.info("🛑 Arrêt du bot... (uptime: {:.1f}s)", 
                        time.time() - self.start_time)
        self.running = False

        # Arrêter les composants spécialisés
        await self._stop_specialized_components()

        # Utiliser le BotLifecycleManager pour l'arrêt centralisé
        components = {
            "monitoring_manager": self.monitoring_manager,
            "display_manager": self.display_manager,
            "ws_manager": self.ws_manager,
            "volatility_tracker": self.volatility_tracker,
            "metrics_monitor": self.metrics_monitor,
        }
        
        await self._lifecycle_manager.stop_lifecycle(components)

    async def _stop_specialized_components(self) -> None:
        """
        Arrête les composants spécialisés (PositionMonitor, FundingCloseManager).
        
        Cette méthode arrête proprement tous les composants spécialisés
        qui ne sont pas gérés par le BotLifecycleManager principal.
        
        Side effects:
            - Arrête le PositionMonitor si actif
            - Arrête le FundingCloseManager si actif
            - Log les erreurs d'arrêt sans les propager
        """
        # Arrêter le PositionMonitor si actif
        if self.position_monitor:
            try:
                self.position_monitor.stop()
                self.logger.info("🔍 PositionMonitor arrêté (composant: surveillance positions)")
            except Exception as e:
                self.logger.warning("⚠️ Erreur arrêt PositionMonitor: {} (composant: surveillance positions)", 
                                   str(e))
        
        # Arrêter le FundingCloseManager si actif
        if self.funding_close_manager:
            try:
                self.funding_close_manager.stop()
                self.logger.info("💰 FundingCloseManager arrêté (composant: fermeture automatique)")
            except Exception as e:
                self.logger.warning("⚠️ Erreur arrêt FundingCloseManager: {} (composant: fermeture automatique)", 
                                   str(e))


class AsyncBotRunner:
    """
    Lance le BotOrchestrator dans un event loop asyncio.
    """

    def __init__(self) -> None:
        """
        Initialise l'AsyncBotRunner.
        
        Cette méthode configure le runner asynchrone qui lance le bot
        dans un event loop asyncio. Elle utilise BotFactory pour créer
        l'orchestrator avec injection de dépendances.
        
        Side effects:
            - Configure le logger
            - Crée l'orchestrator via BotFactory
            - Initialise les variables d'état
        """
        try:
            print("🔧 Configuration du logger...")
            self.logger = setup_logging()
            
            print("🏭 Import de BotFactory...")
            # NOUVEAU: Utiliser BotFactory pour créer l'orchestrator avec injection de dépendances
            from factories.bot_factory import BotFactory
            
            print("⚙️ Récupération de la configuration...")
            # Récupérer testnet depuis la configuration
            settings = get_settings()
            testnet = settings.get("testnet", True)
            
            print(f"🏭 Création du bot (testnet: {testnet})...")
            factory = BotFactory(logger=self.logger)
            self.orchestrator = factory.create_bot(testnet=testnet)
            
            print("✅ Runner initialisé avec succès")
            self.running = True
        except Exception as e:
            print(f"❌ Erreur initialisation AsyncBotRunner: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def start(self) -> None:
        """Démarre le bot de manière asynchrone."""
        self.logger.info("🚀 Démarrage du bot Bybit (mode asynchrone, testnet: {})...", 
                        self.orchestrator.testnet)
        try:
            # Configurer le signal handler pour l'arrêt propre (Windows compatible)
            self._setup_signal_handlers()

            await self.orchestrator.start()
        except asyncio.CancelledError:
            self.logger.info("⏹️ Bot arrêté par annulation de tâche (uptime: {:.1f}s)", 
                            time.time() - self.orchestrator.start_time)
        except Exception as e:
            self.logger.error("❌ Erreur critique dans le runner asynchrone: {} (type: {})", 
                             str(e), type(e).__name__, exc_info=True)
        finally:
            self.logger.info("🏁 Bot Bybit arrêté (session terminée)")

    def _setup_signal_handlers(self) -> None:
        """
        Configure les signal handlers pour l'arrêt propre.
        
        Cette méthode configure les handlers pour SIGINT (Ctrl+C) et SIGTERM
        pour permettre un arrêt propre du bot. Sur Windows, les signal handlers
        ne sont pas supportés par asyncio.
        
        Side effects:
            - Configure les handlers de signal si supportés
            - Log un avertissement si non supportés
        """
        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(
                    sig, lambda: asyncio.create_task(self.stop())
                )
        except NotImplementedError:
            # Sur Windows, les signal handlers ne sont pas supportés
            self.logger.debug(
                "Signal handlers non supportés sur cette plateforme"
            )

    async def stop(self):
        """Arrête le bot de manière asynchrone."""
        if self.running:
            self.running = False
            self.logger.info("Signal d'arrêt reçu, arrêt propre du bot...")
            # Utiliser la nouvelle méthode stop() du orchestrateur refactorisé
            # Utiliser await car stop() est maintenant asynchrone
            await self.orchestrator.stop()
            # Annuler toutes les tâches restantes pour permettre l'arrêt de l'event loop
            await self._cancel_remaining_tasks()
            self.logger.info("Toutes les tâches asynchrones ont été annulées.")
            sys.exit(0)  # Forcer la sortie après l'arrêt propre

    async def _cancel_remaining_tasks(self) -> None:
        """
        Annule toutes les tâches asyncio restantes.
        
        Cette méthode annule toutes les tâches asyncio en cours d'exécution
        pour permettre un arrêt propre de l'event loop. Elle est appelée
        lors de l'arrêt du bot pour éviter les tâches zombies.
        
        Side effects:
            - Annule toutes les tâches asyncio
            - Attend la fin de l'annulation
            - Permet l'arrêt propre de l'event loop
        """
        tasks = [
            t
            for t in asyncio.all_tasks()
            if t is not asyncio.current_task()
        ]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def main_async():
    try:
        print("🔧 Installation du handler asyncio...")
        # Installer le handler asyncio au point d'entrée principal
        install_asyncio_handler_if_needed()
        
        print("🏭 Création du runner...")
        runner = AsyncBotRunner()
        
        print("🚀 Démarrage du runner...")
        await runner.start()
    except Exception as e:
        print(f"❌ Erreur dans main_async: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    try:
        print("🚀 Démarrage du bot Bybit...")
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n🛑 Arrêt demandé par l'utilisateur (KeyboardInterrupt)")
    except Exception as e:
        print(f"❌ Erreur inattendue: {e}")
        import traceback
        traceback.print_exc()