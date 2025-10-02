#!/usr/bin/env python3
"""
Wrapper de compatibilité pour le filtre de symboles du bot Bybit.

Ce fichier maintient la compatibilité avec l'interface existante
tout en utilisant la nouvelle implémentation basée sur BaseFilter.
"""

from typing import List, Tuple, Dict, Optional
from logging_setup import setup_logging
from filters.symbol_filter import SymbolFilter as NewSymbolFilter


class SymbolFilter:
    """
    Wrapper de compatibilité pour le filtre de symboles.
    
    Cette classe maintient l'interface publique de l'ancien SymbolFilter
    tout en utilisant la nouvelle implémentation basée sur BaseFilter.
    
    Responsabilités :
    - Filtrage par funding, volume et fenêtre temporelle
    - Filtrage par spread
    - Calculs de temps de funding
    - Tri et sélection des symboles
    """
    
    def __init__(self, logger=None):
        """
        Initialise le filtre de symboles.
        
        Args:
            logger: Logger pour les messages (optionnel)
        """
        self.logger = logger or setup_logging()
        self._new_filter = NewSymbolFilter(logger=self.logger)
    
    def filter_by_funding(
        self, 
        perp_data: Dict, 
        funding_map: Dict, 
        funding_min: Optional[float], 
        funding_max: Optional[float], 
        volume_min_millions: Optional[float], 
        limite: Optional[int], 
        funding_time_min_minutes: Optional[int] = None, 
        funding_time_max_minutes: Optional[int] = None
    ) -> List[Tuple[str, float, float, str]]:
        """
        Filtre les symboles par funding, volume et fenêtre temporelle avant funding.
        
        Args:
            perp_data: Données des perpétuels (linear, inverse, total)
            funding_map: Dictionnaire des funding rates, volumes et temps de funding
            funding_min: Funding minimum en valeur absolue
            funding_max: Funding maximum en valeur absolue
            volume_min_millions: Volume minimum en millions
            limite: Limite du nombre d'éléments
            funding_time_min_minutes: Temps minimum en minutes avant prochain funding
            funding_time_max_minutes: Temps maximum en minutes avant prochain funding
            
        Returns:
            Liste des (symbol, funding, volume, funding_time_remaining) triés
        """
        # Déléguer à la nouvelle implémentation
        return self._new_filter.filter_by_funding(
            perp_data,
            funding_map,
            funding_min,
            funding_max,
            volume_min_millions,
            limite,
            funding_time_min_minutes=funding_time_min_minutes,
            funding_time_max_minutes=funding_time_max_minutes,
        )
    
    def filter_by_spread(
        self, 
        symbols_data: List[Tuple], 
        spread_data: Dict[str, float], 
        spread_max: Optional[float]
    ) -> List[Tuple[str, float, float, str, float]]:
        """
        Filtre les symboles par spread maximum.
        
        Args:
            symbols_data: Liste des (symbol, funding, volume, funding_time_remaining)
            spread_data: Dictionnaire des spreads {symbol: spread_pct}
            spread_max: Spread maximum autorisé
            
        Returns:
            Liste des (symbol, funding, volume, funding_time_remaining, spread_pct) filtrés
        """
        # Déléguer à la nouvelle implémentation
        return self._new_filter.filter_by_spread(symbols_data, spread_data, spread_max)
    
    def calculate_funding_time_remaining(self, next_funding_time) -> str:
        """
        Retourne "Xh Ym Zs" à partir d'un timestamp Bybit (ms) ou ISO.
        
        Args:
            next_funding_time: Timestamp du prochain funding (ms ou ISO string)
            
        Returns:
            str: Temps restant formaté ou "-" si invalide
        """
        # Déléguer à la nouvelle implémentation
        return self._new_filter.calculate_funding_time_remaining(next_funding_time)
    
    def calculate_funding_minutes_remaining(self, next_funding_time) -> Optional[float]:
        """
        Calcule les minutes restantes avant le prochain funding.
        
        Args:
            next_funding_time: Timestamp du prochain funding
            
        Returns:
            float: Minutes restantes ou None si erreur
        """
        # Déléguer à la nouvelle implémentation
        return self._new_filter.calculate_funding_minutes_remaining(next_funding_time)
    
    def build_funding_data_dict(
        self, 
        symbols_data: List[Tuple]
    ) -> Dict[str, Dict]:
        """
        Construit un dictionnaire de données de funding à partir des symboles filtrés.
        
        Args:
            symbols_data: Liste des tuples (symbol, funding, volume, funding_time_remaining, ...)
            
        Returns:
            Dictionnaire {symbol: {funding, volume, funding_time_remaining, spread_pct, volatility_pct}}
        """
        funding_data = {}
        
        for symbol_data in symbols_data:
            if len(symbol_data) >= 4:
                symbol = symbol_data[0]
                funding = symbol_data[1]
                volume = symbol_data[2]
                funding_time_remaining = symbol_data[3]
                
                # Ajouter les données optionnelles selon la longueur du tuple
                spread_pct = symbol_data[4] if len(symbol_data) > 4 else 0.0
                volatility_pct = symbol_data[5] if len(symbol_data) > 5 else None
                
                funding_data[symbol] = {
                    "funding": funding,
                    "volume": volume,
                    "funding_time_remaining": funding_time_remaining,
                    "spread_pct": spread_pct,
                    "volatility_pct": volatility_pct
                }
        
        return funding_data
    
    def separate_symbols_by_category(
        self, 
        symbols_data: List[Tuple], 
        symbol_categories: Dict[str, str]
    ) -> Tuple[List[str], List[str]]:
        """
        Sépare les symboles par catégorie (linear/inverse).
        
        Args:
            symbols_data: Liste des données de symboles
            symbol_categories: Mapping des catégories de symboles
            
        Returns:
            Tuple[linear_symbols, inverse_symbols]
        """
        # Déléguer à la nouvelle implémentation
        return self._new_filter.separate_symbols_by_category(symbols_data, symbol_categories)
    
    def check_candidate_filters(
        self, 
        symbol: str, 
        funding_map: Dict, 
        funding_min: Optional[float], 
        funding_max: Optional[float], 
        volume_min_millions: Optional[float], 
        funding_time_max_minutes: Optional[int]
    ) -> bool:
        """
        Vérifie si un symbole candidat passe les filtres de base.
        
        Args:
            symbol: Symbole à vérifier
            funding_map: Dictionnaire des données de funding
            funding_min: Funding minimum
            funding_max: Funding maximum
            volume_min_millions: Volume minimum en millions
            funding_time_max_minutes: Temps maximum avant funding en minutes
            
        Returns:
            True si le symbole passe les filtres
        """
        return self._new_filter.check_candidate_filters(
            symbol, funding_map, funding_min, funding_max, 
            volume_min_millions, funding_time_max_minutes
        )
    
    def check_realtime_filters(
        self, 
        symbol: str, 
        ticker_data: dict, 
        funding_min: Optional[float], 
        funding_max: Optional[float], 
        volume_min_millions: Optional[float]
    ) -> bool:
        """
        Vérifie si un symbole passe les filtres en temps réel.
        
        Args:
            symbol: Symbole à vérifier
            ticker_data: Données du ticker reçues via WebSocket
            funding_min: Funding minimum
            funding_max: Funding maximum
            volume_min_millions: Volume minimum en millions
            
        Returns:
            True si le symbole passe les filtres
        """
        return self._new_filter.check_realtime_filters(
            symbol, ticker_data, funding_min, funding_max, volume_min_millions
        )