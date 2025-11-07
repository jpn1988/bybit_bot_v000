#!/usr/bin/env python3
"""
Formateur de tableaux pour le bot Bybit.

Ce module contient la classe TableFormatter responsable de :
- Formatage des données pour l'affichage
- Calcul des largeurs de colonnes
- Gestion des fallbacks entre temps réel et REST
- Formatage des valeurs (funding, volume, spread, volatilité)
"""

import time
from typing import Dict, Optional, Any, Callable
from datetime import datetime


class TableFormatter:
    """
    Formateur de tableaux pour l'affichage des données Bybit.

    Responsabilités :
    - Formatage des données pour l'affichage
    - Calcul des largeurs de colonnes dynamiques
    - Gestion des fallbacks entre temps réel et REST
    - Formatage des valeurs (funding, volume, spread, volatilité)
    """

    def __init__(self, volatility_callback: Optional[Callable[[str], Optional[float]]] = None):
        """
        Initialise le formateur de tableaux.

        Args:
            volatility_callback: Callback pour récupérer la volatilité
        """
        self._volatility_callback = volatility_callback

    def set_volatility_callback(self, callback: Callable[[str], Optional[float]]) -> None:
        """Définit le callback pour la volatilité."""
        self._volatility_callback = callback

    def calculate_column_widths(self, funding_data: Dict) -> Dict[str, int]:
        """
        Calcule les largeurs des colonnes du tableau.

        Args:
            funding_data: Données de funding

        Returns:
            Dictionnaire des largeurs de colonnes
        """
        all_symbols = list(funding_data.keys())
        if all_symbols:
            max_symbol_len = max(
                len("Symbole"), max(len(s) for s in all_symbols)
            )
        else:
            max_symbol_len = len("Symbole")

        return {
            "symbol": max(8, max_symbol_len),
            "funding": 12,
            "volume": 10,
            "spread": 10,
            "volatility": 12,
            "funding_time": 15,
        }

    def format_table_header(self, col_widths: Dict[str, int]) -> str:
        """
        Formate l'en-tête du tableau.

        Args:
            col_widths: Largeurs des colonnes

        Returns:
            En-tête formaté
        """
        w = col_widths
        header = (
            f"{'Symbole':<{w['symbol']}} | {'Funding %':>{w['funding']}} | "
            f"{'Volume (M)':>{w['volume']}} | {'Spread %':>{w['spread']}} | "
            f"{'Volatilité %':>{w['volatility']}} | "
            f"{'Funding T':>{w['funding_time']}}"
        )
        return header

    def format_table_separator(self, col_widths: Dict[str, int]) -> str:
        """
        Formate le séparateur du tableau.

        Args:
            col_widths: Largeurs des colonnes

        Returns:
            Séparateur formaté
        """
        w = col_widths
        sep = (
            f"{'-'*w['symbol']}-+-{'-'*w['funding']}-+-{'-'*w['volume']}-+-"
            f"{'-'*w['spread']}-+-{'-'*w['volatility']}-+-"
            f"{'-'*w['funding_time']}"
        )
        return sep

    def format_table_row(
        self, symbol: str, row_data: Dict[str, Any], col_widths: Dict[str, int]
    ) -> str:
        """
        Formate une ligne du tableau.

        Args:
            symbol: Symbole
            row_data: Données de la ligne
            col_widths: Largeurs des colonnes

        Returns:
            Ligne formatée
        """
        w = col_widths

        # Formater chaque colonne
        funding_str = self.format_funding(row_data["funding"], w["funding"])
        volume_str = self.format_volume(row_data["volume"])
        spread_str = self.format_spread(row_data["spread_pct"])
        volatility_str = self.format_volatility(row_data["volatility_pct"])
        funding_time_str = row_data["funding_time"]

        return (
            f"{symbol:<{w['symbol']}} | {funding_str:>{w['funding']}} | "
            f"{volume_str:>{w['volume']}} | {spread_str:>{w['spread']}} | "
            f"{volatility_str:>{w['volatility']}} | "
            f"{funding_time_str:>{w['funding_time']}}"
        )

    def format_funding(self, funding: Optional[float], width: int) -> str:
        """
        Formate la valeur de funding.

        Args:
            funding: Valeur de funding
            width: Largeur de la colonne

        Returns:
            Valeur formatée
        """
        if funding is not None:
            funding_pct = funding * 100.0
            return f"{funding_pct:+{width-1}.4f}%"
        return "null"

    def format_volume(self, volume: Optional[float]) -> str:
        """
        Formate la valeur de volume en millions.

        Args:
            volume: Valeur de volume

        Returns:
            Valeur formatée
        """
        if volume is not None and volume > 0:
            volume_millions = volume / 1_000_000
            return f"{volume_millions:,.1f}"
        return "null"

    def format_spread(self, spread_pct: Optional[float]) -> str:
        """
        Formate la valeur de spread.

        Args:
            spread_pct: Valeur de spread en pourcentage

        Returns:
            Valeur formatée
        """
        if spread_pct is not None:
            spread_pct_display = spread_pct * 100.0
            return f"{spread_pct_display:+.3f}%"
        return "null"

    def format_volatility(self, volatility_pct: Optional[float]) -> str:
        """
        Formate la valeur de volatilité.

        Args:
            volatility_pct: Valeur de volatilité en pourcentage

        Returns:
            Valeur formatée
        """
        if volatility_pct is not None:
            volatility_pct_display = volatility_pct * 100.0
            return f"{volatility_pct_display:+.3f}%"
        return "-"

    def prepare_row_data(self, symbol: str, data_manager) -> Dict[str, Any]:
        """
        Prépare les données d'une ligne avec fallback entre temps réel et REST.

        Utilise les FundingData Value Objects pour récupérer les données de base.

        Args:
            symbol: Symbole à préparer
            data_manager: Gestionnaire de données

        Returns:
            Dict avec les clés: funding, volume, spread_pct, volatility_pct,
            funding_time
        """
        # Récupérer le FundingData Value Object
        funding_data_obj = data_manager.storage.get_funding_data_object(symbol)
        realtime_info = data_manager.storage.get_realtime_data(symbol)

        # Valeurs initiales (REST) comme fallbacks depuis le Value Object
        if funding_data_obj:
            original_funding = funding_data_obj.funding_rate
            original_volume = funding_data_obj.volume_24h
            original_spread = funding_data_obj.spread_pct
        else:
            original_funding = None
            original_volume = None
            original_spread = None

        # Récupérer les données avec priorité temps réel
        funding = self._get_funding_value(realtime_info, original_funding)
        volume = self._get_volume_value(realtime_info, original_volume)
        spread_pct = self._get_spread_value(realtime_info, original_spread)
        volatility_pct = self._get_volatility_value(symbol)
        funding_time = self._get_funding_time_value(
            symbol, realtime_info, data_manager
        )

        # Fournir des valeurs par défaut si les données manquent
        return {
            "funding": funding,
            "volume": volume,
            "spread_pct": spread_pct if spread_pct is not None else 0.0,  # Valeur par défaut
            "volatility_pct": volatility_pct if volatility_pct is not None else 0.0,  # Valeur par défaut
            "funding_time": funding_time,
        }

    def _get_funding_value(
        self, realtime_info: Optional[Dict], original: Optional[float]
    ) -> Optional[float]:
        """Récupère la valeur de funding avec fallback."""
        if not realtime_info:
            return original

        funding_rate = realtime_info.get("funding_rate")
        if funding_rate is not None:
            return float(funding_rate)
        return original

    def _get_volume_value(
        self, realtime_info: Optional[Dict], original: Optional[float]
    ) -> Optional[float]:
        """Récupère la valeur de volume avec fallback."""
        if not realtime_info:
            return original

        volume24h = realtime_info.get("volume24h")
        if volume24h is not None:
            return float(volume24h)
        return original

    def _get_spread_value(
        self, realtime_info: Optional[Dict], original: Optional[float]
    ) -> Optional[float]:
        """Récupère la valeur de spread avec fallback."""
        if not realtime_info:
            return original

        # Calculer le spread en temps réel si on a bid/ask
        bid1_price = realtime_info.get("bid1_price")
        ask1_price = realtime_info.get("ask1_price")

        if bid1_price and ask1_price:
            try:
                bid = float(bid1_price)
                ask = float(ask1_price)
                if bid > 0 and ask > 0:
                    mid = (ask + bid) / 2
                    if mid > 0:
                        return (ask - bid) / mid
            except (ValueError, TypeError):
                pass

        return original

    def _get_volatility_value(self, symbol: str) -> Optional[float]:
        """Récupère la valeur de volatilité."""
        if self._volatility_callback:
            try:
                return self._volatility_callback(symbol)
            except Exception:
                pass
        return None

    def _get_funding_time_value(
        self, symbol: str, realtime_info: Optional[Dict], data_manager
    ) -> str:
        """Récupère la valeur de temps de funding."""
        # Priorité aux données temps réel
        if realtime_info and realtime_info.get("next_funding_time"):
            next_funding = realtime_info["next_funding_time"]
            return self._calculate_funding_time_remaining(next_funding)

        # Fallback aux données originales
        original_data = data_manager.storage.get_original_funding_data(symbol)
        if original_data:
            return self._calculate_funding_time_remaining(original_data)

        return "-"

    def _calculate_funding_time_remaining(self, next_funding_time) -> str:
        """
        Calcule le temps restant avant le funding.

        Args:
            next_funding_time: Timestamp du prochain funding

        Returns:
            Temps restant formaté ou "-"
        """
        try:
            # Convertir le timestamp en secondes si nécessaire
            if isinstance(next_funding_time, str):
                # Format ISO ou timestamp
                if "T" in next_funding_time:
                    # Format ISO
                    dt = datetime.fromisoformat(
                        next_funding_time.replace("Z", "+00:00")
                    )
                    funding_ts = dt.timestamp()
                else:
                    # Timestamp en millisecondes
                    funding_ts = float(next_funding_time) / 1000
            else:
                # Déjà un timestamp
                funding_ts = float(next_funding_time)

            # Calculer le temps restant
            now_ts = time.time()
            remaining_seconds = funding_ts - now_ts

            if remaining_seconds <= 0:
                return "0s"

            # Formater en heures, minutes, secondes
            hours = int(remaining_seconds // 3600)
            minutes = int((remaining_seconds % 3600) // 60)
            seconds = int(remaining_seconds % 60)

            if hours > 0:
                return f"{hours}h {minutes}m"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"

        except Exception:
            return "-"

    def are_all_data_available(self, funding_data: Dict, data_manager) -> bool:
        """
        Vérifie si toutes les données nécessaires (volatilité et spread)
        sont disponibles.

        Args:
            funding_data: Données de funding des symboles
            data_manager: Gestionnaire de données

        Returns:
            True si toutes les données sont disponibles, False sinon
        """
        if not funding_data:
            return False

        # MODIFICATION: Vérifier seulement si les données de base (funding) sont disponibles
        # Les autres données (volatilité, spread) peuvent être manquantes sans bloquer l'affichage
        for symbol in funding_data.keys():
            row_data = self.prepare_row_data(symbol, data_manager)

            # Vérifier seulement si les données de funding sont disponibles
            funding = row_data.get("funding")
            if funding is None:
                return False

        return True
