#!/usr/bin/env python3
"""
Factory pour créer tous les composants du bot Bybit.

Cette factory centralise la création de tous les composants nécessaires
au fonctionnement du bot, améliorant la maintenabilité et la testabilité.

Responsabilité unique : Instancier les composants avec leurs dépendances
"""

# ============================================================================
# IMPORTS STANDARD LIBRARY
# ============================================================================
import concurrent.futures
from typing import Optional, Any, TYPE_CHECKING

# ============================================================================
# IMPORTS CONFIGURATION ET UTILITAIRES
# ============================================================================
from logging_setup import setup_logging
from config import get_settings

# ============================================================================
# IMPORTS MODELS ET STRUCTURES DE DONNÉES
# ============================================================================
from models.bot_components_bundle import BotComponentsBundle

# ============================================================================
# NOTE: Imports des composants du bot
# ============================================================================
# Les imports des composants du bot sont faits localement dans les méthodes
# pour éviter les imports circulaires et améliorer les performances


class BotComponentFactory:
    """
    Factory pour créer tous les composants du bot.

    Cette classe centralise la création de tous les composants nécessaires
    au fonctionnement du bot. Elle simplifie la complexité de BotOrchestrator
    en extrayant toute la logique de création et d'initialisation.

    Exemple d'utilisation:
        factory = BotComponentFactory(testnet=True, logger=logger)
        bundle = factory.create_all_components()

        # Injecter le bundle dans BotOrchestrator
        orchestrator = BotOrchestrator(components_bundle=bundle, logger=logger)
    """

    def __init__(self, testnet: bool, logger=None):
        """
        Initialise la factory.

        Args:
            testnet: Utiliser le testnet (True) ou le marché réel (False)
            logger: Logger pour les messages (optionnel)
        """
        self.testnet = testnet
        self.logger = logger or setup_logging()
        self.settings = get_settings()

    def create_all_components(self) -> BotComponentsBundle:
        """
        Crée tous les composants du bot et retourne un bundle.

        Cette méthode orchestre la création de tous les composants dans
        le bon ordre, respectant les dépendances entre composants.

        Ordre de création:
        1. Helpers (initializer, configurator, data_loader, starter, etc.)
        2. Managers principaux (via initializer)
        3. Composants lifecycle (lifecycle_manager, position_event_handler, etc.)
        4. Client Bybit (authentification)

        Returns:
            BotComponentsBundle: Bundle contenant tous les composants créés
        """
        self.logger.info("🏭 Création de tous les composants du bot...")

        # 1. Créer les helpers de base
        helpers = self._create_helper_components()

        # 2. Initialiser les managers via l'initializer
        managers = self._initialize_managers(helpers['initializer'])

        # 3. Créer les composants de lifecycle
        lifecycle_components = self._create_lifecycle_components(
            helpers['health_monitor'],
            helpers['shutdown_manager'],
            helpers['thread_manager']
        )

        # 4. Créer le client Bybit (optionnel)
        bybit_client = self._create_bybit_client()

        # 5. Configurer les relations entre composants
        self._configure_component_relations(
            managers,
            lifecycle_components,
            bybit_client
        )

        # 6. Construire et retourner le bundle
        bundle = BotComponentsBundle(
            # Managers principaux
            data_manager=managers['data_manager'],
            display_manager=managers['display_manager'],
            monitoring_manager=managers['monitoring_manager'],
            ws_manager=managers['ws_manager'],
            watchlist_manager=managers['watchlist_manager'],
            callback_manager=managers['callback_manager'],
            opportunity_manager=managers['opportunity_manager'],
            volatility_tracker=managers['volatility_tracker'],

            # Composants spécialisés de surveillance
            candidate_monitor=managers.get('candidate_monitor'),

            # Helpers
            initializer=helpers['initializer'],
            configurator=helpers['configurator'],
            data_loader=helpers['data_loader'],
            starter=helpers['starter'],
            health_monitor=helpers['health_monitor'],
            shutdown_manager=helpers['shutdown_manager'],
            thread_manager=helpers['thread_manager'],

            # Lifecycle
            lifecycle_manager=lifecycle_components['lifecycle_manager'],
            position_event_handler=lifecycle_components['position_event_handler'],
            fallback_data_manager=lifecycle_components['fallback_data_manager'],

            # Client
            bybit_client=bybit_client,
        )

        self.logger.info("✅ Tous les composants créés avec succès")
        return bundle

    def _create_helper_components(self) -> dict:
        """Crée les composants helper de base."""
        self.logger.debug("→ Création des helpers de base...")

        # Imports locaux pour éviter les imports circulaires
        from bot_initializer import BotInitializer
        from bot_configurator import BotConfigurator
        from data_manager import DataManager
        from bot_starter import BotStarter
        from bot_health_monitor import BotHealthMonitor
        from shutdown_manager import ShutdownManager
        from thread_manager import ThreadManager

        initializer = BotInitializer(self.testnet, self.logger)
        configurator = BotConfigurator(self.testnet, self.logger)
        data_loader = DataManager(self.testnet, self.logger)
        starter = BotStarter(self.testnet, self.logger)
        health_monitor = BotHealthMonitor(self.logger)
        shutdown_manager = ShutdownManager(self.logger)
        thread_manager = ThreadManager(self.logger)

        return {
            'initializer': initializer,
            'configurator': configurator,
            'data_loader': data_loader,
            'starter': starter,
            'health_monitor': health_monitor,
            'shutdown_manager': shutdown_manager,
            'thread_manager': thread_manager,
        }

    def _initialize_managers(self, initializer) -> dict:
        """Initialise tous les managers via l'initializer."""
        self.logger.debug("→ Initialisation des managers principaux...")

        initializer.initialize_managers()
        initializer.initialize_specialized_managers()

        # Récupérer les managers de base
        managers = initializer.get_managers()

        # NOUVEAU: Créer OpportunityManager et CandidateMonitor explicitement
        # pour les injecter dans MonitoringManager (évite initialisation paresseuse)
        self.logger.debug("→ Création des composants spécialisés de surveillance...")

        # Imports locaux pour éviter les imports circulaires
        from opportunity_manager import OpportunityManager
        from candidate_monitor import CandidateMonitor
        from monitoring_manager import MonitoringManager

        # Créer OpportunityManager
        opportunity_manager = OpportunityManager(
            data_manager=managers['data_manager'],
            logger=self.logger
        )

        # Créer CandidateMonitor
        candidate_monitor = CandidateMonitor(
            data_manager=managers['data_manager'],
            watchlist_manager=managers['watchlist_manager'],
            testnet=self.testnet,
            logger=self.logger
        )

        # Réinjecter MonitoringManager avec les composants spécialisés
        managers['monitoring_manager'] = MonitoringManager(
            data_manager=managers['data_manager'],
            testnet=self.testnet,
            logger=self.logger,
            opportunity_manager=opportunity_manager,
            candidate_monitor=candidate_monitor
        )

        # Mettre à jour opportunity_manager dans le dictionnaire
        managers['opportunity_manager'] = opportunity_manager

        # Ajouter candidate_monitor au dictionnaire
        managers['candidate_monitor'] = candidate_monitor

        # Configurer les callbacks maintenant que tout est en place
        initializer.setup_manager_callbacks()

        # Récupérer les managers mis à jour
        managers = initializer.get_managers()

        # S'assurer que candidate_monitor est bien dans le dict
        managers['candidate_monitor'] = candidate_monitor

        return managers

    def _create_lifecycle_components(
        self,
        health_monitor,
        shutdown_manager,
        thread_manager
    ) -> dict:
        """Crée les composants de gestion du cycle de vie."""
        self.logger.debug("→ Création des composants lifecycle...")

        # Imports locaux pour éviter les imports circulaires
        from bot_lifecycle_manager import BotLifecycleManager
        from position_event_handler import PositionEventHandler
        from fallback_data_manager import FallbackDataManager

        lifecycle_manager = BotLifecycleManager(
            testnet=self.testnet,
            logger=self.logger,
            health_monitor=health_monitor,
            shutdown_manager=shutdown_manager,
            thread_manager=thread_manager,
        )

        position_event_handler = PositionEventHandler(
            testnet=self.testnet,
            logger=self.logger,
        )

        fallback_data_manager = FallbackDataManager(
            testnet=self.testnet,
            logger=self.logger,
        )

        return {
            'lifecycle_manager': lifecycle_manager,
            'position_event_handler': position_event_handler,
            'fallback_data_manager': fallback_data_manager,
        }

    def _create_bybit_client(self) -> Optional[Any]:
        """Crée le client Bybit avec authentification."""
        self.logger.debug("→ Test de connexion Bybit authentifiée...")

        # Import local pour éviter les imports circulaires
        from bybit_client import BybitClient

        api_key = self.settings.get("api_key")
        api_secret = self.settings.get("api_secret")
        recv_window_ms = int(self.settings.get("recv_window_ms") or 7000)
        time_sync_enabled = bool(self.settings.get("time_sync_enabled", True))
        time_sync_interval = int(self.settings.get("time_sync_interval_seconds") or 60)
        private_max_retries = int(self.settings.get("private_max_retries") or 4)
        private_backoff_base = float(self.settings.get("private_backoff_base") or 0.5)

        if not api_key or not api_secret:
            self.logger.warning("🔒 Clés API non configurées : connexion authentifiée désactivée.")
            return None

        try:
            # Exécuter la logique synchrone dans un thread dédié pour éviter PERF-002
            def _sync_connection_test():
                client = BybitClient(
                    testnet=self.testnet,
                    timeout=self.settings["timeout"],
                    api_key=api_key,
                    api_secret=api_secret,
                    max_retries=private_max_retries,
                    backoff_base=private_backoff_base,
                    recv_window_ms=recv_window_ms,
                    time_sync_enabled=time_sync_enabled,
                    time_sync_interval_seconds=time_sync_interval,
                )
                return client.get_wallet_balance(account_type="UNIFIED")

            # Utiliser concurrent.futures pour éviter les problèmes d'event loop
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(_sync_connection_test)
                future.result()  # Vérifier que la connexion fonctionne

            client = BybitClient(
                testnet=self.testnet,
                timeout=self.settings["timeout"],
                api_key=api_key,
                api_secret=api_secret,
                max_retries=private_max_retries,
                backoff_base=private_backoff_base,
                recv_window_ms=recv_window_ms,
                time_sync_enabled=time_sync_enabled,
                time_sync_interval_seconds=time_sync_interval,
            )

            balance = self._extract_usdt_balance(client.get_wallet_balance(account_type="UNIFIED"))
            self.logger.info(f"✅ Bybit connecté ({'testnet' if self.testnet else 'mainnet'}) en mode authentifié. Balance : {balance} USDT")
            return client

        except Exception as e:
            self.logger.error(f"❌ Vérification Bybit authentifiée échouée : {e}")
            return None

    def _extract_usdt_balance(self, wallet_response: dict) -> str:
        """Extrait le solde USDT de la réponse de l'API Bybit."""
        try:
            account_list = wallet_response.get("list", [])
            if not account_list:
                return "N/A"

            account = account_list[0]
            total_balance = account.get("totalWalletBalance")

            if total_balance and total_balance != "0":
                return f"{float(total_balance):.2f}"

            coins = account.get("coin", [])
            for coin in coins:
                if coin.get("coin") == "USDT":
                    usdt_balance = coin.get("walletBalance", "0")
                    return f"{float(usdt_balance):.2f}"

            return f"{float(total_balance or 0):.2f}"

        except (ValueError, TypeError, KeyError, IndexError) as e:
            self.logger.debug(f"Erreur extraction solde USDT: {e}")
            return "N/A"

    def _configure_component_relations(
        self,
        managers: dict,
        lifecycle_components: dict,
        bybit_client: Optional[Any]
    ):
        """Configure les relations entre composants."""
        self.logger.debug("→ Configuration des relations entre composants...")

        # Configurer le monitoring_manager avec le bybit_client
        if bybit_client:
            managers['monitoring_manager'].set_bybit_client(bybit_client)

        # Configurer le position_event_handler avec les managers
        lifecycle_components['position_event_handler'].set_monitoring_manager(
            managers['monitoring_manager']
        )
        lifecycle_components['position_event_handler'].set_ws_manager(
            managers['ws_manager']
        )
        lifecycle_components['position_event_handler'].set_display_manager(
            managers['display_manager']
        )
        lifecycle_components['position_event_handler'].set_data_manager(
            managers['data_manager']
        )

        # Configurer le fallback_data_manager avec les managers
        lifecycle_components['fallback_data_manager'].set_data_manager(
            managers['data_manager']
        )
        lifecycle_components['fallback_data_manager'].set_watchlist_manager(
            managers['watchlist_manager']
        )

        # Configurer le lifecycle_manager avec le callback de funding update
        lifecycle_components['lifecycle_manager'].set_on_funding_update_callback(
            lifecycle_components['fallback_data_manager'].update_funding_data_periodically
        )

        self.logger.debug("→ Relations configurées avec succès")
