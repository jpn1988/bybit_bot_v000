#!/usr/bin/env python3
"""
Value Object pour les données de funding.

Ce module définit FundingData, un Value Object immutable pour encapsuler
les données de funding d'un symbole avec validation automatique.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class FundingData:
    """
    Value Object pour les données de funding d'un symbole.

    Cette classe est immutable (frozen=True) et valide automatiquement
    les données lors de la création.

    Attributes:
        symbol: Symbole du contrat (ex: BTCUSDT)
        funding_rate: Taux de funding (entre -1 et 1, typiquement -0.01 à 0.01)
        volume_24h: Volume sur 24h en USDT
        next_funding_time: Temps restant avant le prochain funding (format: "1h 30m")
        spread_pct: Spread bid/ask en pourcentage (0.0 à 1.0)
        volatility_pct: Volatilité 5 minutes en pourcentage (optionnel)

    Raises:
        ValueError: Si les valeurs sont invalides
    """

    symbol: str
    funding_rate: float
    volume_24h: float
    next_funding_time: str
    spread_pct: float
    volatility_pct: Optional[float] = None
    weight: Optional[float] = None

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

        # Validation du taux de funding (typiquement entre -1% et 1%, mais peut aller jusqu'à -100% à 100%)
        if not isinstance(self.funding_rate, (int, float)):
            raise ValueError(
                f"Funding rate doit être un nombre: {self.funding_rate}"
            )

        if self.funding_rate < -1.0 or self.funding_rate > 1.0:
            raise ValueError(
                f"Funding rate hors limites pour {self.symbol}: "
                f"{self.funding_rate} (doit être entre -1.0 et 1.0)"
            )

        # Validation du volume
        if not isinstance(self.volume_24h, (int, float)):
            raise ValueError(
                f"Volume doit être un nombre: {self.volume_24h}"
            )

        if self.volume_24h < 0:
            raise ValueError(
                f"Volume négatif pour {self.symbol}: {self.volume_24h}"
            )

        # Validation du temps de funding
        if not isinstance(self.next_funding_time, str):
            raise ValueError(
                f"Next funding time doit être une chaîne: {self.next_funding_time}"
            )

        # Validation du spread
        if not isinstance(self.spread_pct, (int, float)):
            raise ValueError(
                f"Spread doit être un nombre: {self.spread_pct}"
            )

        if self.spread_pct < 0 or self.spread_pct > 1.0:
            raise ValueError(
                f"Spread hors limites pour {self.symbol}: "
                f"{self.spread_pct} (doit être entre 0.0 et 1.0)"
            )

        # Validation de la volatilité (optionnelle)
        if self.volatility_pct is not None:
            if not isinstance(self.volatility_pct, (int, float)):
                raise ValueError(
                    f"Volatility doit être un nombre: {self.volatility_pct}"
                )

            if self.volatility_pct < 0:
                raise ValueError(
                    f"Volatilité négative pour {self.symbol}: {self.volatility_pct}"
                )

        # Validation du poids (optionnel)
        if self.weight is not None:
            if not isinstance(self.weight, (int, float)):
                raise ValueError(
                    f"Weight doit être un nombre: {self.weight}"
                )

    @property
    def funding_rate_pct(self) -> float:
        """Retourne le taux de funding en pourcentage (0.01 = 1%)."""
        return self.funding_rate * 100

    @property
    def volume_millions(self) -> float:
        """Retourne le volume en millions."""
        return self.volume_24h / 1_000_000

    @property
    def has_volatility(self) -> bool:
        """Vérifie si les données de volatilité sont disponibles."""
        return self.volatility_pct is not None

    def to_tuple(self) -> tuple:
        """
        Convertit en tuple pour compatibilité avec l'ancien code.

        Returns:
            tuple: (funding_rate, volume_24h, next_funding_time, spread_pct, volatility_pct, weight)
        """
        return (
            self.funding_rate,
            self.volume_24h,
            self.next_funding_time,
            self.spread_pct,
            self.volatility_pct,
            self.weight,
        )

    def to_dict(self) -> dict:
        """
        Convertit en dictionnaire.

        Returns:
            dict: Dictionnaire avec tous les champs
        """
        return {
            "symbol": self.symbol,
            "funding_rate": self.funding_rate,
            "funding_rate_pct": self.funding_rate_pct,
            "volume_24h": self.volume_24h,
            "volume_millions": self.volume_millions,
            "next_funding_time": self.next_funding_time,
            "spread_pct": self.spread_pct,
            "volatility_pct": self.volatility_pct,
            "weight": self.weight,
        }

    @classmethod
    def from_tuple(
        cls,
        symbol: str,
        data: tuple
    ) -> "FundingData":
        """
        Crée une instance depuis un tuple (compatibilité avec l'ancien code).

        Args:
            symbol: Symbole du contrat
            data: Tuple (funding_rate, volume_24h, next_funding_time, spread_pct, volatility_pct, weight)

        Returns:
            FundingData: Nouvelle instance
        """
        if len(data) < 4:
            raise ValueError(
                f"Tuple invalide pour {symbol}: doit contenir au moins 4 éléments"
            )

        funding_rate, volume_24h, next_funding_time, spread_pct = data[:4]
        volatility_pct = data[4] if len(data) > 4 else None
        weight = data[5] if len(data) > 5 else None

        return cls(
            symbol=symbol,
            funding_rate=funding_rate,
            volume_24h=volume_24h,
            next_funding_time=next_funding_time,
            spread_pct=spread_pct,
            volatility_pct=volatility_pct,
            weight=weight,
        )

    @classmethod
    def from_dict(cls, data: dict) -> "FundingData":
        """
        Crée une instance depuis un dictionnaire.

        Args:
            data: Dictionnaire contenant les données

        Returns:
            FundingData: Nouvelle instance
        """
        return cls(
            symbol=data["symbol"],
            funding_rate=data["funding_rate"],
            volume_24h=data["volume_24h"],
            next_funding_time=data["next_funding_time"],
            spread_pct=data["spread_pct"],
            volatility_pct=data.get("volatility_pct"),
            weight=data.get("weight"),
        )

