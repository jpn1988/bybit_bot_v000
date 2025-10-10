#!/usr/bin/env python3
"""
Gestionnaire de surveillance unifié pour le bot Bybit.

Cette classe coordonne les différents composants de surveillance :
- MarketScanner : Scan périodique du marché
- OpportunityDetector : Détection et intégration d'opportunités
- CandidateMonitor : Surveillance WebSocket des candidats

Cette version refactorisée suit le principe de responsabilité unique.
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
    ):
        """
        Initialise le gestionnaire de surveillance unifié.

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

        # Gestionnaires externes
        self.watchlist_manager: Optional[WatchlistManager] = None
        self.volatility_tracker: Optional[VolatilityTracker] = None
        self.ws_manager = None  # Référence au WebSocket principal

        # Composants de surveillance (initialisés après set_watchlist_manager)
        self.market_scanner: Optional[MarketScanner] = None
        self.opportunity_detector: Optional[OpportunityDetector] = None
        self.candidate_monitor: Optional[CandidateMonitor] = None

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
        """
        if self._running:
            self.logger.warning("⚠️ Surveillance continue déjà active")
            return

        # Initialiser les composants si nécessaire
        self._initialize_components()

        self._running = True

        # Démarrer le scan périodique du marché
        await self._start_market_scanning(base_url, perp_data)

        # Configurer la surveillance des candidats
        self._setup_candidate_monitoring(base_url, perp_data)

        self.logger.info("🔍 Surveillance continue démarrée")

    async def stop_continuous_monitoring(self):
        """Arrête la surveillance continue."""
        if not self._running:
            return

        self._running = False

        # Arrêter le scan du marché
        if self.market_scanner:
            await self.market_scanner.stop_scanning()

        # Arrêter la surveillance des candidats
        if self.candidate_monitor:
            self.candidate_monitor.stop_monitoring()

        # Nettoyer les callbacks pour éviter les fuites mémoire
        self._on_new_opportunity_callback = None
        self._on_candidate_ticker_callback = None

        self.logger.info("🛑 Surveillance continue arrêtée")

    def _initialize_components(self):
        """Initialise les composants de surveillance."""
        if not self.watchlist_manager or not self.volatility_tracker:
            raise ValueError(
                "WatchlistManager et VolatilityTracker doivent être définis"
            )

        # Créer le scanner de marché si nécessaire
        if not self.market_scanner:
            self.market_scanner = MarketScanner(
                scan_interval=60, logger=self.logger
            )
            # Définir le callback pour effectuer le scan
            self.market_scanner.set_scan_callback(self._on_market_scan)

        # Créer le détecteur d'opportunités si nécessaire
        if not self.opportunity_detector:
            self.opportunity_detector = OpportunityDetector(
                data_manager=self.data_manager,
                watchlist_manager=self.watchlist_manager,
                volatility_tracker=self.volatility_tracker,
                testnet=self.testnet,
                logger=self.logger,
            )
            # Transférer les références
            self.opportunity_detector.set_ws_manager(self.ws_manager)
            self.opportunity_detector.set_on_new_opportunity_callback(
                self._on_new_opportunity_callback
            )

        # Créer le moniteur de candidats si nécessaire
        if not self.candidate_monitor:
            self.candidate_monitor = CandidateMonitor(
                data_manager=self.data_manager,
                watchlist_manager=self.watchlist_manager,
                testnet=self.testnet,
                logger=self.logger,
            )
            # Transférer le callback
            self.candidate_monitor.set_on_candidate_ticker_callback(
                self._on_candidate_ticker_callback
            )

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
