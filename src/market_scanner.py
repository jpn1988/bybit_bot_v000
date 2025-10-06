#!/usr/bin/env python3
"""
Scanner de marché pour le bot Bybit.

Ce module contient les classes responsables du scan du marché :
- MarketScanScheduler : Planification des scans
- MarketOpportunityScanner : Scan des opportunités
- OpportunityIntegrator : Intégration des opportunités
- ContinuousMarketScanner : Orchestrateur du scan continu
"""

import asyncio
import time
from typing import List, Dict, Optional, Callable
from data_manager import DataManager
from bybit_client import BybitPublicClient
from watchlist_manager import WatchlistManager
from volatility_tracker import VolatilityTracker


class MarketScanScheduler:
    """
    Planificateur de scans de marché - Version asynchrone.

    Responsabilités :
    - Gestion de la boucle de surveillance périodique
    - Contrôle des intervalles de scan
    - Gestion des tâches asynchrones de surveillance
    """

    def __init__(self, logger):
        """Initialise le planificateur de scans."""
        self.logger = logger
        self._running = False
        self._scan_task: Optional[asyncio.Task] = None
        self._scan_interval = 60  # 1 minute entre chaque scan complet
        self._last_scan_time = 0

    async def start_scanning(self, scan_callback: Callable):
        """
        Démarre la surveillance périodique.

        Args:
            scan_callback: Fonction à appeler pour chaque scan
        """
        if self._scan_task and not self._scan_task.done():
            self.logger.warning("⚠️ Surveillance continue déjà active")
            return

        self._running = True
        self._scan_task = asyncio.create_task(
            self._scanning_loop(scan_callback)
        )

        self.logger.info("🔍 Surveillance continue démarrée")

    async def stop_scanning(self):
        """Arrête la surveillance périodique."""
        if not self._running:
            return

        self._running = False

        # Annuler la tâche de surveillance
        if self._scan_task and not self._scan_task.done():
            try:
                self._scan_task.cancel()
                # Attendre l'annulation avec timeout plus court
                try:
                    await asyncio.wait_for(
                        self._scan_task, timeout=3.0
                    )  # Timeout réduit à 3s
                except asyncio.TimeoutError:
                    self.logger.warning(
                        "⚠️ Tâche surveillance n'a pas pu être annulée dans les temps"
                    )
                except asyncio.CancelledError:
                    pass  # Annulation normale
            except Exception as e:
                self.logger.warning(
                    f"⚠️ Erreur annulation tâche surveillance: {e}"
                )

        # Nettoyer la référence de la tâche
        self._scan_task = None
        self.logger.info("🔍 Surveillance continue arrêtée")

    async def _scanning_loop(self, scan_callback: Callable):
        """Boucle de surveillance périodique asynchrone."""
        while self._running:
            try:
                # Vérification immédiate pour arrêt rapide
                if not self._running:
                    self.logger.info(
                        "🛑 Arrêt de la surveillance continue demandé"
                    )
                    break

                current_time = time.time()

                # Effectuer un scan si l'intervalle est écoulé
                if self._should_perform_scan(current_time):
                    # Exécuter le callback de manière asynchrone
                    if asyncio.iscoroutinefunction(scan_callback):
                        await scan_callback()
                    else:
                        # Exécuter dans un thread séparé si c'est une fonction synchrone
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, scan_callback)

                    self._last_scan_time = current_time

                    # Vérifier après le scan pour arrêt rapide
                    if not self._running:
                        break

                # Attendre avec vérification d'interruption
                await self._wait_with_interrupt_check(10)

            except asyncio.CancelledError:
                self.logger.info("🛑 Surveillance continue annulée")
                break
            except Exception as e:
                self.logger.warning(
                    f"⚠️ Erreur dans la boucle de surveillance continue: {e}"
                )
                if not self._running:
                    break
                # Attendre avant de continuer pour éviter une boucle d'erreur
                await asyncio.sleep(10)
                continue

    def _should_perform_scan(self, current_time: float) -> bool:
        """Vérifie s'il est temps d'effectuer un nouveau scan."""
        return self._running and (
            current_time - self._last_scan_time >= self._scan_interval
        )

    async def _wait_with_interrupt_check(self, seconds: int):
        """Attend avec vérification d'interruption."""
        for _ in range(seconds):
            if not self._running:
                break
            await asyncio.sleep(1)

    def is_running(self) -> bool:
        """Vérifie si le planificateur est en cours d'exécution."""
        return self._running and self._scan_task and not self._scan_task.done()


class MarketOpportunityScanner:
    """
    Scanner d'opportunités de marché.

    Responsabilités :
    - Scan du marché pour détecter de nouvelles opportunités
    - Construction de la watchlist via le gestionnaire
    - Gestion des clients API
    """

    def __init__(
        self,
        data_manager: DataManager,
        testnet: bool,
        logger,
        watchlist_manager: Optional[WatchlistManager] = None,
        volatility_tracker: Optional[VolatilityTracker] = None,
    ):
        """Initialise le scanner d'opportunités."""
        self.data_manager = data_manager
        self.testnet = testnet
        self.logger = logger
        self.watchlist_manager = watchlist_manager
        self.volatility_tracker = volatility_tracker

    def set_watchlist_manager(self, watchlist_manager: WatchlistManager):
        """Définit le gestionnaire de watchlist."""
        self.watchlist_manager = watchlist_manager

    def set_volatility_tracker(self, volatility_tracker: VolatilityTracker):
        """Définit le tracker de volatilité."""
        self.volatility_tracker = volatility_tracker

    def set_ws_manager(self, ws_manager):
        """Définit le gestionnaire WebSocket principal."""
        self.ws_manager = ws_manager

    def scan_for_opportunities(
        self, base_url: str, perp_data: Dict, ws_manager=None
    ) -> Optional[Dict]:
        """
        Scanne le marché pour trouver de nouvelles opportunités.

        Args:
            base_url: URL de base de l'API
            perp_data: Données des perpétuels
            ws_manager: Gestionnaire WebSocket pour vérifier l'état (optionnel)

        Returns:
            Dict avec les opportunités trouvées ou None
        """
        try:
            # Si le WebSocket est déjà actif, éviter le scan complet coûteux
            if (
                ws_manager
                and hasattr(ws_manager, "running")
                and ws_manager.running
            ):
                # Le WebSocket gère déjà les données, pas besoin de refaire
                # un scan complet
                self.logger.info("🔄 Scan évité - WebSocket déjà actif")
                return None

            # Créer un nouveau client pour éviter les problèmes de futures
            client = BybitPublicClient(testnet=self.testnet, timeout=10)
            fresh_base_url = client.public_base_url()

            # Reconstruire la watchlist (peut prendre du temps)
            if not self.watchlist_manager or not self.volatility_tracker:
                return None

            (
                linear_symbols,
                inverse_symbols,
                funding_data,
            ) = self.watchlist_manager.build_watchlist(
                fresh_base_url, perp_data, self.volatility_tracker
            )

            if linear_symbols or inverse_symbols:
                return {
                    "linear": linear_symbols,
                    "inverse": inverse_symbols,
                    "funding_data": funding_data,
                }

        except Exception as e:
            self.logger.warning(f"⚠️ Erreur scan opportunités: {e}")

        return None


class OpportunityIntegrator:
    """
    Intégrateur d'opportunités.

    Responsabilités :
    - Intégration des nouvelles opportunités dans la watchlist
    - Mise à jour des données de funding
    - Gestion des callbacks de notification
    """

    def __init__(self, data_manager: DataManager, logger):
        """Initialise l'intégrateur d'opportunités."""
        self.data_manager = data_manager
        self.logger = logger
        self._on_new_opportunity_callback: Optional[Callable] = None
        self.watchlist_manager: Optional[WatchlistManager] = None

    def set_watchlist_manager(self, watchlist_manager: WatchlistManager):
        """Définit le gestionnaire de watchlist."""
        self.watchlist_manager = watchlist_manager

    def set_on_new_opportunity_callback(self, callback: Callable):
        """Définit le callback pour les nouvelles opportunités."""
        self._on_new_opportunity_callback = callback

    def integrate_opportunities(self, opportunities: Dict):
        """
        Intègre les nouvelles opportunités détectées.

        Args:
            opportunities: Dict avec les opportunités à intégrer
        """
        linear_symbols = opportunities.get("linear", [])
        inverse_symbols = opportunities.get("inverse", [])
        funding_data = opportunities.get("funding_data", {})

        # Récupérer les symboles existants
        existing_linear = set(self.data_manager.get_linear_symbols())
        existing_inverse = set(self.data_manager.get_inverse_symbols())

        # Identifier les nouveaux symboles
        new_linear = set(linear_symbols) - existing_linear
        new_inverse = set(inverse_symbols) - existing_inverse

        if new_linear or new_inverse:
            # Mettre à jour les listes de symboles
            self._update_symbol_lists(
                linear_symbols,
                inverse_symbols,
                existing_linear,
                existing_inverse,
            )

            # Mettre à jour les données de funding
            self._update_funding_data(funding_data)

            # Notifier les nouvelles opportunités
            if self._on_new_opportunity_callback:
                try:
                    self._on_new_opportunity_callback(
                        linear_symbols, inverse_symbols
                    )
                except Exception as e:
                    self.logger.warning(
                        f"⚠️ Erreur callback nouvelles opportunités: {e}"
                    )

    def _update_symbol_lists(
        self,
        linear_symbols: List[str],
        inverse_symbols: List[str],
        existing_linear: set,
        existing_inverse: set,
    ):
        """Met à jour les listes de symboles avec les nouvelles opportunités."""
        # Fusionner les listes
        all_linear = list(existing_linear | set(linear_symbols))
        all_inverse = list(existing_inverse | set(inverse_symbols))

        # Mettre à jour dans le data manager
        self.data_manager.set_symbol_lists(all_linear, all_inverse)

    def _update_funding_data(self, new_funding_data: Dict):
        """Met à jour les données de funding avec les nouvelles opportunités."""
        # Mettre à jour chaque symbole dans le data manager
        for symbol, data in new_funding_data.items():
            if isinstance(data, (list, tuple)) and len(data) >= 4:
                funding, volume, funding_time, spread = data[:4]
                volatility = data[4] if len(data) > 4 else None
                self.data_manager.update_funding_data(
                    symbol, funding, volume, funding_time, spread, volatility
                )
            elif isinstance(data, dict):
                # Si c'est un dictionnaire, extraire les valeurs
                funding = data.get("funding", 0.0)
                volume = data.get("volume", 0.0)
                funding_time = data.get("funding_time_remaining", "-")
                spread = data.get("spread_pct", 0.0)
                volatility = data.get("volatility_pct", None)
                self.data_manager.update_funding_data(
                    symbol, funding, volume, funding_time, spread, volatility
                )

        # Mettre à jour les données originales si disponible
        if self.watchlist_manager:
            try:
                original_data = (
                    self.watchlist_manager.get_original_funding_data()
                )
                for symbol, next_funding_time in original_data.items():
                    self.data_manager.update_original_funding_data(
                        symbol, next_funding_time
                    )
            except Exception as e:
                self.logger.warning(
                    f"⚠️ Erreur mise à jour données originales: {e}"
                )


class ContinuousMarketScanner:
    """
    Scanner de marché continu pour détecter de nouvelles opportunités.

    Cette classe orchestre les composants spécialisés :
    - MarketScanScheduler : Planification des scans
    - MarketOpportunityScanner : Scan des opportunités
    - OpportunityIntegrator : Intégration des opportunités
    """

    def __init__(
        self,
        data_manager: DataManager,
        testnet: bool,
        logger,
        watchlist_manager: Optional[WatchlistManager] = None,
        volatility_tracker: Optional[VolatilityTracker] = None,
    ):
        """
        Initialise le scanner de marché continu.

        Args:
            data_manager: Gestionnaire de données
            testnet: Utiliser le testnet
            logger: Logger pour les messages
            watchlist_manager: Gestionnaire de watchlist
            volatility_tracker: Tracker de volatilité
        """
        self.data_manager = data_manager
        self.testnet = testnet
        self.logger = logger

        # Composants spécialisés
        self._scheduler = MarketScanScheduler(logger)
        self._scanner = MarketOpportunityScanner(
            data_manager,
            testnet,
            logger,
            watchlist_manager,
            volatility_tracker,
        )
        self._integrator = OpportunityIntegrator(data_manager, logger)

        # État de surveillance
        self._running = False
        self._base_url = ""
        self._perp_data = {}
        self.ws_manager = None  # Référence au WebSocket principal

    def set_watchlist_manager(self, watchlist_manager: WatchlistManager):
        """Définit le gestionnaire de watchlist."""
        self._scanner.set_watchlist_manager(watchlist_manager)
        self._integrator.set_watchlist_manager(watchlist_manager)

    def set_volatility_tracker(self, volatility_tracker: VolatilityTracker):
        """Définit le tracker de volatilité."""
        self._scanner.set_volatility_tracker(volatility_tracker)

    def set_ws_manager(self, ws_manager):
        """Définit le gestionnaire WebSocket principal."""
        self.ws_manager = ws_manager
        self._scanner.set_ws_manager(ws_manager)

    def set_on_new_opportunity_callback(self, callback: Callable):
        """Définit le callback pour les nouvelles opportunités."""
        self._integrator.set_on_new_opportunity_callback(callback)

    async def start_scanning(self, base_url: str, perp_data: Dict):
        """
        Démarre la surveillance continue du marché.

        Args:
            base_url: URL de base de l'API Bybit
            perp_data: Données des perpétuels
        """
        self._base_url = base_url
        self._perp_data = perp_data
        self._running = True

        # Démarrer le planificateur avec le callback de scan
        await self._scheduler.start_scanning(self._perform_market_scan)

    async def stop_scanning(self):
        """Arrête la surveillance continue."""
        self._running = False
        await self._scheduler.stop_scanning()

    async def _perform_market_scan(self):
        """Effectue un scan complet du marché pour détecter de nouvelles
        opportunités."""
        if not self._running:
            return

        try:
            # Scanner les opportunités (passer le ws_manager pour éviter
            # les scans inutiles)
            new_opportunities = self._scanner.scan_for_opportunities(
                self._base_url, self._perp_data, self.ws_manager
            )

            # Vérification après le scan qui peut être long
            if not self._running:
                return

            # Intégrer les opportunités si trouvées
            if new_opportunities and self._running:
                self._integrator.integrate_opportunities(new_opportunities)

        except Exception as e:
            # Ne pas logger si on est en train de s'arrêter
            if self._running:
                self.logger.warning(f"⚠️ Erreur lors du re-scan: {e}")
                # Continuer la surveillance même en cas d'erreur
                # Ne pas arrêter la boucle de surveillance

    def is_running(self) -> bool:
        """Vérifie si le scanner est en cours d'exécution."""
        return self._running and self._scheduler.is_running()
