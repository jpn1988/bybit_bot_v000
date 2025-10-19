#!/usr/bin/env python3
"""
Gestionnaire de surveillance unifié pour le bot Bybit.

╔═══════════════════════════════════════════════════════════════════╗
║                    📖 GUIDE DE LECTURE                            ║
╚═══════════════════════════════════════════════════════════════════╝

Ce fichier est le COORDINATEUR DE SURVEILLANCE du bot. Il orchestre
les composants spécialisés sans implémenter directement la logique métier.

🔍 COMPRENDRE CE FICHIER EN 3 MINUTES :

1. __init__() (lignes 34-68) : Initialisation des références
   └─> Prépare les références aux managers externes

2. Méthodes set_*() (lignes 70-113) : Configuration
   └─> Injecte les dépendances nécessaires

3. start_continuous_monitoring() (lignes 115-140) : Démarrage
   ├─> Initialise les composants de surveillance
   ├─> Démarre le scan périodique du marché
   └─> Configure la surveillance des candidats

4. stop_continuous_monitoring() (lignes 142-161) : Arrêt propre
   └─> Arrête tous les composants et nettoie les callbacks

🎯 COMPOSANTS COORDONNÉS :
- Scan périodique intégré : Détecte périodiquement de nouvelles opportunités
- OpportunityManager : Analyse et intègre les opportunités trouvées
- CandidateMonitor : Surveille les symboles proches des critères

📚 FLUX TYPIQUE :
1. Création du MonitoringManager
2. Configuration via set_watchlist_manager(), set_volatility_tracker(), etc.
3. Démarrage via start_continuous_monitoring()
4. Callbacks automatiques lors de découvertes
5. Arrêt propre via stop_continuous_monitoring()

⚡ RESPONSABILITÉ UNIQUE : Orchestration pure
   → Délègue toute la logique métier aux composants spécialisés
"""

import asyncio
import time
from typing import List, Dict, Optional, Callable, Any, TYPE_CHECKING
from logging_setup import setup_logging
from interfaces.monitoring_manager_interface import MonitoringManagerInterface
from config.timeouts import ScanIntervalConfig, TimeoutConfig

# Éviter les imports circulaires avec TYPE_CHECKING
if TYPE_CHECKING:
    from data_manager import DataManager
    from watchlist_manager import WatchlistManager
    from volatility_tracker import VolatilityTracker
    from opportunity_manager import OpportunityManager
    from candidate_monitor import CandidateMonitor


class MonitoringManager(MonitoringManagerInterface):
    """
    Coordinateur de surveillance pour le bot Bybit.

    Cette classe coordonne les différents composants de surveillance
    sans implémenter directement la logique métier.
    
    Responsabilité unique : Orchestration des composants de surveillance.
    """

    def __init__(
        self,
        data_manager: Any,
        testnet: bool = True,
        logger=None,
        scan_interval: int = None,
        opportunity_manager: Optional[Any] = None,
        candidate_monitor: Optional[Any] = None,
    ):
        """
        Initialise le gestionnaire de surveillance unifié.

        Args:
            data_manager: Gestionnaire de données
            testnet: Utiliser le testnet (True) ou le marché réel (False)
            logger: Logger pour les messages (optionnel)
            scan_interval: Intervalle entre chaque scan en secondes (utilise ScanIntervalConfig.MARKET_SCAN par défaut)
            opportunity_manager: Gestionnaire d'opportunités (optionnel, créé
            automatiquement si non fourni lors de l'initialisation)
            candidate_monitor: Moniteur de candidats (optionnel, créé
            automatiquement si non fourni lors de l'initialisation)
        """
        self.data_manager = data_manager
        self.testnet = testnet
        self.logger = logger or setup_logging()

        # État de surveillance
        self._running = False

        # Gestionnaires externes
        self.watchlist_manager: Optional[WatchlistManager] = None
        self.volatility_tracker: Optional[VolatilityTracker] = None
        self.ws_manager = None  # Référence au WebSocket principal

        # Scan périodique intégré (anciennement dans MarketScanner)
        self._scan_interval = scan_interval if scan_interval is not None else ScanIntervalConfig.MARKET_SCAN
        self._scan_running = False
        self._scan_task: Optional[asyncio.Task] = None
        self._last_scan_time = 0

        # Composants de surveillance (injection avec initialisation paresseuse)
        self.opportunity_manager: Optional[Any] = opportunity_manager
        self.candidate_monitor: Optional[Any] = candidate_monitor

        # Callbacks externes
        self._on_new_opportunity_callback: Optional[Callable] = None
        self._on_candidate_ticker_callback: Optional[Callable] = None

    def set_watchlist_manager(self, watchlist_manager: Any) -> None:
        """
        Définit le gestionnaire de watchlist.

        Args:
            watchlist_manager: Gestionnaire de watchlist
        """
        self.watchlist_manager = watchlist_manager

    def set_volatility_tracker(self, volatility_tracker: Any) -> None:
        """
        Définit le tracker de volatilité.

        Args:
            volatility_tracker: Tracker de volatilité
        """
        self.volatility_tracker = volatility_tracker

    def set_ws_manager(self, ws_manager):
        """
        Définit le gestionnaire WebSocket principal.

        Args:
            ws_manager: Gestionnaire WebSocket principal
        """
        self.ws_manager = ws_manager

    def set_on_new_opportunity_callback(self, callback: Callable) -> None:
        """
        Définit le callback pour les nouvelles opportunités.

        Args:
            callback: Fonction à appeler lors de nouvelles opportunités
        """
        self._on_new_opportunity_callback = callback

    def set_on_candidate_ticker_callback(self, callback: Callable) -> None:
        """
        Définit le callback pour les tickers des candidats.

        Args:
            callback: Fonction à appeler pour chaque ticker candidat
        """
        self._on_candidate_ticker_callback = callback

    def set_opportunity_manager(self, opportunity_manager: Any) -> None:
        """
        Définit le gestionnaire d'opportunités.

        Args:
            opportunity_manager: Gestionnaire d'opportunités
        """
        self.opportunity_manager = opportunity_manager

    def set_data_manager(self, data_manager: Any) -> None:
        """
        Définit le gestionnaire de données.

        Args:
            data_manager: Gestionnaire de données
        """
        self.data_manager = data_manager

    async def start_continuous_monitoring(
        self, base_url: str, perp_data: Dict
    ):
        """
        Démarre la surveillance continue du marché.

        Args:
            base_url: URL de base de l'API Bybit
            perp_data: Données des perpétuels

        Raises:
            ValueError: Si la configuration est invalide
            RuntimeError: Si l'initialisation échoue
        """
        if self._running:
            self.logger.warning("⚠️ Surveillance continue déjà active")
            return

        try:
            # Valider les paramètres d'entrée
            self._validate_monitoring_params(base_url, perp_data)

            # Initialiser les composants si nécessaire
            self._initialize_components()

            self._running = True

            # Démarrer le scan périodique du marché
            await self._start_market_scanning(base_url, perp_data)

            # Configurer la surveillance des candidats
            self._setup_candidate_monitoring(base_url, perp_data)

            self.logger.info("🔍 Surveillance continue démarrée avec succès")

        except ValueError as e:
            self.logger.error(f"❌ Configuration invalide : {e}")
            self._running = False
            raise
        except Exception as e:
            self.logger.error(f"❌ Erreur démarrage surveillance : {e}")
            self._running = False
            # Tenter un nettoyage
            await self._cleanup_on_error()
            raise RuntimeError(f"Échec démarrage surveillance : {e}") from e

    async def stop_continuous_monitoring(self):
        """
        Arrête la surveillance continue de manière propre.

        Cette méthode garantit un arrêt propre de tous les composants
        même en cas d'erreur sur l'un d'eux.
        """
        if not self._running:
            self.logger.debug("ℹ️ Surveillance déjà arrêtée")
            return

        self._running = False
        errors = []

        # Arrêter le scan du marché
        try:
            await self._stop_market_scanning()
            self.logger.debug("✓ Scan de marché arrêté")
        except Exception as e:
            errors.append(f"Scan marché: {e}")
            self.logger.warning(f"⚠️ Erreur arrêt scan marché : {e}")

        # Arrêter la surveillance des candidats
        if self.candidate_monitor:
            try:
                self.candidate_monitor.stop_monitoring()
                self.logger.debug("✓ CandidateMonitor arrêté")
            except Exception as e:
                errors.append(f"CandidateMonitor: {e}")
                self.logger.warning(f"⚠️ Erreur arrêt CandidateMonitor : {e}")

        # Nettoyer les callbacks pour éviter les fuites mémoire
        self._on_new_opportunity_callback = None
        self._on_candidate_ticker_callback = None

        if errors:
            self.logger.warning(
                f"🛑 Surveillance arrêtée avec {len(errors)} erreur(s) : {', '.join(errors)}"
            )
        else:
            self.logger.info("🛑 Surveillance continue arrêtée proprement")

    def _initialize_components(self):
        """
        Initialise les composants de surveillance de manière paresseuse.

        Cette méthode crée uniquement les composants qui n'existent pas encore.
        Cela permet de réutiliser des composants déjà configurés.

        Raises:
            ValueError: Si les dépendances requises ne sont pas configurées
        """
        # Vérifier les dépendances obligatoires
        self._validate_required_dependencies()

        # Initialiser chaque composant de manière indépendante
        self._init_opportunity_manager()
        self._init_candidate_monitor()

        self.logger.debug("✓ Composants de surveillance initialisés")

    def _validate_required_dependencies(self):
        """
        Valide que toutes les dépendances requises sont configurées.

        Raises:
            ValueError: Si une dépendance manque
        """
        if not self.watchlist_manager:
            raise ValueError("WatchlistManager doit être configuré via set_watchlist_manager()")

        if not self.volatility_tracker:
            raise ValueError("VolatilityTracker doit être configuré via set_volatility_tracker()")

    def _init_opportunity_manager(self):
        """Initialise le gestionnaire d'opportunités si nécessaire."""
        if self.opportunity_manager:
            self.logger.debug("→ OpportunityManager déjà initialisé, réutilisation")
            return

        # Import local pour éviter les imports circulaires
        from opportunity_manager import OpportunityManager
        
        self.opportunity_manager = OpportunityManager(
            data_manager=self.data_manager,
            watchlist_manager=self.watchlist_manager,
            volatility_tracker=self.volatility_tracker,
            testnet=self.testnet,
            logger=self.logger,
        )
        # Configurer les références
        self.opportunity_manager.set_ws_manager(self.ws_manager)
        self.opportunity_manager.set_on_new_opportunity_callback(
            self._on_new_opportunity_callback
        )
        self.logger.debug("→ OpportunityManager créé et configuré")

    def _init_candidate_monitor(self):
        """Initialise le moniteur de candidats si nécessaire."""
        if self.candidate_monitor:
            self.logger.debug("→ CandidateMonitor déjà initialisé, réutilisation")
            return

        # Import local pour éviter les imports circulaires
        from candidate_monitor import CandidateMonitor
        
        self.candidate_monitor = CandidateMonitor(
            data_manager=self.data_manager,
            watchlist_manager=self.watchlist_manager,
            testnet=self.testnet,
            logger=self.logger,
        )
        # Configurer le callback
        self.candidate_monitor.set_on_candidate_ticker_callback(
            self._on_candidate_ticker_callback
        )
        self.logger.debug("→ CandidateMonitor créé et configuré")

    async def _start_market_scanning(self, base_url: str, perp_data: Dict):
        """Démarre le scan périodique du marché."""
        if self._scan_task and not self._scan_task.done():
            self.logger.warning("⚠️ Scan du marché déjà actif")
            return

        self._scan_running = True
        self._scan_task = asyncio.create_task(
            self._scanning_loop(base_url, perp_data)
        )
        self.logger.info("🔍 Scanner de marché démarré")

    async def _stop_market_scanning(self):
        """Arrête le scan périodique du marché."""
        if not self._scan_running:
            return

        self._scan_running = False

        # Annuler la tâche de surveillance
        if self._scan_task and not self._scan_task.done():
            try:
                self._scan_task.cancel()
                try:
                    await asyncio.wait_for(self._scan_task, timeout=TimeoutConfig.ASYNC_TASK_SHUTDOWN)
                except asyncio.TimeoutError:
                    self.logger.warning(
                        "⚠️ Tâche scan n'a pas pu être annulée dans les temps"
                    )
                except asyncio.CancelledError:
                    pass  # Annulation normale
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur annulation tâche scan: {e}")

        self._scan_task = None
        self.logger.info("🔍 Scanner de marché arrêté")

    async def _scanning_loop(self, base_url: str, perp_data: Dict):
        """Boucle de surveillance périodique asynchrone."""
        while self._scan_running:
            try:
                # Vérification immédiate pour arrêt rapide
                if not self._scan_running:
                    self.logger.info("🛑 Arrêt du scanner demandé")
                    break

                current_time = time.time()

                # Effectuer un scan si l'intervalle est écoulé
                if self._should_perform_scan(current_time):
                    await self._perform_scan(base_url, perp_data)
                    self._last_scan_time = current_time

                    # Vérifier après le scan pour arrêt rapide
                    if not self._scan_running:
                        break

                # Attendre avec vérification d'interruption
                await self._wait_with_interrupt_check(10)

            except asyncio.CancelledError:
                self.logger.info("🛑 Scanner annulé")
                break
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur dans la boucle de scan: {e}")
                if not self._scan_running:
                    break
                # Attendre avant de continuer pour éviter une boucle d'erreur
                await asyncio.sleep(10)
                continue

    def _should_perform_scan(self, current_time: float) -> bool:
        """Vérifie s'il est temps d'effectuer un nouveau scan."""
        return self._scan_running and (
            current_time - self._last_scan_time >= self._scan_interval
        )

    async def _wait_with_interrupt_check(self, seconds: int):
        """
        Attend avec vérification d'interruption.
        
        CORRECTIF PERF-002: Optimisation pour réduire les cycles CPU en utilisant
        des délais plus longs entre les vérifications.
        """
        # CORRECTIF PERF-002: Vérifier toutes les 2 secondes au lieu d'1 seconde
        # pour réduire les cycles CPU tout en gardant une bonne réactivité
        check_interval = 2
        remaining_seconds = seconds
        
        while remaining_seconds > 0 and self._scan_running:
            sleep_time = min(check_interval, remaining_seconds)
            try:
                await asyncio.sleep(sleep_time)
                remaining_seconds -= sleep_time
            except asyncio.CancelledError:
                # Annulation normale - permettre la propagation pour arrêt propre
                raise

    async def _perform_scan(self, base_url: str, perp_data: Dict):
        """
        Effectue un scan complet du marché.
        
        Args:
            base_url: URL de base de l'API
            perp_data: Données des perpétuels
        """
        if not self._scan_running or not self.opportunity_manager:
            return

        try:
            # Scanner les opportunités
            new_opportunities = self.opportunity_manager.scan_for_opportunities(
                base_url, perp_data
            )

            # Intégrer les opportunités si trouvées
            if new_opportunities:
                self.opportunity_manager.integrate_opportunities(new_opportunities)
            
        except Exception as e:
            # Ne pas logger si on est en train de s'arrêter
            if self._scan_running:
                self.logger.warning(f"⚠️ Erreur lors du scan: {e}")

    def _setup_candidate_monitoring(self, base_url: str, perp_data: Dict):
        """
        Configure la surveillance des symboles candidats.

        Args:
            base_url: URL de base de l'API Bybit
            perp_data: Données des perpétuels
        """
        if self.candidate_monitor:
            self.candidate_monitor.setup_monitoring(base_url, perp_data)

    def setup_candidate_monitoring(self, base_url: str, perp_data: Dict):
        """
        Configure la surveillance des symboles candidats.
        
        Méthode publique pour compatibilité avec l'interface existante.

        Args:
            base_url: URL de base de l'API Bybit
            perp_data: Données des perpétuels
        """
        self._setup_candidate_monitoring(base_url, perp_data)

    def is_running(self) -> bool:
        """
        Vérifie si le gestionnaire de surveillance est en cours d'exécution.

        Returns:
            True si en cours d'exécution
        """
        scanner_running = self._scan_running
        monitor_running = (
            self.candidate_monitor.is_running()
            if self.candidate_monitor
            else False
        )
        return self._running and (scanner_running or monitor_running)

    @property
    def candidate_symbols(self) -> List[str]:
        """
        Retourne la liste des symboles candidats surveillés.
        
        Propriété pour compatibilité avec l'interface existante.

        Returns:
            Liste des symboles candidats
        """
        if self.candidate_monitor:
            return self.candidate_monitor.get_candidate_symbols()
        return []

    # ===== MÉTHODES PRIVÉES DE VALIDATION ET SUPPORT =====

    def _validate_monitoring_params(self, base_url: str, perp_data: Dict):
        """
        Valide les paramètres d'entrée pour la surveillance.

        Args:
            base_url: URL de base de l'API
            perp_data: Données des perpétuels

        Raises:
            ValueError: Si les paramètres sont invalides
        """
        if not base_url or not isinstance(base_url, str):
            raise ValueError("base_url doit être une chaîne non vide")

        if not perp_data or not isinstance(perp_data, dict):
            raise ValueError("perp_data doit être un dictionnaire non vide")

        if "linear" not in perp_data or "inverse" not in perp_data:
            raise ValueError(
                "perp_data doit contenir les clés 'linear' et 'inverse'"
            )

    async def _cleanup_on_error(self):
        """
        Nettoie les ressources en cas d'erreur lors du démarrage.

        Cette méthode est appelée automatiquement en cas d'erreur
        pour éviter les fuites de ressources.
        """
        try:
            # Tenter d'arrêter les composants déjà démarrés
            await self._stop_market_scanning()
            if self.candidate_monitor:
                self.candidate_monitor.stop_monitoring()
        except Exception as e:
            self.logger.debug(f"Erreur lors du nettoyage : {e}")

    # ===== MÉTHODES DE DIAGNOSTIC ET SANTÉ =====

    def get_health_status(self) -> Dict[str, any]:
        """
        Retourne l'état de santé détaillé du gestionnaire de surveillance.

        Returns:
            Dict contenant :
            - running: True si en cours d'exécution
            - components: État de chaque composant
            - candidate_count: Nombre de candidats surveillés
        """
        return {
            "running": self._running,
            "components": {
                "market_scanner": {
                    "initialized": True,  # Intégré directement
                    "running": self._scan_running,
                },
                "opportunity_manager": {
                    "initialized": self.opportunity_manager is not None,
                },
                "candidate_monitor": {
                    "initialized": self.candidate_monitor is not None,
                    "running": (
                        self.candidate_monitor.is_running()
                        if self.candidate_monitor
                        else False
                    ),
                },
            },
            "candidate_count": len(self.candidate_symbols),
            "callbacks_configured": {
                "new_opportunity": self._on_new_opportunity_callback is not None,
                "candidate_ticker": self._on_candidate_ticker_callback
                is not None,
            },
        }

