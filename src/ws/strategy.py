#!/usr/bin/env python3
"""
Stratégie de connexion WebSocket pour le bot Bybit.

Ce module gère la logique de répartition des symboles entre les connexions
linear et inverse, et détermine la stratégie de connexion optimale.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from logging_setup import setup_logging


@dataclass
class ConnectionStrategy:
    """Stratégie de connexion WebSocket."""
    needs_linear: bool
    needs_inverse: bool
    total_connections: int
    linear_symbols: List[str]
    inverse_symbols: List[str]


class WebSocketConnectionStrategy:
    """
    Gestionnaire de stratégie de connexion WebSocket.
    
    Responsabilités :
    - Analyser les symboles fournis
    - Déterminer la stratégie de connexion optimale
    - Séparer les symboles par catégorie
    - Optimiser le nombre de connexions
    """
    
    def __init__(self, logger=None):
        """
        Initialise la stratégie de connexion.
        
        Args:
            logger: Logger pour les messages
        """
        self.logger = logger or setup_logging()
    
    def analyze_symbols(self, linear_symbols: List[str], inverse_symbols: List[str]) -> ConnectionStrategy:
        """
        Analyse les symboles et détermine la stratégie de connexion.
        
        Args:
            linear_symbols: Symboles linear (USDT)
            inverse_symbols: Symboles inverse (USD)
            
        Returns:
            ConnectionStrategy: Stratégie optimale
        """
        needs_linear = len(linear_symbols) > 0
        needs_inverse = len(inverse_symbols) > 0
        
        total_connections = sum([needs_linear, needs_inverse])
        
        strategy = ConnectionStrategy(
            needs_linear=needs_linear,
            needs_inverse=needs_inverse,
            total_connections=total_connections,
            linear_symbols=linear_symbols,
            inverse_symbols=inverse_symbols
        )
        
        self.logger.info(f"📊 Stratégie connexion: {total_connections} connexion(s) "
                        f"(linear: {needs_linear}, inverse: {needs_inverse})")
        
        return strategy
    
    def get_connection_plan(self, strategy: ConnectionStrategy) -> List[Dict[str, any]]:
        """
        Génère le plan de connexion basé sur la stratégie.
        
        Args:
            strategy: Stratégie de connexion
            
        Returns:
            Liste des plans de connexion
        """
        plans = []
        
        if strategy.needs_linear:
            plans.append({
                "category": "linear",
                "symbols": strategy.linear_symbols,
                "priority": 1
            })
        
        if strategy.needs_inverse:
            plans.append({
                "category": "inverse", 
                "symbols": strategy.inverse_symbols,
                "priority": 2
            })
        
        return plans
    
    def optimize_symbols(self, symbols: List[str], max_per_connection: int = 100) -> List[str]:
        """
        Optimise la liste des symboles pour une connexion.
        
        Args:
            symbols: Liste des symboles
            max_per_connection: Maximum par connexion
            
        Returns:
            Liste optimisée des symboles
        """
        if len(symbols) <= max_per_connection:
            return symbols
        
        # Trier par priorité (ex: volume, liquidité)
        # Pour l'instant, on garde les premiers
        optimized = symbols[:max_per_connection]
        
        self.logger.warning(f"⚠️ Limitation symboles: {len(symbols)} → {len(optimized)} "
                           f"(max {max_per_connection})")
        
        return optimized
    
    def validate_symbols(self, symbols: List[str], category: str) -> List[str]:
        """
        Valide et filtre les symboles pour une catégorie.
        
        Args:
            symbols: Liste des symboles
            category: Catégorie ("linear" ou "inverse")
            
        Returns:
            Liste des symboles valides
        """
        if not symbols:
            return []
        
        valid_symbols = []
        
        for symbol in symbols:
            if not symbol or not isinstance(symbol, str):
                continue
                
            # Validation basique selon la catégorie
            if category == "linear":
                if symbol.endswith("USDT"):
                    valid_symbols.append(symbol)
                else:
                    self.logger.debug(f"⚠️ Symbole {symbol} ignoré (pas USDT)")
            elif category == "inverse":
                if symbol.endswith("USD") and not symbol.endswith("USDT"):
                    valid_symbols.append(symbol)
                else:
                    self.logger.debug(f"⚠️ Symbole {symbol} ignoré (pas USD)")
        
        if len(valid_symbols) != len(symbols):
            self.logger.info(f"✅ Validation {category}: {len(symbols)} → {len(valid_symbols)} symboles")
        
        return valid_symbols
    
    def get_connection_summary(self, strategy: ConnectionStrategy) -> Dict[str, any]:
        """
        Génère un résumé de la stratégie de connexion.
        
        Args:
            strategy: Stratégie de connexion
            
        Returns:
            Résumé de la stratégie
        """
        return {
            "total_connections": strategy.total_connections,
            "linear_count": len(strategy.linear_symbols),
            "inverse_count": len(strategy.inverse_symbols),
            "needs_linear": strategy.needs_linear,
            "needs_inverse": strategy.needs_inverse,
            "strategy_type": self._get_strategy_type(strategy)
        }
    
    def _get_strategy_type(self, strategy: ConnectionStrategy) -> str:
        """Détermine le type de stratégie."""
        if strategy.total_connections == 0:
            return "none"
        elif strategy.total_connections == 1:
            return "single"
        else:
            return "dual"
