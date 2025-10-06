#!/usr/bin/env python3
"""
Gestionnaire de données pour le bot Bybit.

Cette classe gère uniquement :
- Le stockage des données de funding et temps réel
- La synchronisation thread-safe des données
- Les opérations CRUD sur les données
"""

import time
import threading
from typing import Dict, List, Optional, Tuple, Any
from logging_setup import setup_logging


class DataManager:
    """
    Gestionnaire de données pour le bot Bybit.

    Responsabilités :
    - Stockage thread-safe des données de funding et temps réel
    - Gestion des verrous pour la synchronisation
    - Opérations CRUD sur les données
    - Gestion des catégories de symboles
    """

    def __init__(self, logger=None):
        """
        Initialise le gestionnaire de données.

        Args:
            logger: Logger pour les messages (optionnel)
        """
        self.logger = logger or setup_logging()

        # Données de funding (format: {symbol: (funding, volume, funding_time,
        # spread, volatility)})
        self.funding_data: Dict[
            str, Tuple[float, float, str, float, Optional[float]]
        ] = {}

        # Données de funding originales avec next_funding_time
        self.original_funding_data: Dict[str, str] = {}

        # Données en temps réel via WebSocket
        # Format: {symbol: {funding_rate, volume24h, bid1, ask1,
        # next_funding_time, ...}}
        self.realtime_data: Dict[str, Dict[str, Any]] = {}

        # Verrous pour la synchronisation thread-safe
        self._funding_lock = threading.Lock()
        self._realtime_lock = threading.Lock()

        # Catégories des symboles
        self.symbol_categories: Dict[str, str] = {}

        # Listes de symboles par catégorie
        self.linear_symbols: List[str] = []
        self.inverse_symbols: List[str] = []

    def set_symbol_categories(self, symbol_categories: Dict[str, str]):
        """
        Définit le mapping des catégories de symboles.

        Args:
            symbol_categories: Dictionnaire {symbol: category}
        """
        self.symbol_categories = symbol_categories

    def update_funding_data(
        self,
        symbol: str,
        funding: float,
        volume: float,
        funding_time: str,
        spread: float,
        volatility: Optional[float] = None,
    ):
        """
        Met à jour les données de funding pour un symbole.

        Args:
            symbol: Symbole à mettre à jour
            funding: Taux de funding
            volume: Volume 24h
            funding_time: Temps restant avant funding
            spread: Spread en pourcentage
            volatility: Volatilité (optionnel)
        """
        with self._funding_lock:
            self.funding_data[symbol] = (
                funding,
                volume,
                funding_time,
                spread,
                volatility,
            )

    def get_funding_data(
        self, symbol: str
    ) -> Optional[Tuple[float, float, str, float, Optional[float]]]:
        """
        Récupère les données de funding pour un symbole.

        Args:
            symbol: Symbole à récupérer

        Returns:
            Tuple des données de funding ou None si absent
        """
        with self._funding_lock:
            return self.funding_data.get(symbol)

    def get_all_funding_data(
        self,
    ) -> Dict[str, Tuple[float, float, str, float, Optional[float]]]:
        """
        Récupère toutes les données de funding.

        Returns:
            Dictionnaire des données de funding
        """
        with self._funding_lock:
            return self.funding_data.copy()

    def update_realtime_data(self, symbol: str, ticker_data: Dict[str, Any]):
        """
        Met à jour les données en temps réel pour un symbole.

        Args:
            symbol: Symbole à mettre à jour
            ticker_data: Données du ticker reçues via WebSocket
        """
        if not symbol:
            return

        try:
            # Construire un diff et fusionner avec l'état précédent
            now_ts = time.time()
            incoming = {
                "funding_rate": ticker_data.get("fundingRate"),
                "volume24h": ticker_data.get("volume24h"),
                "bid1_price": ticker_data.get("bid1Price"),
                "ask1_price": ticker_data.get("ask1Price"),
                "next_funding_time": ticker_data.get("nextFundingTime"),
                "mark_price": ticker_data.get("markPrice"),
                "last_price": ticker_data.get("lastPrice"),
            }

            # Vérifier si des données importantes sont présentes
            important_keys = [
                "funding_rate",
                "volume24h",
                "bid1_price",
                "ask1_price",
                "next_funding_time",
            ]

            if any(incoming[key] is not None for key in important_keys):
                with self._realtime_lock:
                    current = self.realtime_data.get(symbol, {})
                    merged = dict(current) if current else {}
                    for k, v in incoming.items():
                        if v is not None:
                            merged[k] = v
                    merged["timestamp"] = now_ts
                    self.realtime_data[symbol] = merged

        except Exception as e:
            self.logger.warning(
                f"⚠️ Erreur mise à jour données temps réel pour {symbol}: {e}"
            )

    def get_realtime_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les données en temps réel pour un symbole.

        Args:
            symbol: Symbole à récupérer

        Returns:
            Dictionnaire des données temps réel ou None si absent
        """
        with self._realtime_lock:
            return self.realtime_data.get(symbol)

    def get_all_realtime_data(self) -> Dict[str, Dict[str, Any]]:
        """
        Récupère toutes les données en temps réel.

        Returns:
            Dictionnaire des données temps réel
        """
        with self._realtime_lock:
            return self.realtime_data.copy()

    def update_original_funding_data(
        self, symbol: str, next_funding_time: str
    ):
        """
        Met à jour les données de funding originales.

        Args:
            symbol: Symbole à mettre à jour
            next_funding_time: Timestamp du prochain funding
        """
        with self._funding_lock:
            self.original_funding_data[symbol] = next_funding_time

    def get_original_funding_data(self, symbol: str) -> Optional[str]:
        """
        Récupère les données de funding originales pour un symbole.

        Args:
            symbol: Symbole à récupérer

        Returns:
            Timestamp du prochain funding ou None si absent
        """
        with self._funding_lock:
            return self.original_funding_data.get(symbol)

    def get_all_original_funding_data(self) -> Dict[str, str]:
        """
        Récupère toutes les données de funding originales.

        Returns:
            Dictionnaire des données de funding originales
        """
        with self._funding_lock:
            return self.original_funding_data.copy()

    def set_symbol_lists(
        self, linear_symbols: List[str], inverse_symbols: List[str]
    ):
        """
        Définit les listes de symboles par catégorie.

        Args:
            linear_symbols: Liste des symboles linear
            inverse_symbols: Liste des symboles inverse
        """
        self.linear_symbols = linear_symbols.copy()
        self.inverse_symbols = inverse_symbols.copy()

    def get_linear_symbols(self) -> List[str]:
        """
        Récupère la liste des symboles linear.

        Returns:
            Liste des symboles linear
        """
        return self.linear_symbols.copy()

    def get_inverse_symbols(self) -> List[str]:
        """
        Récupère la liste des symboles inverse.

        Returns:
            Liste des symboles inverse
        """
        return self.inverse_symbols.copy()

    def get_all_symbols(self) -> List[str]:
        """
        Récupère tous les symboles (linear + inverse).

        Returns:
            Liste de tous les symboles
        """
        return self.linear_symbols + self.inverse_symbols

    def add_symbol_to_category(self, symbol: str, category: str):
        """
        Ajoute un symbole à une catégorie.

        Args:
            symbol: Symbole à ajouter
            category: Catégorie ("linear" ou "inverse")
        """
        if category == "linear" and symbol not in self.linear_symbols:
            self.linear_symbols.append(symbol)
        elif category == "inverse" and symbol not in self.inverse_symbols:
            self.inverse_symbols.append(symbol)

    def remove_symbol_from_category(self, symbol: str, category: str):
        """
        Retire un symbole d'une catégorie.

        Args:
            symbol: Symbole à retirer
            category: Catégorie ("linear" ou "inverse")
        """
        if category == "linear" and symbol in self.linear_symbols:
            self.linear_symbols.remove(symbol)
        elif category == "inverse" and symbol in self.inverse_symbols:
            self.inverse_symbols.remove(symbol)

    def clear_all_data(self):
        """
        Vide toutes les données stockées.
        """
        with self._funding_lock:
            self.funding_data.clear()
            self.original_funding_data.clear()

        with self._realtime_lock:
            self.realtime_data.clear()

        self.linear_symbols.clear()
        self.inverse_symbols.clear()

    def get_data_stats(self) -> Dict[str, int]:
        """
        Retourne les statistiques des données stockées.

        Returns:
            Dictionnaire avec les statistiques
        """
        with self._funding_lock:
            funding_count = len(self.funding_data)
            original_count = len(self.original_funding_data)

        with self._realtime_lock:
            realtime_count = len(self.realtime_data)

        return {
            "funding_data": funding_count,
            "original_funding_data": original_count,
            "realtime_data": realtime_count,
            "linear_symbols": len(self.linear_symbols),
            "inverse_symbols": len(self.inverse_symbols),
        }
