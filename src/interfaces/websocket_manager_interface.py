#!/usr/bin/env python3
"""
Interface pour WebSocketManager - Contrat pour les gestionnaires WebSocket.

Cette interface définit le contrat que doivent respecter tous les gestionnaires
WebSocket, permettant une meilleure testabilité et une architecture flexible.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Callable, Dict, Any


class WebSocketManagerInterface(ABC):
    """
    Interface pour les gestionnaires WebSocket.

    Cette interface définit les méthodes que doit implémenter tout gestionnaire
    WebSocket, permettant de facilement créer des mocks pour les tests.
    """

    @abstractmethod
    async def start_connections(
        self,
        linear_symbols: List[str],
        inverse_symbols: List[str],
        on_ticker_callback: Optional[Callable] = None,
        on_orderbook_callback: Optional[Callable] = None
    ) -> None:
        """
        Démarre les connexions WebSocket.

        Args:
            linear_symbols: Liste des symboles linear à suivre
            inverse_symbols: Liste des symboles inverse à suivre
            on_ticker_callback: Callback appelé lors de la réception de tickers
            on_orderbook_callback: Callback appelé lors de la réception d'orderbook

        Raises:
            Exception: En cas d'erreur de connexion
        """
        pass

    @abstractmethod
    async def stop_connections(self) -> None:
        """
        Arrête toutes les connexions WebSocket.

        Raises:
            Exception: En cas d'erreur d'arrêt
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """
        Vérifie si au moins une connexion WebSocket est active.

        Returns:
            bool: True si connecté, False sinon
        """
        pass

    @abstractmethod
    def get_connection_status(self) -> Dict[str, bool]:
        """
        Retourne le statut de toutes les connexions.

        Returns:
            Dict: Statut de chaque connexion {nom: bool}
        """
        pass

    @abstractmethod
    def get_connected_symbols(self) -> Dict[str, List[str]]:
        """
        Retourne la liste des symboles connectés par catégorie.

        Returns:
            Dict: Symboles connectés {"linear": [...], "inverse": [...]}
        """
        pass

    @abstractmethod
    def add_symbols(
        self,
        category: str,
        symbols: List[str]
    ) -> None:
        """
        Ajoute des symboles à une connexion existante.

        Args:
            category: Catégorie des symboles ("linear" ou "inverse")
            symbols: Liste des symboles à ajouter

        Raises:
            Exception: En cas d'erreur d'ajout
        """
        pass

    @abstractmethod
    def remove_symbols(
        self,
        category: str,
        symbols: List[str]
    ) -> None:
        """
        Retire des symboles d'une connexion existante.

        Args:
            category: Catégorie des symboles ("linear" ou "inverse")
            symbols: Liste des symboles à retirer

        Raises:
            Exception: En cas d'erreur de suppression
        """
        pass

    @abstractmethod
    def set_ticker_callback(self, callback: Callable) -> None:
        """
        Définit le callback pour les tickers.

        Args:
            callback: Fonction à appeler lors de la réception de tickers
        """
        pass

    @abstractmethod
    def set_orderbook_callback(self, callback: Callable) -> None:
        """
        Définit le callback pour les orderbooks.

        Args:
            callback: Fonction à appeler lors de la réception d'orderbooks
        """
        pass

    @abstractmethod
    def get_reconnect_delays(self) -> List[int]:
        """
        Retourne la liste des délais de reconnexion.

        Returns:
            List[int]: Délais de reconnexion en secondes
        """
        pass

    @abstractmethod
    def set_reconnect_delays(self, delays: List[int]) -> None:
        """
        Définit les délais de reconnexion.

        Args:
            delays: Liste des délais en secondes
        """
        pass

    @abstractmethod
    def get_reconnect_count(self) -> int:
        """
        Retourne le nombre de reconnexions effectuées.

        Returns:
            int: Nombre de reconnexions
        """
        pass

    @abstractmethod
    def reset_reconnect_count(self) -> None:
        """
        Remet à zéro le compteur de reconnexions.
        """
        pass

    @abstractmethod
    def get_last_error(self) -> Optional[Exception]:
        """
        Retourne la dernière erreur rencontrée.

        Returns:
            Optional[Exception]: Dernière erreur ou None
        """
        pass

    @abstractmethod
    def clear_last_error(self) -> None:
        """
        Efface la dernière erreur.
        """
        pass

    @abstractmethod
    def get_connection_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques de connexion.

        Returns:
            Dict: Statistiques détaillées des connexions
        """
        pass

    @abstractmethod
    def is_testnet(self) -> bool:
        """
        Indique si le gestionnaire utilise le testnet.

        Returns:
            bool: True si testnet, False si mainnet
        """
        pass

    @abstractmethod
    def get_data_manager(self):
        """
        Retourne le gestionnaire de données associé.

        Returns:
            DataManager: Gestionnaire de données
        """
        pass

    @abstractmethod
    def set_data_manager(self, data_manager) -> None:
        """
        Définit le gestionnaire de données.

        Args:
            data_manager: Gestionnaire de données à associer
        """
        pass

    @abstractmethod
    def start_watchdog(self) -> None:
        """
        Démarre le thread watchdog pour surveiller les connexions.
        """
        pass

    @abstractmethod
    def stop_watchdog(self) -> None:
        """
        Arrête le thread watchdog.
        """
        pass

    @abstractmethod
    def is_watchdog_running(self) -> bool:
        """
        Vérifie si le watchdog est en cours d'exécution.

        Returns:
            bool: True si le watchdog est actif, False sinon
        """
        pass

    @abstractmethod
    async def switch_to_single_symbol(self, symbol: str, category: str = "linear") -> None:
        """
        Bascule vers un symbole unique dans le WebSocket.

        Args:
            symbol: Symbole à surveiller
            category: Catégorie du symbole ("linear" ou "inverse")

        Raises:
            Exception: En cas d'erreur lors du basculement
        """
        pass

    @abstractmethod
    async def restore_full_watchlist(
        self,
        linear_symbols: List[str],
        inverse_symbols: List[str]
    ) -> None:
        """
        Restaure la watchlist complète dans le WebSocket.

        Args:
            linear_symbols: Liste des symboles linear à surveiller
            inverse_symbols: Liste des symboles inverse à surveiller

        Raises:
            Exception: En cas d'erreur lors de la restauration
        """
        pass
