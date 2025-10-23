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
from scheduler_manager import SchedulerManager
from position_monitor import PositionMonitor
from funding_close_manager import FundingCloseManager
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
        from metrics_monitor import metrics_monitor
        self.metrics_monitor = metrics_monitor

    # ============================================================================
    # MÉTHODES D'INITIALISATION
    # ============================================================================

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

    # ============================================================================
    # MÉTHODES DE DÉMARRAGE
    # ============================================================================

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

        # 7. Initialiser et démarrer le Scheduler pour la surveillance du funding
        self._initialize_scheduler(config)

        # 8. Initialiser le PositionMonitor
        self._initialize_position_monitor()
        
        # 9. Initialiser le FundingCloseManager
        self._initialize_funding_close_manager()
        
        # 10. Définir le callback du scheduler après l'initialisation
        if self.scheduler:
            self.scheduler.on_position_opened_callback = self._on_position_opened

        # 11. Maintenir le bot en vie avec une boucle d'attente
        await self._keep_bot_alive()

    def _initialize_scheduler(self, config):
        """Initialise le SchedulerManager pour la surveillance du funding."""
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
            
            self.logger.info("🔍 PositionMonitor initialisé")
            
        except Exception as e:
            self.logger.error(f"❌ Erreur initialisation PositionMonitor: {e}")
            self.position_monitor = None

    def _initialize_funding_close_manager(self):
        """Initialise le FundingCloseManager pour fermeture automatique après funding."""
        try:
            self.funding_close_manager = FundingCloseManager(
                testnet=self.testnet,
                logger=self.logger,
                bybit_client=self.bybit_client,
                on_position_closed=self._on_position_closed
            )
            self.funding_close_manager.start()
            self.logger.info("💰 FundingCloseManager initialisé")
        except Exception as e:
            self.logger.error(f"❌ Erreur initialisation FundingCloseManager: {e}")
            self.funding_close_manager = None

    # ============================================================================
    # MÉTHODES DE CALLBACK POUR LES POSITIONS
    # ============================================================================

    def _on_position_opened(self, symbol: str, position_data: Dict[str, Any]):
        """
        Callback appelé lors de l'ouverture d'une position.
        
        Args:
            symbol: Symbole de la position ouverte
            position_data: Données de la position
        """
        try:
            self.logger.info(f"📈 Position ouverte détectée: {symbol}")
            
            # Ajouter la position active
            if self.monitoring_manager:
                self.monitoring_manager.add_active_position(symbol)
            
            # Basculer vers le symbole unique seulement si c'est la première position
            if self.ws_manager and len(self.monitoring_manager.get_active_positions()) == 1:
                self._switch_to_single_symbol(symbol)
            
            # Filtrer l'affichage vers le symbole unique
            if self.display_manager:
                self.display_manager.set_symbol_filter({symbol})
            
            # Ajouter la position à la surveillance du funding
            if self.funding_close_manager:
                self.funding_close_manager.add_position_to_monitor(symbol)
            
            self.logger.info(f"⏸️ Watchlist en pause - Position ouverte sur {symbol}")
            
        except Exception as e:
            self.logger.error(f"❌ Erreur callback position ouverte: {e}")

    def _switch_to_single_symbol(self, symbol: str):
        """Bascule vers un symbole unique dans le WebSocket."""
        # Déterminer la catégorie du symbole
        category = "linear" if symbol.endswith("USDT") else "inverse"
        
        # Basculer vers le symbole unique (asynchrone)
        import asyncio
        asyncio.create_task(
            self.ws_manager.switch_to_single_symbol(symbol, category)
        )

    def _on_position_closed(self, symbol: str, position_data: Dict[str, Any]):
        """
        Callback appelé lors de la fermeture d'une position.
        
        Args:
            symbol: Symbole de la position fermée
            position_data: Données de la position
        """
        try:
            self.logger.info(f"📉 Position fermée détectée: {symbol}")
            
            # Retirer la position active
            if self.monitoring_manager:
                self.monitoring_manager.remove_active_position(symbol)
            
            # Retirer aussi du scheduler
            if self.scheduler:
                self.scheduler.remove_position(symbol)
            
            # Restaurer la watchlist complète seulement si plus de positions actives
            if (self.ws_manager and self.data_manager and 
                not self.monitoring_manager.has_active_positions()):
                self._restore_full_watchlist()
            
            # Restaurer l'affichage de tous les symboles
            if self.display_manager:
                self.display_manager.clear_symbol_filter()
            
            # Retirer la position de la surveillance du funding
            if self.funding_close_manager:
                self.funding_close_manager.remove_position_from_monitor(symbol)
            
            self.logger.info("▶️ Watchlist reprise - Position fermée")
            
        except Exception as e:
            self.logger.error(f"❌ Erreur callback position fermée: {e}")

    def _restore_full_watchlist(self):
        """Restaure la watchlist complète dans le WebSocket."""
        linear_symbols = self.data_manager.storage.get_linear_symbols()
        inverse_symbols = self.data_manager.storage.get_inverse_symbols()
        
        # Restaurer la watchlist complète (asynchrone)
        import asyncio
        asyncio.create_task(
            self.ws_manager.restore_full_watchlist(linear_symbols, inverse_symbols)
        )

    # ============================================================================
    # MÉTHODES DE DONNÉES ET MONITORING
    # ============================================================================

    def _get_funding_data_for_scheduler(self) -> Dict[str, Dict[str, Any]]:
        """
        Récupère les données de funding formatées pour le Scheduler.
        Calcule dynamiquement le temps restant à partir des timestamps temps réel.
        
        Returns:
            Dict avec les données de funding formatées pour chaque symbole
        """
        funding_data = {}
        selected_symbols = self.watchlist_manager.get_selected_symbols()
        self.logger.debug(f"[SCHEDULER] Symboles sélectionnés: {len(selected_symbols)}")
        
        for symbol in selected_symbols:
            funding_info = self._get_symbol_funding_data(symbol)
            if funding_info:
                funding_data[symbol] = funding_info
        
        self.logger.debug(f"[SCHEDULER] Données récupérées: {len(funding_data)} symboles")
        return funding_data

    def _get_symbol_funding_data(self, symbol: str) -> Dict[str, Any]:
        """Récupère les données de funding pour un symbole spécifique."""
        # Récupérer les données temps réel (mises à jour via WebSocket)
        realtime_info = self.data_manager.storage.get_realtime_data(symbol)
        
        if realtime_info and realtime_info.get("next_funding_time"):
            # Calculer le temps restant à partir du timestamp temps réel
            next_funding_timestamp = realtime_info["next_funding_time"]
            funding_time_str = self.watchlist_manager.calculate_funding_time_remaining(next_funding_timestamp)
            
            funding_data = {
                'next_funding_time': funding_time_str,  # Recalculé dynamiquement
                'funding_rate': realtime_info.get('funding_rate'),
                'volume_24h': realtime_info.get('volume24h')
            }
            self.logger.debug(f"[SCHEDULER] {symbol}: {funding_time_str} (temps réel)")
            return funding_data
        else:
            # Fallback sur les données originales si pas de données temps réel
            return self._get_fallback_funding_data(symbol)

    def _get_fallback_funding_data(self, symbol: str) -> Dict[str, Any]:
        """Récupère les données de funding en fallback depuis les données originales."""
        funding_obj = self.data_manager.storage.get_funding_data_object(symbol)
        if funding_obj:
            original_timestamp = self.data_manager.storage.get_original_funding_data(symbol)
            if original_timestamp:
                funding_time_str = self.watchlist_manager.calculate_funding_time_remaining(original_timestamp)
            else:
                funding_time_str = funding_obj.next_funding_time
                
            funding_data = {
                'next_funding_time': funding_time_str,
                'funding_rate': funding_obj.funding_rate,
                'volume_24h': funding_obj.volume_24h
            }
            self.logger.debug(f"[SCHEDULER] {symbol}: {funding_time_str} (fallback)")
            return funding_data
        else:
            self.logger.debug(f"[SCHEDULER] Aucune donnée pour {symbol}")
            return None

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

            # Arrêter les composants spécialisés
            await self._stop_specialized_components()

            # Utiliser ShutdownManager pour l'arrêt asynchrone
            # CORRECTIF : Utiliser await au lieu d'asyncio.run()
            # pour éviter de créer une nouvelle event loop imbriquée
            await self._shutdown_manager.stop_all_managers_async(managers)

            self.logger.info("✅ Bot arrêté proprement via ShutdownManager")

        except Exception as e:
            self.logger.error(f"❌ Erreur lors de l'arrêt: {e}")

    async def _stop_specialized_components(self):
        """Arrête les composants spécialisés (PositionMonitor, FundingCloseManager)."""
        # Arrêter le PositionMonitor si actif
        if self.position_monitor:
            try:
                self.position_monitor.stop()
                self.logger.info("🔍 PositionMonitor arrêté")
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur arrêt PositionMonitor: {e}")
        
        # Arrêter le FundingCloseManager si actif
        if self.funding_close_manager:
            try:
                self.funding_close_manager.stop()
                self.logger.info("💰 FundingCloseManager arrêté")
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur arrêt FundingCloseManager: {e}")


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
            self._setup_signal_handlers()

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

    def _setup_signal_handlers(self):
        """Configure les signal handlers pour l'arrêt propre."""
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
            # CORRECTIF : Utiliser await car stop() est maintenant asynchrone
            await self.orchestrator.stop()
            # Annuler toutes les tâches restantes pour permettre l'arrêt de l'event loop
            await self._cancel_remaining_tasks()
            self.logger.info("Toutes les tâches asynchrones ont été annulées.")
            sys.exit(0)  # Forcer la sortie après l'arrêt propre

    async def _cancel_remaining_tasks(self):
        """Annule toutes les tâches asyncio restantes."""
        tasks = [
            t
            for t in asyncio.all_tasks()
            if t is not asyncio.current_task()
        ]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


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