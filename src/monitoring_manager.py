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
- MarketScanner : Scan périodique pour détecter de nouvelles opportunités
- OpportunityDetector : Analyse et intègre les opportunités trouvées
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
from typing import List, Dict, Optional, Callable
from logging_setup import setup_logging
from data_manager import DataManager
from watchlist_manager import WatchlistManager
from volatility_tracker import VolatilityTracker
from market_scanner import MarketScanner
from opportunity_detector import OpportunityDetector
from candidate_monitor import CandidateMonitor
from config.timeouts import ScanIntervalConfig


class MonitoringManager:
    """
    Coordinateur de surveillance pour le bot Bybit.

    Cette classe coordonne les différents composants de surveillance
    sans implémenter directement la logique métier.
    
    Responsabilité unique : Orchestration des composants de surveillance.
    """

    def __init__(
        self,
        data_manager: DataManager,
        testnet: bool = True,
        logger=None,
        market_scanner: Optional[MarketScanner] = None,
        opportunity_detector: Optional[OpportunityDetector] = None,
        candidate_monitor: Optional[CandidateMonitor] = None,
    ):
        """
        Initialise le gestionnaire de surveillance unifié.

        Args:
            data_manager: Gestionnaire de données
            testnet: Utiliser le testnet (True) ou le marché réel (False)
            logger: Logger pour les messages (optionnel)
            market_scanner: Scanner de marché (optionnel, créé
            automatiquement si non fourni lors de l'initialisation)
            opportunity_detector: Détecteur d'opportunités (optionnel, créé
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

        # Composants de surveillance (injection avec initialisation paresseuse)
        self.market_scanner: Optional[MarketScanner] = market_scanner
        self.opportunity_detector: Optional[OpportunityDetector] = opportunity_detector
        self.candidate_monitor: Optional[CandidateMonitor] = candidate_monitor

        # Callbacks externes
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

    def set_ws_manager(self, ws_manager):
        """
        Définit le gestionnaire WebSocket principal.

        Args:
            ws_manager: Gestionnaire WebSocket principal
        """
        self.ws_manager = ws_manager

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
        if self.market_scanner:
            try:
                await self.market_scanner.stop_scanning()
                self.logger.debug("✓ MarketScanner arrêté")
            except Exception as e:
                errors.append(f"MarketScanner: {e}")
                self.logger.warning(f"⚠️ Erreur arrêt MarketScanner : {e}")

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
        self._init_market_scanner()
        self._init_opportunity_detector()
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

    def _init_market_scanner(self):
        """Initialise le scanner de marché si nécessaire."""
        if self.market_scanner:
            self.logger.debug("→ MarketScanner déjà initialisé, réutilisation")
            return

        self.market_scanner = MarketScanner(
            scan_interval=ScanIntervalConfig.MARKET_SCAN, logger=self.logger
        )
        self.market_scanner.set_scan_callback(self._on_market_scan)
        self.logger.debug(f"→ MarketScanner créé (intervalle: {ScanIntervalConfig.MARKET_SCAN}s)")

    def _init_opportunity_detector(self):
        """Initialise le détecteur d'opportunités si nécessaire."""
        if self.opportunity_detector:
            self.logger.debug("→ OpportunityDetector déjà initialisé, réutilisation")
            return

        self.opportunity_detector = OpportunityDetector(
            data_manager=self.data_manager,
            watchlist_manager=self.watchlist_manager,
            volatility_tracker=self.volatility_tracker,
            testnet=self.testnet,
            logger=self.logger,
        )
        # Configurer les références
        self.opportunity_detector.set_ws_manager(self.ws_manager)
        self.opportunity_detector.set_on_new_opportunity_callback(
            self._on_new_opportunity_callback
        )
        self.logger.debug("→ OpportunityDetector créé et configuré")

    def _init_candidate_monitor(self):
        """Initialise le moniteur de candidats si nécessaire."""
        if self.candidate_monitor:
            self.logger.debug("→ CandidateMonitor déjà initialisé, réutilisation")
            return

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
        if self.market_scanner:
            await self.market_scanner.start_scanning(base_url, perp_data)

    async def _on_market_scan(self, base_url: str, perp_data: Dict):
        """
        Callback appelé par le MarketScanner lors de chaque scan.
        
        Args:
            base_url: URL de base de l'API
            perp_data: Données des perpétuels
        """
        if not self.opportunity_detector:
            return

        # Scanner les opportunités
        new_opportunities = self.opportunity_detector.scan_for_opportunities(
            base_url, perp_data
        )

        # Intégrer les opportunités si trouvées
        if new_opportunities:
            self.opportunity_detector.integrate_opportunities(new_opportunities)

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
        scanner_running = (
            self.market_scanner.is_running() if self.market_scanner else False
        )
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
            if self.market_scanner:
                await self.market_scanner.stop_scanning()
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
                    "initialized": self.market_scanner is not None,
                    "running": (
                        self.market_scanner.is_running()
                        if self.market_scanner
                        else False
                    ),
                },
                "opportunity_detector": {
                    "initialized": self.opportunity_detector is not None,
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

    def get_monitoring_stats(self) -> Dict[str, any]:
        """
        Retourne les statistiques de surveillance.

        Returns:
            Dict contenant les statistiques détaillées
        """
        stats = {
            "is_running": self._running,
            "candidate_symbols_count": len(self.candidate_symbols),
        }

        # Ajouter les stats du scanner si disponible
        if self.market_scanner and hasattr(
            self.market_scanner, "get_scan_stats"
        ):
            stats["market_scanner"] = self.market_scanner.get_scan_stats()

        # Ajouter les stats du détecteur si disponible
        if self.opportunity_detector and hasattr(
            self.opportunity_detector, "get_detection_stats"
        ):
            stats["opportunity_detector"] = (
                self.opportunity_detector.get_detection_stats()
            )

        return stats

    def check_components_health(self) -> bool:
        """
        Vérifie que tous les composants critiques sont en bonne santé.

        Returns:
            True si tous les composants sont opérationnels
        """
        if not self._running:
            return False

        # Vérifier le scanner de marché
        if self.market_scanner and not self.market_scanner.is_running():
            self.logger.warning("⚠️ MarketScanner non opérationnel")
            return False

        # Vérifier le moniteur de candidats (optionnel)
        # Note : le CandidateMonitor peut ne pas être actif si pas de candidats

        return True
