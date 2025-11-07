#!/usr/bin/env python3
"""
Gestionnaires de callbacks et métriques WebSocket.

Ce module centralise la gestion des callbacks WebSocket et des métriques
pour éviter la duplication de code et améliorer la maintenabilité.
"""

import time
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from typing import Callable, Optional, Dict, Any, List, TYPE_CHECKING
from dataclasses import dataclass
from logging_setup import setup_logging
from interfaces.data_manager_interface import DataManagerInterface

if TYPE_CHECKING:
    from typing_imports import DataManager


@dataclass
class WebSocketMetrics:
    """Métriques WebSocket."""
    total_connections: int = 0
    connected_count: int = 0
    total_reconnects: int = 0
    last_error: Optional[Exception] = None
    last_activity: float = 0.0


class WebSocketHandlers:
    """
    Gestionnaire de callbacks et métriques WebSocket.

    Responsabilités :
    - Gérer les callbacks de données
    - Tracker les métriques de connexion
    - Router les données vers les gestionnaires appropriés
    - Gérer les erreurs et exceptions
    """

    def __init__(self, logger=None):
        """
        Initialise les gestionnaires.

        Args:
            logger: Logger pour les messages
        """
        self.logger = logger or setup_logging()

        # Callbacks
        self._ticker_callback: Optional[Callable] = None
        self._orderbook_callback: Optional[Callable] = None
        self._error_callback: Optional[Callable] = None

        # Métriques
        self._metrics = WebSocketMetrics()

        # Data manager pour stockage
        self._data_manager = None

    def set_ticker_callback(self, callback: Callable[[dict], None]):
        """
        Définit le callback pour les données ticker.

        Args:
            callback: Fonction à appeler avec les données ticker
        """
        self._ticker_callback = callback
        self.logger.debug("✅ Callback ticker défini")

    def set_orderbook_callback(self, callback: Callable[[dict], None]):
        """
        Définit le callback pour les données orderbook.

        Args:
            callback: Fonction à appeler avec les données orderbook
        """
        self._orderbook_callback = callback
        self.logger.debug("✅ Callback orderbook défini")

    def set_error_callback(self, callback: Callable[[Exception], None]):
        """
        Définit le callback pour les erreurs.

        Args:
            callback: Fonction à appeler en cas d'erreur
        """
        self._error_callback = callback
        self.logger.debug("✅ Callback erreur défini")

    def set_data_manager(self, data_manager: Optional[DataManagerInterface]):
        """
        Définit le gestionnaire de données.

        Args:
            data_manager: Instance du gestionnaire de données (DataManagerInterface)
        """
        self._data_manager = data_manager
        self.logger.debug("✅ Data manager défini")

    def handle_ticker_data(self, ticker_data: dict):
        """
        Gère les données ticker reçues.

        Args:
            ticker_data: Données ticker du WebSocket
        """
        try:
            symbol = ticker_data.get("symbol", "")
            mark_price = ticker_data.get("markPrice")
            last_price = ticker_data.get("lastPrice")

            # Mettre à jour le store de prix si data_manager disponible
            if symbol and mark_price is not None and last_price is not None and self._data_manager:
                mark_val = float(mark_price)
                last_val = float(last_price)
                # Utiliser la méthode déléguée de DataManagerInterface au lieu d'accéder à .storage
                self._data_manager.update_price_data(symbol, mark_val, last_val, time.time())

            # Appeler le callback externe
            if self._ticker_callback and symbol:
                self._ticker_callback(ticker_data)

            # Mettre à jour les métriques
            self._metrics.last_activity = time.time()

        except Exception as e:
            self.logger.warning(f"⚠️ Erreur traitement ticker: {e}")
            self._handle_error(e)

    def handle_orderbook_data(self, orderbook_data: dict):
        """
        Gère les données orderbook reçues.

        Args:
            orderbook_data: Données orderbook du WebSocket
        """
        try:
            if self._orderbook_callback:
                self._orderbook_callback(orderbook_data)

            # Mettre à jour les métriques
            self._metrics.last_activity = time.time()

        except Exception as e:
            self.logger.warning(f"⚠️ Erreur traitement orderbook: {e}")
            self._handle_error(e)

    def handle_connection_event(self, event_type: str, data: dict):
        """
        Gère les événements de connexion.

        Args:
            event_type: Type d'événement ("connected", "disconnected", "reconnected")
            data: Données de l'événement
        """
        try:
            if event_type == "connected":
                self._metrics.connected_count += 1
                self.logger.info(f"✅ Connexion WebSocket établie: {data.get('category', 'unknown')}")
            elif event_type == "disconnected":
                self._metrics.connected_count = max(0, self._metrics.connected_count - 1)
                self.logger.warning(f"⚠️ Connexion WebSocket fermée: {data.get('category', 'unknown')}")
            elif event_type == "reconnected":
                self._metrics.total_reconnects += 1
                self.logger.info(f"🔄 Reconnexion WebSocket: {data.get('category', 'unknown')}")

            # Mettre à jour les métriques
            self._metrics.last_activity = time.time()

        except Exception as e:
            self.logger.warning(f"⚠️ Erreur traitement événement connexion: {e}")
            self._handle_error(e)

    def _handle_error(self, error: Exception):
        """
        Gère les erreurs internes.

        Args:
            error: Exception à traiter
        """
        self._metrics.last_error = error

        if self._error_callback:
            try:
                self._error_callback(error)
            except Exception as callback_error:
                self.logger.error(f"❌ Erreur callback erreur: {callback_error}")

    def update_connection_count(self, count: int):
        """
        Met à jour le nombre de connexions.

        Args:
            count: Nombre de connexions
        """
        self._metrics.total_connections = count

    def get_metrics(self) -> WebSocketMetrics:
        """
        Retourne les métriques actuelles.

        Returns:
            Métriques WebSocket
        """
        return self._metrics

    def get_connection_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques de connexion.

        Returns:
            Dictionnaire des statistiques
        """
        return {
            "total_connections": self._metrics.total_connections,
            "connected_count": self._metrics.connected_count,
            "total_reconnects": self._metrics.total_reconnects,
            "last_error": str(self._metrics.last_error) if self._metrics.last_error else None,
            "last_activity": self._metrics.last_activity,
            "is_active": self._metrics.last_activity > 0
        }

    def reset_metrics(self):
        """Remet à zéro les métriques."""
        self._metrics = WebSocketMetrics()
        self.logger.debug("🔄 Métriques WebSocket réinitialisées")

    def clear_callbacks(self):
        """Nettoie tous les callbacks."""
        self._ticker_callback = None
        self._orderbook_callback = None
        self._error_callback = None
        self.logger.debug("🧹 Callbacks WebSocket nettoyés")
