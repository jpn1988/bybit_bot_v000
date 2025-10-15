#!/usr/bin/env python3
"""
Value Object pour les données de ticker.

Ce module définit TickerData, un Value Object immutable pour encapsuler
les données de ticker reçues via WebSocket avec validation automatique.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TickerData:
    """
    Value Object pour les données de ticker d'un symbole.
    
    Cette classe est immutable (frozen=True) et valide automatiquement
    les données lors de la création.
    
    Attributes:
        symbol: Symbole du contrat (ex: BTCUSDT)
        last_price: Dernier prix de transaction
        mark_price: Prix de marque
        index_price: Prix de l'index (optionnel)
        bid1_price: Meilleur prix d'achat (optionnel)
        ask1_price: Meilleur prix de vente (optionnel)
        volume_24h: Volume sur 24h (optionnel)
        turnover_24h: Turnover sur 24h en USDT (optionnel)
        funding_rate: Taux de funding actuel (optionnel)
        next_funding_time: Timestamp du prochain funding (optionnel)
        open_interest: Open interest (optionnel)
        timestamp: Timestamp de la mise à jour
        
    Raises:
        ValueError: Si les valeurs sont invalides
    """
    
    symbol: str
    last_price: float
    mark_price: float
    timestamp: float
    index_price: Optional[float] = None
    bid1_price: Optional[float] = None
    ask1_price: Optional[float] = None
    volume_24h: Optional[float] = None
    turnover_24h: Optional[float] = None
    funding_rate: Optional[float] = None
    next_funding_time: Optional[str] = None
    open_interest: Optional[float] = None
    
    def __post_init__(self):
        """
        Validation automatique des données après initialisation.
        
        Raises:
            ValueError: Si une valeur est invalide
        """
        # Validation du symbole
        if not self.symbol or not isinstance(self.symbol, str):
            raise ValueError(f"Symbol invalide: {self.symbol}")
        
        # Validation des prix (doivent être positifs)
        if self.last_price <= 0:
            raise ValueError(
                f"Last price invalide pour {self.symbol}: {self.last_price}"
            )
        
        if self.mark_price <= 0:
            raise ValueError(
                f"Mark price invalide pour {self.symbol}: {self.mark_price}"
            )
        
        # Validation des prix optionnels
        if self.index_price is not None and self.index_price <= 0:
            raise ValueError(
                f"Index price invalide pour {self.symbol}: {self.index_price}"
            )
        
        if self.bid1_price is not None and self.bid1_price <= 0:
            raise ValueError(
                f"Bid price invalide pour {self.symbol}: {self.bid1_price}"
            )
        
        if self.ask1_price is not None and self.ask1_price <= 0:
            raise ValueError(
                f"Ask price invalide pour {self.symbol}: {self.ask1_price}"
            )
        
        # Validation du volume
        if self.volume_24h is not None and self.volume_24h < 0:
            raise ValueError(
                f"Volume négatif pour {self.symbol}: {self.volume_24h}"
            )
        
        if self.turnover_24h is not None and self.turnover_24h < 0:
            raise ValueError(
                f"Turnover négatif pour {self.symbol}: {self.turnover_24h}"
            )
        
        # Validation du timestamp
        if self.timestamp <= 0:
            raise ValueError(
                f"Timestamp invalide pour {self.symbol}: {self.timestamp}"
            )
    
    @property
    def spread_pct(self) -> Optional[float]:
        """
        Calcule le spread en pourcentage si bid et ask sont disponibles.
        
        Returns:
            float: Spread en pourcentage (0.01 = 1%) ou None
        """
        if self.bid1_price is None or self.ask1_price is None:
            return None
        
        if self.bid1_price <= 0:
            return None
        
        spread = (self.ask1_price - self.bid1_price) / self.bid1_price
        return spread
    
    
    def to_dict(self) -> dict:
        """
        Convertit en dictionnaire.
        
        Returns:
            dict: Dictionnaire avec tous les champs
        """
        result = {
            "symbol": self.symbol,
            "lastPrice": str(self.last_price),
            "markPrice": str(self.mark_price),
            "timestamp": int(self.timestamp),
        }
        
        # Ajouter les champs optionnels s'ils sont présents
        if self.index_price is not None:
            result["indexPrice"] = str(self.index_price)
        
        if self.bid1_price is not None:
            result["bid1Price"] = str(self.bid1_price)
        
        if self.ask1_price is not None:
            result["ask1Price"] = str(self.ask1_price)
        
        if self.volume_24h is not None:
            result["volume24h"] = str(self.volume_24h)
        
        if self.turnover_24h is not None:
            result["turnover24h"] = str(self.turnover_24h)
        
        if self.funding_rate is not None:
            result["fundingRate"] = str(self.funding_rate)
        
        if self.next_funding_time is not None:
            result["nextFundingTime"] = str(self.next_funding_time)
        
        if self.open_interest is not None:
            result["openInterest"] = str(self.open_interest)
        
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> "TickerData":
        """
        Crée une instance depuis un dictionnaire (format API Bybit).
        
        Args:
            data: Dictionnaire contenant les données du ticker
            
        Returns:
            TickerData: Nouvelle instance
        """
        def safe_float(value, default=None):
            """Convertit en float de manière sécurisée."""
            if value is None:
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default
        
        return cls(
            symbol=data.get("symbol", ""),
            last_price=safe_float(data.get("lastPrice"), 0.0),
            mark_price=safe_float(data.get("markPrice"), 0.0),
            timestamp=safe_float(data.get("timestamp"), 0.0),
            index_price=safe_float(data.get("indexPrice")),
            bid1_price=safe_float(data.get("bid1Price")),
            ask1_price=safe_float(data.get("ask1Price")),
            volume_24h=safe_float(data.get("volume24h")),
            turnover_24h=safe_float(data.get("turnover24h")),
            funding_rate=safe_float(data.get("fundingRate")),
            next_funding_time=data.get("nextFundingTime"),
            open_interest=safe_float(data.get("openInterest")),
        )

