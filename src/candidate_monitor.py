#!/usr/bin/env python3
"""
Moniteur de candidats pour le bot Bybit.

Cette classe est responsable de la surveillance en temps réel
des symboles candidats via WebSocket.
"""

import threading
from typing import List, Dict, Optional, Callable
from logging_setup import setup_logging
from data_manager import DataManager
from watchlist_manager import WatchlistManager
from instruments import category_of_symbol
from config.timeouts import TimeoutConfig


class CandidateMonitor:
    """
    Moniteur de symboles candidats via WebSocket.
    
    Responsabilité unique : Surveiller en temps réel les candidats
    qui sont proches de passer les filtres.
    """

    def __init__(
        self,
        data_manager: DataManager,
        watchlist_manager: WatchlistManager,
        testnet: bool = True,
        logger=None,
    ):
        """
        Initialise le moniteur de candidats.

        Args:
            data_manager: Gestionnaire de données
            watchlist_manager: Gestionnaire de watchlist
            testnet: Utiliser le testnet (True) ou le marché réel (False)
            logger: Logger pour les messages (optionnel)
        """
        self.data_manager = data_manager
        self.watchlist_manager = watchlist_manager
        self.testnet = testnet
        self.logger = logger or setup_logging()
        
        # État de surveillance
        self._candidate_running = False
        
        # Gestionnaires WebSocket pour candidats
        self.candidate_ws_client = None
        self._candidate_ws_thread: Optional[threading.Thread] = None
        
        # Liste des symboles candidats surveillés
        self.candidate_symbols: List[str] = []
        
        # Callback pour les tickers candidats
        self._on_candidate_ticker_callback: Optional[Callable] = None

    def set_on_candidate_ticker_callback(self, callback: Callable):
        """
        Définit le callback pour les tickers des candidats.

        Args:
            callback: Fonction à appeler pour chaque ticker candidat
        """
        self._on_candidate_ticker_callback = callback

    def setup_monitoring(self, base_url: str, perp_data: Dict):
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
            self._start_monitoring(linear_candidates, inverse_candidates)

    def stop_monitoring(self):
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

        # Attendre la fin du thread avec timeout
        if self._candidate_ws_thread and self._candidate_ws_thread.is_alive():
            try:
                self._candidate_ws_thread.join(timeout=TimeoutConfig.THREAD_CANDIDATE_SHUTDOWN)
                if self._candidate_ws_thread.is_alive():
                    self.logger.warning(
                        "⚠️ Thread candidats n'a pas pu être arrêté dans les temps"
                    )
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur attente thread candidats: {e}")

        # Nettoyer le callback pour éviter les fuites mémoire
        self._on_candidate_ticker_callback = None

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
            # Détecter les candidats
            candidate_symbols = self.watchlist_manager.find_candidate_symbols(
                base_url, perp_data
            )

            if not candidate_symbols:
                return [], []

            # Séparer les candidats par catégorie
            linear_candidates = []
            inverse_candidates = []

            symbol_categories = self.data_manager.storage.symbol_categories

            for symbol in candidate_symbols:
                category = category_of_symbol(symbol, symbol_categories)
                if category == "linear":
                    linear_candidates.append(symbol)
                elif category == "inverse":
                    inverse_candidates.append(symbol)

            return linear_candidates, inverse_candidates

        except Exception as e:
            self.logger.warning(
                f"⚠️ Erreur détection candidats: {e}"
            )
            return [], []

    def _start_monitoring(
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
                on_ticker_callback=self._on_ticker_received,
            )

            # Lancer la surveillance dans un thread séparé
            self._candidate_ws_thread = threading.Thread(
                target=self._ws_runner
            )
            self._candidate_ws_thread.daemon = True
            self._candidate_ws_thread.start()

            self._candidate_running = True
            
            self.logger.info(
                f"👀 Surveillance des candidats démarrée: {len(symbols_to_monitor)} symboles"
            )

        except Exception as e:
            self.logger.error(
                f"❌ Erreur démarrage surveillance candidats: {e}"
            )

    def _ws_runner(self):
        """Runner pour la WebSocket des candidats."""
        if self.candidate_ws_client:
            try:
                self.candidate_ws_client.run()
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur WebSocket candidats: {e}")

    def _on_ticker_received(self, ticker_data: dict):
        """
        Callback appelé pour chaque ticker des candidats.
        
        Args:
            ticker_data: Données du ticker
        """
        try:
            symbol = ticker_data.get("symbol", "")
            if not symbol:
                return

            # Vérifier si le candidat passe maintenant les filtres
            if self.watchlist_manager.check_if_symbol_now_passes_filters(
                symbol, ticker_data
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
            symbol = ticker_data.get("symbol", "inconnu")
            self.logger.warning(f"⚠️ Erreur traitement candidat {symbol}: {e}")

    def is_running(self) -> bool:
        """
        Vérifie si le moniteur est en cours d'exécution.

        Returns:
            True si en cours d'exécution
        """
        return self._candidate_running

    def get_candidate_symbols(self) -> List[str]:
        """
        Retourne la liste des symboles candidats surveillés.

        Returns:
            Liste des symboles candidats
        """
        return self.candidate_symbols.copy()

