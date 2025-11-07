#!/usr/bin/env python3
"""
Value Object pour les données de symbole.

Ce module définit SymbolData, un Value Object immutable pour encapsuler
les informations d'un symbole de trading.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SymbolData:
    """
    Value Object pour les informations d'un symbole de trading.

    Cette classe est immutable (frozen=True) et valide automatiquement
    les données lors de la création.

    Attributes:
        symbol: Symbole du contrat (ex: BTCUSDT)
        category: Catégorie du contrat ("linear" ou "inverse")
        base_coin: Coin de base (ex: BTC pour BTCUSDT)
        quote_coin: Coin de quote (ex: USDT pour BTCUSDT)
        contract_type: Type de contrat (ex: "LinearPerpetual")
        status: Statut du symbole (ex: "Trading")
        launch_time: Timestamp de lancement (optionnel)

    Raises:
        ValueError: Si les valeurs sont invalides
    """

    symbol: str
    category: str
    base_coin: str = ""
    quote_coin: str = ""
    contract_type: str = ""
    status: str = "Trading"
    launch_time: Optional[int] = None

    def __post_init__(self):
        """
        Validation automatique des données après initialisation.

        Raises:
            ValueError: Si une valeur est invalide
        """
        # Validation du symbole
        if not self.symbol or not isinstance(self.symbol, str):
            raise ValueError(f"Symbol invalide: {self.symbol}")

        if len(self.symbol) < 3:
            raise ValueError(
                f"Symbol trop court: {self.symbol} (minimum 3 caractères)"
            )

        # Validation de la catégorie
        valid_categories = ["linear", "inverse"]
        if self.category not in valid_categories:
            raise ValueError(
                f"Catégorie invalide pour {self.symbol}: {self.category} "
                f"(doit être {' ou '.join(valid_categories)})"
            )

    @property
    def is_linear(self) -> bool:
        """Vérifie si le symbole est de type linear."""
        return self.category == "linear"

    @property
    def is_inverse(self) -> bool:
        """Vérifie si le symbole est de type inverse."""
        return self.category == "inverse"

    @property
    def is_trading(self) -> bool:
        """Vérifie si le symbole est en état de trading."""
        return self.status.lower() == "trading"

    def to_dict(self) -> dict:
        """
        Convertit en dictionnaire.

        Returns:
            dict: Dictionnaire avec tous les champs
        """
        result = {
            "symbol": self.symbol,
            "category": self.category,
            "baseCoin": self.base_coin,
            "quoteCoin": self.quote_coin,
            "contractType": self.contract_type,
            "status": self.status,
        }

        if self.launch_time is not None:
            result["launchTime"] = self.launch_time

        return result

    @classmethod
    def from_dict(cls, data: dict, category: str = "linear") -> "SymbolData":
        """
        Crée une instance depuis un dictionnaire (format API Bybit).

        Args:
            data: Dictionnaire contenant les données du symbole
            category: Catégorie par défaut si non spécifiée

        Returns:
            SymbolData: Nouvelle instance
        """
        return cls(
            symbol=data.get("symbol", ""),
            category=data.get("category", category),
            base_coin=data.get("baseCoin", ""),
            quote_coin=data.get("quoteCoin", ""),
            contract_type=data.get("contractType", ""),
            status=data.get("status", "Trading"),
            launch_time=data.get("launchTime"),
        )

