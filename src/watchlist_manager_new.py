#!/usr/bin/env python3
"""
Gestionnaire de watchlist pour le bot Bybit - Version refactorisée.

Cette classe est un wrapper autour de WatchlistBuilder pour maintenir la compatibilité
avec l'interface existante tout en utilisant la nouvelle architecture modulaire.
"""

from typing import List, Tuple, Dict
from logging_setup import setup_logging
from watchlist_builder import WatchlistBuilder
from volatility_tracker import VolatilityTracker


class WatchlistManager:
    """
    Gestionnaire de watchlist pour le bot Bybit - Version refactorisée.
    
    Cette classe maintient l'interface publique de l'ancien WatchlistManager
    tout en utilisant la nouvelle architecture modulaire.
    """
    
    def __init__(self, testnet: bool = True, logger=None):
        """
        Initialise le gestionnaire de watchlist.
        
        Args:
            testnet (bool): Utiliser le testnet (True) ou le marché réel (False)
            logger: Logger pour les messages (optionnel)
        """
        self.testnet = testnet
        self.logger = logger or setup_logging()
        
        # Utiliser le nouveau constructeur
        self._builder = WatchlistBuilder(testnet=testnet, logger=self.logger)
        
        # Propriétés pour la compatibilité
        self.config = {}
        self.symbol_categories = {}
        self.selected_symbols = []
        self.funding_data = {}
        self.original_funding_data = {}
    
    def load_and_validate_config(self) -> Dict:
        """
        Charge et valide la configuration depuis le fichier YAML.
        
        Returns:
            Dict: Configuration validée
            
        Raises:
            ValueError: Si la configuration est invalide
        """
        config = self._builder.load_and_validate_config()
        self.config = config
        return config
    
    def set_symbol_categories(self, symbol_categories: Dict[str, str]):
        """
        Définit le mapping des catégories de symboles.
        
        Args:
            symbol_categories: Dictionnaire {symbol: category}
        """
        self.symbol_categories = symbol_categories
        self._builder.set_symbol_categories(symbol_categories)
    
    def build_watchlist(
        self,
        base_url: str,
        perp_data: Dict,
        volatility_tracker: VolatilityTracker
    ) -> Tuple[List[str], List[str], Dict]:
        """
        Construit la watchlist complète en appliquant tous les filtres.
        
        Args:
            base_url: URL de base de l'API Bybit
            perp_data: Données des perpétuels
            volatility_tracker: Tracker de volatilité pour le filtrage
            
        Returns:
            Tuple[linear_symbols, inverse_symbols, funding_data]
        """
        linear_symbols, inverse_symbols, funding_data = self._builder.build_watchlist(
            base_url, perp_data, volatility_tracker
        )
        
        # Mettre à jour les propriétés pour la compatibilité
        self.selected_symbols = self._builder.get_selected_symbols()
        self.funding_data = self._builder.get_funding_data()
        self.original_funding_data = self._builder.get_original_funding_data()
        
        return linear_symbols, inverse_symbols, funding_data
    
    def find_candidate_symbols(self, base_url: str, perp_data: Dict) -> List[str]:
        """
        Trouve les symboles qui sont proches de passer les filtres (candidats).
        
        Args:
            base_url: URL de base de l'API Bybit
            perp_data: Données des perpétuels
            
        Returns:
            Liste des symboles candidats
        """
        return self._builder.find_candidate_symbols(base_url, perp_data)
    
    def check_if_symbol_now_passes_filters(self, symbol: str, ticker_data: dict) -> bool:
        """
        Vérifie si un symbole candidat passe maintenant les filtres.
        
        Args:
            symbol: Symbole à vérifier
            ticker_data: Données du ticker reçues via WebSocket
            
        Returns:
            True si le symbole passe maintenant les filtres
        """
        return self._builder.check_if_symbol_now_passes_filters(symbol, ticker_data)
    
    def get_selected_symbols(self) -> List[str]:
        """
        Retourne la liste des symboles sélectionnés.
        
        Returns:
            Liste des symboles de la watchlist
        """
        return self.selected_symbols.copy()
    
    def get_funding_data(self) -> Dict:
        """
        Retourne les données de funding de la watchlist.
        
        Returns:
            Dictionnaire des données de funding
        """
        return self.funding_data.copy()
    
    def get_original_funding_data(self) -> Dict:
        """
        Retourne les données de funding originales (next_funding_time).
        
        Returns:
            Dictionnaire des next_funding_time originaux
        """
        return self.original_funding_data.copy()
