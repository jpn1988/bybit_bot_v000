#!/usr/bin/env python3
"""
Orchestrateur principal du bot Bybit - Version refactorisée.

Cette classe coordonne les différents composants spécialisés :
- BotInitializer : Initialisation des managers
- BotConfigurator : Configuration du bot
    - UnifiedDataManager : Gestion unifiée des données
- BotStarter : Démarrage des composants
- BotHealthMonitor : Surveillance de la santé
- ShutdownManager : Gestion de l'arrêt
- ThreadManager : Gestion des threads
"""

import asyncio
import time
import atexit
from typing import Dict, Any
from logging_setup import setup_logging

# cleaned: removed unused imports (log_startup_summary, log_shutdown_summary)
from config_unified import get_settings
from http_client_manager import close_all_http_clients
from metrics_monitor import start_metrics_monitoring

# Import des composants refactorisés
from bot_initializer import BotInitializer
from bot_configurator import BotConfigurator
from unified_data_manager import UnifiedDataManager, set_global_data_manager
from bot_starter import BotStarter
from bot_health_monitor import BotHealthMonitor
from shutdown_manager import ShutdownManager
from thread_manager import ThreadManager


class BotOrchestrator:
    """
    Orchestrateur principal du bot Bybit - Version refactorisée.

    Cette classe coordonne les différents composants spécialisés :
    - BotInitializer : Initialisation des managers
    - BotConfigurator : Configuration du bot
    - UnifiedDataManager : Gestion unifiée des données
    - BotStarter : Démarrage des composants
    - BotHealthMonitor : Surveillance de la santé
    - ShutdownManager : Gestion de l'arrêt
    - ThreadManager : Gestion des threads
    """

    def __init__(self):
        """Initialise l'orchestrateur du bot."""
        self.logger = setup_logging()
        self.running = True

        # S'assurer que les clients HTTP sont fermés à l'arrêt
        atexit.register(close_all_http_clients)

        # Configuration
        settings = get_settings()
        self.testnet = settings["testnet"]

        # Initialiser les composants spécialisés
        self._initializer = BotInitializer(self.testnet, self.logger)
        self._configurator = BotConfigurator(self.testnet, self.logger)
        self._data_loader = UnifiedDataManager(self.testnet, self.logger)
        self._starter = BotStarter(self.testnet, self.logger)
        self._health_monitor = BotHealthMonitor(self.logger)

        # Initialiser les nouveaux managers
        self._shutdown_manager = ShutdownManager(self.logger)
        self._thread_manager = ThreadManager(self.logger)

        # Initialiser les managers via l'initialiseur
        self._initialize_components()

        # Configuration du signal handler pour Ctrl+C via ShutdownManager
        self._shutdown_manager.setup_signal_handler(self)

        # Initialiser le temps de démarrage pour l'uptime
        self.start_time = time.time()

        # Démarrer le monitoring des métriques
        start_metrics_monitoring(interval_minutes=5)

        # Stocker la référence au moniteur de métriques pour l'arrêt
        from metrics_monitor import metrics_monitor

        self.metrics_monitor = metrics_monitor

    def _initialize_components(self):
        """Initialise tous les composants du bot."""
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

        # Configurer le gestionnaire global pour la compatibilité avec price_store.py
        set_global_data_manager(self.data_manager)

    async def start(self):
        """Démarre le suivi des prix avec filtrage par funding."""
        try:
            # 1. Charger et valider la configuration
            config = self._configurator.load_and_validate_config(
                self.watchlist_manager.config_manager
            )
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
            return

        # 5. Afficher le résumé de démarrage
        self._starter.display_startup_summary(
            config, perp_data, self.data_manager
        )

        # 6. Démarrer tous les composants
        await self._starter.start_bot_components(
            self.volatility_tracker,
            self.display_manager,
            self.ws_manager,
            self.data_manager,
            self.monitoring_manager,
            base_url,
            perp_data,
        )

        # 7. Maintenir le bot en vie avec une boucle d'attente
        await self._keep_bot_alive()

    async def _keep_bot_alive(self):
        """Maintient le bot en vie avec une boucle d'attente et monitoring mémoire."""
        self.logger.info("🔄 Bot opérationnel - surveillance continue...")

        try:
            while self.running:
                # Vérifier que tous les composants principaux sont toujours actifs
                if not self._health_monitor.check_components_health(
                    self.monitoring_manager,
                    self.display_manager,
                    self.volatility_tracker,
                ):
                    self.logger.warning(
                        "⚠️ Un composant critique s'est arrêté, redémarrage..."
                    )
                    # Optionnel: redémarrer les composants défaillants

                # Monitoring mémoire périodique
                if self._health_monitor.should_check_memory():
                    self._health_monitor.monitor_memory_usage()

                # Attendre avec vérification d'interruption
                await asyncio.sleep(1.0)

        except asyncio.CancelledError:
            self.logger.info("🛑 Arrêt demandé par l'utilisateur")
            self.running = False
        except Exception as e:
            self.logger.error(f"❌ Erreur dans la boucle principale: {e}")
            self.running = False

    def get_status(self) -> Dict[str, Any]:
        """
        Retourne le statut actuel du bot.

        Returns:
            Dictionnaire contenant le statut du bot
        """
        return {
            "running": self.running,
            "uptime_seconds": time.time() - self.start_time,
            "testnet": self.testnet,
            "health_status": self._health_monitor.get_health_status(
                self.monitoring_manager,
                self.display_manager,
                self.volatility_tracker,
            ),
            "startup_stats": self._starter.get_startup_stats(
                self.data_manager
            ),
        }

    def stop(self):
        """Arrête le bot de manière propre via ShutdownManager."""
        self.logger.info("🛑 Arrêt du bot...")
        self.running = False

        # Utiliser ShutdownManager pour l'arrêt centralisé
        try:
            # Préparer le dictionnaire des managers pour ShutdownManager
            managers = {
                "monitoring_manager": self.monitoring_manager,
                "display_manager": self.display_manager,
                "ws_manager": self.ws_manager,
                "volatility_tracker": self.volatility_tracker,
                "metrics_monitor": self.metrics_monitor,
            }

            # Utiliser ShutdownManager pour l'arrêt asynchrone
            asyncio.run(
                self._shutdown_manager.stop_all_managers_async(managers)
            )

            self.logger.info("✅ Bot arrêté proprement via ShutdownManager")

        except Exception as e:
            self.logger.error(f"❌ Erreur lors de l'arrêt: {e}")


# Point d'entrée géré par bot.py
