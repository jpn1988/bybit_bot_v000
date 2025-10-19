#!/usr/bin/env python3
"""
Orchestrateur principal du bot Bybit.

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
"""

import asyncio
import signal
import sys
import time
import atexit
from typing import Dict, Any
from logging_setup import setup_logging

from config import get_settings
from http_client_manager import close_all_http_clients
from metrics_monitor import start_metrics_monitoring
from bybit_client import BybitClient

# Import des composants refactorisés
from bot_initializer import BotInitializer
from bot_configurator import BotConfigurator
from data_manager import DataManager
from bot_starter import BotStarter
from bot_health_monitor import BotHealthMonitor
from shutdown_manager import ShutdownManager
from thread_manager import ThreadManager
from thread_exception_handler import install_global_exception_handlers, install_asyncio_handler_if_needed


class BotOrchestrator:
    """
    Orchestrateur principal du bot Bybit.

    Cette classe coordonne les différents composants spécialisés :
    - BotInitializer : Initialisation des managers
    - BotConfigurator : Configuration du bot
    - DataManager : Gestion des données
    - BotStarter : Démarrage des composants
    - BotHealthMonitor : Surveillance de la santé
    - ShutdownManager : Gestion de l'arrêt
    - ThreadManager : Gestion des threads
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
        """
        self.logger = logger or setup_logging()
        self.running = True

        # Installer les handlers globaux pour exceptions non capturées
        # IMPORTANT : À faire avant de créer des threads ou tâches asyncio
        install_global_exception_handlers(self.logger)

        # S'assurer que les clients HTTP sont fermés à l'arrêt
        atexit.register(close_all_http_clients)

        # Configuration
        settings = get_settings()
        self.testnet = settings["testnet"]
        
        # Test de connexion Bybit authentifiée (exécuté dans un thread dédié pour éviter PERF-002)
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


    def _test_bybit_auth_connection_sync(self) -> bool:
        """
        Teste la connexion à l'API Bybit avec authentification complète.
        Vérifie les clés BYBIT_API_KEY/BYBIT_API_SECRET depuis .env
        et log le statut de la connexion.
        
        Utilise concurrent.futures.ThreadPoolExecutor pour exécuter dans un thread dédié
        et supprimer le warning PERF-002.
        """
        settings = get_settings()
        testnet = settings["testnet"]
        api_key = settings["api_key"]
        api_secret = settings["api_secret"]

        if not api_key or not api_secret:
            self.logger.warning("🔒 Clés API non configurées : connexion authentifiée désactivée.")
            return False

        try:
            # Exécuter la logique synchrone dans un thread dédié pour éviter PERF-002
            def _sync_connection_test():
                client = BybitClient(
                    testnet=testnet,
                    timeout=settings["timeout"],
                    api_key=api_key,
                    api_secret=api_secret,
                )
                return client.get_wallet_balance(account_type="UNIFIED")
            
            # Utiliser concurrent.futures pour éviter les problèmes d'event loop
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(_sync_connection_test)
                result = future.result()
            
            balance = self._extract_usdt_balance(result)
            self.logger.info(f"✅ Bybit connecté ({'testnet' if testnet else 'mainnet'}) en mode authentifié. Balance : {balance} USDT")
            return True
        except Exception as e:
            self.logger.error(f"❌ Vérification Bybit authentifiée échouée : {e}")
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
            self.logger.debug(f"Erreur extraction solde USDT: {e}")
            return "N/A"

    async def start(self):
        """Démarre le suivi des prix avec filtrage par funding."""
        # Installer le handler asyncio pour la boucle événementielle actuelle
        install_asyncio_handler_if_needed()
        
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

    async def stop(self):
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
            # CORRECTIF : Utiliser await au lieu d'asyncio.run()
            # pour éviter de créer une nouvelle event loop imbriquée
            await self._shutdown_manager.stop_all_managers_async(managers)

            self.logger.info("✅ Bot arrêté proprement via ShutdownManager")

        except Exception as e:
            self.logger.error(f"❌ Erreur lors de l'arrêt: {e}")


class AsyncBotRunner:
    """
    Lance le BotOrchestrator dans un event loop asyncio.
    """

    def __init__(self):
        self.logger = setup_logging()
        self.orchestrator = BotOrchestrator()
        self.running = True

    async def start(self):
        """Démarre le bot de manière asynchrone."""
        self.logger.info("Démarrage du bot Bybit (mode asynchrone)...")
        try:
            # Configurer le signal handler pour l'arrêt propre (Windows compatible)
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

            await self.orchestrator.start()
        except asyncio.CancelledError:
            self.logger.info("Bot arrêté par annulation de tâche.")
        except Exception as e:
            self.logger.error(
                f"Erreur critique dans le runner asynchrone: {e}",
                exc_info=True,
            )
        finally:
            self.logger.info("Bot Bybit arrêté.")

    async def stop(self):
        """Arrête le bot de manière asynchrone."""
        if self.running:
            self.running = False
            self.logger.info("Signal d'arrêt reçu, arrêt propre du bot...")
            # Utiliser la nouvelle méthode stop() du orchestrateur refactorisé
            # CORRECTIF : Utiliser await car stop() est maintenant asynchrone
            await self.orchestrator.stop()
            # Annuler toutes les tâches restantes pour permettre l'arrêt de l'event loop
            tasks = [
                t
                for t in asyncio.all_tasks()
                if t is not asyncio.current_task()
            ]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            self.logger.info("Toutes les tâches asynchrones ont été annulées.")
            sys.exit(0)  # Forcer la sortie après l'arrêt propre


async def main_async():
    # Installer le handler asyncio au point d'entrée principal
    install_asyncio_handler_if_needed()
    
    runner = AsyncBotRunner()
    await runner.start()


if __name__ == "__main__":
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nArrêt demandé par l'utilisateur (KeyboardInterrupt)")
    except Exception as e:
        print(f"Erreur inattendue: {e}")
