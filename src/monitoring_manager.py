#!/usr/bin/env python3
"""
Gestionnaire de surveillance pour le bot Bybit - Version refactorisée.

Cette classe orchestre les différents composants de surveillance :
- Scanner de marché continu (market_scanner.py)
- Moniteur de candidats (candidate_monitor.py)
- Coordination des callbacks
"""

from typing import Dict, Optional, Callable
from logging_setup import setup_logging
from data_manager import DataManager
from watchlist_manager import WatchlistManager
from volatility_tracker import VolatilityTracker
from market_scanner import ContinuousMarketScanner
from candidate_monitor import CandidateMonitor


class MonitoringManager:
    """
    Gestionnaire de surveillance pour le bot Bybit.

    Cette classe orchestre les différents composants de surveillance :
    - Scanner de marché continu
    - Moniteur de candidats
    - Coordination des callbacks
    """

    def __init__(self, data_manager: DataManager, testnet: bool = True, logger=None):
        """
        Initialise le gestionnaire de surveillance.

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

        # Composants de surveillance
        self._market_scanner = ContinuousMarketScanner(
            data_manager=data_manager,
            testnet=testnet,
            logger=self.logger
        )

        self._candidate_monitor = CandidateMonitor(
            data_manager=data_manager,
            testnet=testnet,
            logger=self.logger
        )

        # Gestionnaires
        self.watchlist_manager: Optional[WatchlistManager] = None
        self.volatility_tracker: Optional[VolatilityTracker] = None
        self.ws_manager = None  # Référence au WebSocket principal

        # Callbacks
        self._on_new_opportunity_callback: Optional[Callable] = None
        self._on_candidate_ticker_callback: Optional[Callable] = None

    def set_watchlist_manager(self, watchlist_manager: WatchlistManager):
        """
        Définit le gestionnaire de watchlist.

        Args:
            watchlist_manager: Gestionnaire de watchlist
        """
        self.watchlist_manager = watchlist_manager
        self._market_scanner.set_watchlist_manager(watchlist_manager)
        self._candidate_monitor.set_watchlist_manager(watchlist_manager)

    def set_volatility_tracker(self, volatility_tracker: VolatilityTracker):
        """
        Définit le tracker de volatilité.

        Args:
            volatility_tracker: Tracker de volatilité
        """
        self.volatility_tracker = volatility_tracker
        self._market_scanner.set_volatility_tracker(volatility_tracker)

    def set_ws_manager(self, ws_manager):
        """
        Définit le gestionnaire WebSocket principal.

        Args:
            ws_manager: Gestionnaire WebSocket principal
        """
        self.ws_manager = ws_manager
        self._market_scanner.set_ws_manager(ws_manager)

    def set_on_new_opportunity_callback(self, callback: Callable):
        """
        Définit le callback pour les nouvelles opportunités.

        Args:
            callback: Fonction à appeler lors de nouvelles opportunités
        """
        self._on_new_opportunity_callback = callback
        self._market_scanner.set_on_new_opportunity_callback(callback)

    def set_on_candidate_ticker_callback(self, callback: Callable):
        """
        Définit le callback pour les tickers des candidats.

        Args:
            callback: Fonction à appeler pour chaque ticker candidat
        """
        self._on_candidate_ticker_callback = callback
        self._candidate_monitor.set_on_candidate_ticker_callback(callback)

    async def start_continuous_monitoring(self, base_url: str, perp_data: Dict):
        """
        Démarre la surveillance continue du marché.

        Args:
            base_url: URL de base de l'API Bybit
            perp_data: Données des perpétuels
        """
        if self._running:
            self.logger.warning("⚠️ Surveillance continue déjà active")
            return

        self._running = True

        # Démarrer le scanner de marché
        await self._market_scanner.start_scanning(base_url, perp_data)

        # Configurer la surveillance des candidats
        self._candidate_monitor.setup_candidate_monitoring(base_url, perp_data)

    async def stop_continuous_monitoring(self):
        """Arrête la surveillance continue."""
        if not self._running:
            return

        self._running = False

        # Nettoyer les callbacks pour éviter les fuites mémoire
        self._on_new_opportunity_callback = None
        self._on_candidate_ticker_callback = None

        # Arrêter le scanner de marché
        await self._market_scanner.stop_scanning()

        # Arrêter la surveillance des candidats
        self._candidate_monitor.stop_candidate_monitoring()

    def setup_candidate_monitoring(self, base_url: str, perp_data: Dict):
        """
        Configure la surveillance des symboles candidats.

        Args:
            base_url: URL de base de l'API Bybit
            perp_data: Données des perpétuels
        """
        self._candidate_monitor.setup_candidate_monitoring(base_url, perp_data)

    def is_running(self) -> bool:
        """
        Vérifie si le gestionnaire de surveillance est en cours d'exécution.

        Returns:
            True si en cours d'exécution
        """
        return self._running and self._market_scanner.is_running()
