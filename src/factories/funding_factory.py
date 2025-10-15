#!/usr/bin/env python3
"""
Factory centralisée pour créer FundingData Value Objects.

Ce module centralise la logique de création de FundingData pour éviter
la duplication de code entre opportunity_manager.py et data_manager.py.
"""

from typing import Dict, Any, Optional, Tuple, List, Union
from models.funding_data import FundingData


class FundingDataFactory:
    """Factory centralisée pour créer FundingData Value Objects."""
    
    @staticmethod
    def from_ticker_data(
        symbol: str, 
        ticker_data: dict, 
        watchlist_manager=None
    ) -> Optional[FundingData]:
        """
        Crée FundingData depuis données ticker WebSocket.
        
        Args:
            symbol: Symbole du contrat
            ticker_data: Données ticker reçues via WebSocket
            watchlist_manager: Manager pour calculer funding_time_remaining (optionnel)
            
        Returns:
            FundingData ou None si données invalides
        """
        try:
            # Extraire les données du ticker
            funding_rate = ticker_data.get("fundingRate")
            volume24h = ticker_data.get("volume24h")
            next_funding_time = ticker_data.get("nextFundingTime")
            
            if funding_rate is None:
                return None
                
            funding = float(funding_rate)
            volume = float(volume24h) if volume24h is not None else 0.0
            
            # Calculer le temps de funding restant
            if watchlist_manager and next_funding_time:
                funding_time_remaining = watchlist_manager.calculate_funding_time_remaining(next_funding_time)
            else:
                funding_time_remaining = "-"
            
            # Calculer le spread si disponible
            spread_pct = FundingDataFactory._calculate_spread_from_ticker(ticker_data)
            
            return FundingData(
                symbol=symbol,
                funding_rate=funding,
                volume_24h=volume,
                next_funding_time=funding_time_remaining,
                spread_pct=spread_pct,
                volatility_pct=None  # Sera calculé séparément
            )
            
        except (ValueError, TypeError) as e:
            return None
    
    @staticmethod
    def from_tuple_data(symbol: str, data: Tuple) -> Optional[FundingData]:
        """
        Crée FundingData depuis format tuple (compatibilité data_manager).
        
        Args:
            symbol: Symbole du contrat
            data: Tuple (funding, volume, funding_time, spread, volatility?)
            
        Returns:
            FundingData ou None si données invalides
        """
        try:
            if len(data) < 4:
                return None
                
            funding, volume, funding_time, spread = data[:4]
            volatility = data[4] if len(data) > 4 else None
            
            return FundingData(
                symbol=symbol,
                funding_rate=funding,
                volume_24h=volume,
                next_funding_time=funding_time,
                spread_pct=spread,
                volatility_pct=volatility
            )
            
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def from_dict_data(symbol: str, data: Dict[str, Any]) -> Optional[FundingData]:
        """
        Crée FundingData depuis format dictionnaire (compatibilité data_manager).
        
        Args:
            symbol: Symbole du contrat
            data: Dict avec clés funding, volume, funding_time_remaining, etc.
            
        Returns:
            FundingData ou None si données invalides
        """
        try:
            funding = data.get("funding", 0.0)
            volume = data.get("volume", 0.0)
            funding_time = data.get("funding_time_remaining", "-")
            spread = data.get("spread_pct", 0.0)
            volatility = data.get("volatility_pct", None)
            
            return FundingData(
                symbol=symbol,
                funding_rate=funding,
                volume_24h=volume,
                next_funding_time=funding_time,
                spread_pct=spread,
                volatility_pct=volatility
            )
            
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def from_raw_data(
        symbol: str, 
        data: Union[Dict[str, Any], Tuple, List]
    ) -> Optional[FundingData]:
        """
        Factory universelle qui détecte automatiquement le format des données.
        
        Args:
            symbol: Symbole du contrat
            data: Données en format dict, tuple, ou list
            
        Returns:
            FundingData ou None si format non supporté
        """
        if isinstance(data, dict):
            return FundingDataFactory.from_dict_data(symbol, data)
        elif isinstance(data, (tuple, list)) and len(data) >= 4:
            return FundingDataFactory.from_tuple_data(symbol, tuple(data))
        else:
            return None
    
    @staticmethod
    def _calculate_spread_from_ticker(ticker_data: Dict[str, Any]) -> float:
        """
        Calcule le spread depuis les données de ticker.
        
        Args:
            ticker_data: Données ticker avec bid1Price et ask1Price
            
        Returns:
            Spread en pourcentage (0.0 si calcul impossible)
        """
        try:
            bid1_price = ticker_data.get("bid1Price")
            ask1_price = ticker_data.get("ask1Price")
            
            if not bid1_price or not ask1_price:
                return 0.0
                
            bid = float(bid1_price)
            ask = float(ask1_price)
            
            if bid <= 0 or ask <= 0:
                return 0.0
                
            mid = (ask + bid) / 2
            if mid <= 0:
                return 0.0
                
            return (ask - bid) / mid
            
        except (ValueError, TypeError):
            return 0.0
