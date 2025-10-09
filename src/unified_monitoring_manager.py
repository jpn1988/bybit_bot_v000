#!/usr/bin/env python3
"""
Gestionnaire de surveillance unifié pour le bot Bybit.

Cette classe consolide toutes les fonctionnalités de surveillance :
- Surveillance continue du marché (scan périodique)
- Surveillance des candidats en temps réel
- Détection d'opportunités
- Gestion WebSocket pour les candidats
- Coordination des callbacks

Cette version unifiée remplace les anciens composants de surveillance.
"""

import asyncio
import threading
import time
from typing import List, Dict, Optional, Callable
from logging_setup import setup_logging
from unified_data_manager import UnifiedDataManager
from watchlist_manager import WatchlistManager
from volatility_tracker import VolatilityTracker
from bybit_client import BybitPublicClient
from instruments import category_of_symbol
from models.funding_data import FundingData


class UnifiedMonitoringManager:
    """
    Gestionnaire de surveillance unifié pour le bot Bybit.

    Cette classe consolide toutes les fonctionnalités de surveillance :
    - Surveillance continue du marché (scan périodique)
    - Surveillance des candidats en temps réel
    - Détection d'opportunités
    - Gestion WebSocket pour les candidats
    - Coordination des callbacks
    """

    def __init__(
        self,
        data_manager: UnifiedDataManager,
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
        self._scan_running = False
        self._candidate_running = False

        # Tâches asynchrones
        self._scan_task: Optional[asyncio.Task] = None
        self._scan_interval = 60  # 1 minute entre chaque scan complet
        self._last_scan_time = 0

        # Gestionnaires WebSocket pour candidats
        self.candidate_ws_client = None
        self._candidate_ws_thread: Optional[threading.Thread] = None

        # Gestionnaires
        self.watchlist_manager: Optional[WatchlistManager] = None
        self.volatility_tracker: Optional[VolatilityTracker] = None
        self.ws_manager = None  # Référence au WebSocket principal

        # Callbacks
        self._on_new_opportunity_callback: Optional[Callable] = None
        self._on_candidate_ticker_callback: Optional[Callable] = None

        # Candidats
        self.candidate_symbols: List[str] = []

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

        self._running = True

        # Démarrer le scan périodique du marché
        await self._start_market_scanning(base_url, perp_data)

        # Configurer la surveillance des candidats
        self._setup_candidate_monitoring(base_url, perp_data)

    async def stop_continuous_monitoring(self):
        """Arrête la surveillance continue."""
        if not self._running:
            return

        self._running = False

        # Nettoyer les callbacks pour éviter les fuites mémoire
        self._on_new_opportunity_callback = None
        self._on_candidate_ticker_callback = None

        # Arrêter le scan du marché
        await self._stop_market_scanning()

        # Arrêter la surveillance des candidats
        self._stop_candidate_monitoring()

    async def _start_market_scanning(self, base_url: str, perp_data: Dict):
        """Démarre le scan périodique du marché."""
        if self._scan_task and not self._scan_task.done():
            self.logger.warning("⚠️ Scan du marché déjà actif")
            return

        self._scan_running = True
        self._scan_task = asyncio.create_task(
            self._scanning_loop(base_url, perp_data)
        )
        self.logger.info("🔍 Surveillance continue démarrée")

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
                    await asyncio.wait_for(self._scan_task, timeout=3.0)
                except asyncio.TimeoutError:
                    self.logger.warning(
                        "⚠️ Tâche scan n'a pas pu être annulée dans les temps"
                    )
                except asyncio.CancelledError:
                    pass  # Annulation normale
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur annulation tâche scan: {e}")

        self._scan_task = None
        self.logger.info("🔍 Surveillance continue arrêtée")

    async def _scanning_loop(self, base_url: str, perp_data: Dict):
        """Boucle de surveillance périodique asynchrone."""
        while self._scan_running:
            try:
                # Vérification immédiate pour arrêt rapide
                if not self._scan_running:
                    self.logger.info(
                        "🛑 Arrêt de la surveillance continue demandé"
                    )
                    break

                current_time = time.time()

                # Effectuer un scan si l'intervalle est écoulé
                if self._should_perform_scan(current_time):
                    await self._perform_market_scan(base_url, perp_data)
                    self._last_scan_time = current_time

                    # Vérifier après le scan pour arrêt rapide
                    if not self._scan_running:
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
        """Attend avec vérification d'interruption."""
        for _ in range(seconds):
            if not self._scan_running:
                break
            await asyncio.sleep(1)

    async def _perform_market_scan(self, base_url: str, perp_data: Dict):
        """Effectue un scan complet du marché pour détecter de nouvelles
        opportunités."""
        if not self._scan_running:
            return

        try:
            # Si le WebSocket est déjà actif, éviter le scan complet coûteux
            if (
                self.ws_manager
                and hasattr(self.ws_manager, "running")
                and self.ws_manager.running
            ):
                self.logger.info("🔄 Scan évité - WebSocket déjà actif")
                return

            # Scanner les opportunités
            new_opportunities = self._scan_for_opportunities(
                base_url, perp_data
            )

            # Vérification après le scan qui peut être long
            if not self._scan_running:
                return

            # Intégrer les opportunités si trouvées
            if new_opportunities and self._scan_running:
                self._integrate_opportunities(new_opportunities)

        except Exception as e:
            # Ne pas logger si on est en train de s'arrêter
            if self._scan_running:
                self.logger.warning(f"⚠️ Erreur lors du re-scan: {e}")

    def _scan_for_opportunities(
        self, base_url: str, perp_data: Dict
    ) -> Optional[Dict]:
        """
        Scanne le marché pour trouver de nouvelles opportunités.

        Args:
            base_url: URL de base de l'API
            perp_data: Données des perpétuels

        Returns:
            Dict avec les opportunités trouvées ou None
        """
        try:
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

    def _integrate_opportunities(self, opportunities: Dict):
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
        """Met à jour les données de funding avec les nouvelles opportunités (utilise Value Objects)."""
        # Mettre à jour chaque symbole dans le data manager
        for symbol, data in new_funding_data.items():
            try:
                # Créer un FundingData Value Object
                if isinstance(data, (list, tuple)) and len(data) >= 4:
                    funding, volume, funding_time, spread = data[:4]
                    volatility = data[4] if len(data) > 4 else None
                    
                    funding_obj = FundingData(
                        symbol=symbol,
                        funding_rate=funding,
                        volume_24h=volume,
                        next_funding_time=funding_time,
                        spread_pct=spread,
                        volatility_pct=volatility
                    )
                    
                elif isinstance(data, dict):
                    # Si c'est un dictionnaire, extraire les valeurs
                    funding = data.get("funding", 0.0)
                    volume = data.get("volume", 0.0)
                    funding_time = data.get("funding_time_remaining", "-")
                    spread = data.get("spread_pct", 0.0)
                    volatility = data.get("volatility_pct", None)
                    
                    funding_obj = FundingData(
                        symbol=symbol,
                        funding_rate=funding,
                        volume_24h=volume,
                        next_funding_time=funding_time,
                        spread_pct=spread,
                        volatility_pct=volatility
                    )
                else:
                    continue
                
                # Stocker le Value Object
                self.data_manager.set_funding_data_object(funding_obj)
                
            except (ValueError, TypeError) as e:
                self.logger.warning(f"⚠️ Erreur création FundingData pour {symbol}: {e}")

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

    def _setup_candidate_monitoring(self, base_url: str, perp_data: Dict):
        """
        Configure la surveillance des symboles candidats.

        Args:
            base_url: URL de base de l'API Bybit
            perp_data: Données des perpétuels
        """
        # Détecter les candidats
        linear_candidates, inverse_candidates = self._detect_candidates(
            base_url, perp_data
        )

        # Stocker les candidats
        self.candidate_symbols = linear_candidates + inverse_candidates

        # Démarrer la surveillance WebSocket si des candidats existent
        if linear_candidates or inverse_candidates:
            self._start_candidate_monitoring(
                linear_candidates, inverse_candidates
            )

    def _detect_candidates(
        self, base_url: str, perp_data: Dict
    ) -> tuple[List[str], List[str]]:
        """
        Détecte les symboles candidats et les sépare par catégorie.

        Args:
            base_url: URL de base de l'API
            perp_data: Données des perpétuels

        Returns:
            Tuple (linear_candidates, inverse_candidates)
        """
        try:
            if not self.watchlist_manager:
                return [], []

            # Détecter les candidats
            candidate_symbols = self.watchlist_manager.find_candidate_symbols(
                base_url, perp_data
            )

            if not candidate_symbols:
                return [], []

            # Séparer les candidats par catégorie
            linear_candidates = []
            inverse_candidates = []

            symbol_categories = self.data_manager.symbol_categories

            for symbol in candidate_symbols:
                category = category_of_symbol(symbol, symbol_categories)
                if category == "linear":
                    linear_candidates.append(symbol)
                elif category == "inverse":
                    inverse_candidates.append(symbol)

            return linear_candidates, inverse_candidates

        except Exception as e:
            self.logger.warning(
                f"⚠️ Erreur configuration surveillance candidats: {e}"
            )
            return [], []

    def _start_candidate_monitoring(
        self, linear_candidates: List[str], inverse_candidates: List[str]
    ):
        """
        Démarre la surveillance WebSocket des candidats.

        Args:
            linear_candidates: Liste des candidats linear
            inverse_candidates: Liste des candidats inverse
        """
        try:
            # Déterminer les symboles à surveiller
            if linear_candidates and inverse_candidates:
                # Si on a les deux catégories, utiliser linear (plus courant)
                symbols_to_monitor = linear_candidates + inverse_candidates
                category = "linear"
            elif linear_candidates:
                symbols_to_monitor = linear_candidates
                category = "linear"
            elif inverse_candidates:
                symbols_to_monitor = inverse_candidates
                category = "inverse"
            else:
                return

            # Créer la connexion WebSocket
            from ws_public import PublicWSClient

            self.candidate_ws_client = PublicWSClient(
                category=category,
                symbols=symbols_to_monitor,
                testnet=self.testnet,
                logger=self.logger,
                on_ticker_callback=self._on_candidate_ticker,
            )

            # Lancer la surveillance dans un thread séparé
            self._candidate_ws_thread = threading.Thread(
                target=self._candidate_ws_runner
            )
            self._candidate_ws_thread.daemon = True
            self._candidate_ws_thread.start()

            self._candidate_running = True

        except Exception as e:
            self.logger.error(
                f"❌ Erreur démarrage surveillance candidats: {e}"
            )

    def _stop_candidate_monitoring(self):
        """Arrête la surveillance des candidats."""
        if not self._candidate_running:
            return

        self._candidate_running = False

        if self.candidate_ws_client:
            try:
                self.candidate_ws_client.close()
            except Exception as e:
                self.logger.warning(
                    f"⚠️ Erreur fermeture WebSocket candidats: {e}"
                )

        # Attendre la fin du thread avec timeout amélioré
        if self._candidate_ws_thread and self._candidate_ws_thread.is_alive():
            try:
                self._candidate_ws_thread.join(
                    timeout=10
                )  # Augmenté de 3s à 10s
                if self._candidate_ws_thread.is_alive():
                    self.logger.warning(
                        "⚠️ Thread candidats n'a pas pu être arrêté dans les temps"
                    )
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur attente thread candidats: {e}")

    def _candidate_ws_runner(self):
        """Runner pour la WebSocket des candidats."""
        if self.candidate_ws_client:
            try:
                self.candidate_ws_client.run()
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur WebSocket candidats: {e}")

    def _on_candidate_ticker(self, ticker_data: dict):
        """Callback appelé pour chaque ticker des candidats."""
        try:
            symbol = ticker_data.get("symbol", "")
            if not symbol:
                return

            # Vérifier si le candidat passe maintenant les filtres
            if (
                self.watchlist_manager
                and self.watchlist_manager.check_if_symbol_now_passes_filters(
                    symbol, ticker_data
                )
            ):
                # 🎯 NOUVELLE OPPORTUNITÉ DÉTECTÉE !
                self.logger.info(f"🎯 Nouvelle opportunité détectée: {symbol}")

                # Appeler le callback externe si défini
                if self._on_candidate_ticker_callback:
                    try:
                        self._on_candidate_ticker_callback(symbol, ticker_data)
                    except Exception as e:
                        self.logger.warning(
                            f"⚠️ Erreur callback candidat: {e}"
                        )

        except Exception as e:
            self.logger.warning(f"⚠️ Erreur traitement candidat {symbol}: {e}")

    def setup_candidate_monitoring(self, base_url: str, perp_data: Dict):
        """
        Configure la surveillance des symboles candidats.

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
        return self._running and (
            self._scan_running or self._candidate_running
        )
