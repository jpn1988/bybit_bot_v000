#!/usr/bin/env python3
"""
Moniteur de candidats pour le bot Bybit.

Ce module contient les classes responsables de la surveillance des symboles candidats :
- CandidateSymbolDetector : Détection des symboles candidats
- CandidateWebSocketManager : Gestion WebSocket des candidats
- CandidateOpportunityDetector : Détection d'opportunités pour les candidats
- CandidateMonitor : Orchestrateur de surveillance des candidats
"""

import threading
from typing import List, Dict, Optional, Callable
from data_manager import DataManager
from watchlist_manager import WatchlistManager
from instruments import category_of_symbol


class CandidateSymbolDetector:
    """
    Détecteur de symboles candidats.

    Responsabilités :
    - Détection des symboles candidats via le watchlist manager
    - Séparation des candidats par catégorie (linear/inverse)
    - Gestion des catégories de symboles
    """

    def __init__(self, data_manager: DataManager, logger):
        """Initialise le détecteur de candidats."""
        self.data_manager = data_manager
        self.logger = logger
        self.watchlist_manager: Optional[WatchlistManager] = None

    def set_watchlist_manager(self, watchlist_manager: WatchlistManager):
        """Définit le gestionnaire de watchlist."""
        self.watchlist_manager = watchlist_manager

    def detect_candidates(
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


class CandidateWebSocketManager:
    """
    Gestionnaire WebSocket pour les candidats.

    Responsabilités :
    - Gestion des connexions WebSocket pour les candidats
    - Surveillance des tickers en temps réel
    - Gestion des threads WebSocket
    """

    def __init__(self, testnet: bool, logger):
        """Initialise le gestionnaire WebSocket des candidats."""
        self.testnet = testnet
        self.logger = logger
        self.candidate_ws_client = None
        self._candidate_ws_thread: Optional[threading.Thread] = None
        self._on_candidate_ticker_callback: Optional[Callable] = None

    def set_on_candidate_ticker_callback(self, callback: Callable):
        """Définit le callback pour les tickers des candidats."""
        self._on_candidate_ticker_callback = callback

    def start_monitoring(
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

        except Exception as e:
            self.logger.error(
                f"❌ Erreur démarrage surveillance candidats: {e}"
            )

    def stop_monitoring(self):
        """Arrête la surveillance des candidats."""
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

            # Appeler le callback externe si défini
            if self._on_candidate_ticker_callback:
                try:
                    self._on_candidate_ticker_callback(symbol, ticker_data)
                except Exception as e:
                    self.logger.warning(f"⚠️ Erreur callback candidat: {e}")

        except Exception as e:
            self.logger.warning(f"⚠️ Erreur traitement candidat {symbol}: {e}")


class CandidateOpportunityDetector:
    """
    Détecteur d'opportunités pour les candidats.

    Responsabilités :
    - Vérification si un candidat passe les filtres
    - Détection des nouvelles opportunités en temps réel
    - Notification des opportunités détectées
    """

    def __init__(self, logger):
        """Initialise le détecteur d'opportunités."""
        self.logger = logger
        self.watchlist_manager: Optional[WatchlistManager] = None
        self._on_candidate_ticker_callback: Optional[Callable] = None

    def set_watchlist_manager(self, watchlist_manager: WatchlistManager):
        """Définit le gestionnaire de watchlist."""
        self.watchlist_manager = watchlist_manager

    def set_on_candidate_ticker_callback(self, callback: Callable):
        """Définit le callback pour les tickers des candidats."""
        self._on_candidate_ticker_callback = callback

    def process_candidate_ticker(self, symbol: str, ticker_data: dict):
        """
        Traite un ticker de candidat pour détecter les opportunités.

        Args:
            symbol: Symbole du candidat
            ticker_data: Données du ticker
        """
        try:
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


class CandidateMonitor:
    """
    Moniteur de symboles candidats pour détecter les nouvelles opportunités
    en temps réel.

    Cette classe orchestre les composants spécialisés :
    - CandidateSymbolDetector : Détection des candidats
    - CandidateWebSocketManager : Gestion WebSocket
    - CandidateOpportunityDetector : Détection d'opportunités
    """

    def __init__(self, data_manager: DataManager, testnet: bool, logger):
        """
        Initialise le moniteur de candidats.

        Args:
            data_manager: Gestionnaire de données
            testnet: Utiliser le testnet
            logger: Logger pour les messages
        """
        self.data_manager = data_manager
        self.testnet = testnet
        self.logger = logger

        # Composants spécialisés
        self._detector = CandidateSymbolDetector(data_manager, logger)
        self._ws_manager = CandidateWebSocketManager(testnet, logger)
        self._opportunity_detector = CandidateOpportunityDetector(logger)

        # État
        self.candidate_symbols: List[str] = []

    def set_watchlist_manager(self, watchlist_manager: WatchlistManager):
        """Définit le gestionnaire de watchlist."""
        self._detector.set_watchlist_manager(watchlist_manager)
        self._opportunity_detector.set_watchlist_manager(watchlist_manager)

    def set_on_candidate_ticker_callback(self, callback: Callable):
        """Définit le callback pour les tickers des candidats."""
        self._ws_manager.set_on_candidate_ticker_callback(
            self._on_candidate_ticker
        )
        self._opportunity_detector.set_on_candidate_ticker_callback(callback)

    def setup_candidate_monitoring(self, base_url: str, perp_data: Dict):
        """
        Configure la surveillance des symboles candidats.

        Args:
            base_url: URL de base de l'API Bybit
            perp_data: Données des perpétuels
        """
        # Détecter les candidats
        (
            linear_candidates,
            inverse_candidates,
        ) = self._detector.detect_candidates(base_url, perp_data)

        # Stocker les candidats
        self.candidate_symbols = linear_candidates + inverse_candidates

        # Démarrer la surveillance WebSocket si des candidats existent
        if linear_candidates or inverse_candidates:
            self._ws_manager.start_monitoring(
                linear_candidates, inverse_candidates
            )

    def stop_candidate_monitoring(self):
        """Arrête la surveillance des candidats."""
        self._ws_manager.stop_monitoring()

    def _on_candidate_ticker(self, symbol: str, ticker_data: dict):
        """Callback interne pour traiter les tickers des candidats."""
        self._opportunity_detector.process_candidate_ticker(
            symbol, ticker_data
        )
