#!/usr/bin/env python3
"""
Gestionnaire d'opportunités pour le bot Bybit.

Cette classe gère uniquement :
- La détection de nouvelles opportunités
- L'intégration des opportunités dans la watchlist
- La gestion des symboles candidats
"""

from typing import List, Dict, Optional, Callable
from logging_setup import setup_logging
from data_manager import DataManager
from watchlist_manager import WatchlistManager
from instruments import category_of_symbol


class OpportunityManager:
    """
    Gestionnaire d'opportunités pour le bot Bybit.
    
    Responsabilités :
    - Détection de nouvelles opportunités
    - Intégration des opportunités dans la watchlist
    - Gestion des symboles candidats
    """
    
    def __init__(self, data_manager: DataManager, logger=None):
        """
        Initialise le gestionnaire d'opportunités.
        
        Args:
            data_manager: Gestionnaire de données
            logger: Logger pour les messages (optionnel)
        """
        self.data_manager = data_manager
        self.logger = logger or setup_logging()
    
    def on_new_opportunity(
        self,
        linear_symbols: List[str],
        inverse_symbols: List[str],
        ws_manager,
        watchlist_manager: WatchlistManager
    ):
        """
        Callback appelé lors de nouvelles opportunités détectées.
        
        Args:
            linear_symbols: Nouveaux symboles linear
            inverse_symbols: Nouveaux symboles inverse
            ws_manager: Gestionnaire WebSocket
            watchlist_manager: Gestionnaire de watchlist
        """
        try:
            # Vérifier si le WebSocketManager est déjà en cours d'exécution
            if ws_manager.running:
                # Si déjà en cours, ne pas redémarrer, juste logger l'info
                self.logger.info(f"🎯 Nouvelles opportunités détectées: {len(linear_symbols)} linear, {len(inverse_symbols)} inverse (WebSocket déjà actif)")
            else:
                # Démarrer les connexions WebSocket pour les nouvelles opportunités
                ws_manager.start_connections(linear_symbols, inverse_symbols)
                self.logger.info(f"🎯 Nouvelles opportunités intégrées: {len(linear_symbols)} linear, {len(inverse_symbols)} inverse")
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur intégration nouvelles opportunités: {e}")
    
    def on_candidate_ticker(
        self,
        symbol: str,
        ticker_data: dict,
        watchlist_manager: WatchlistManager
    ):
        """
        Callback appelé pour les tickers des candidats.
        
        Args:
            symbol: Symbole candidat
            ticker_data: Données du ticker
            watchlist_manager: Gestionnaire de watchlist
        """
        try:
            # Ajouter le symbole à la watchlist principale
            self._add_symbol_to_main_watchlist(symbol, ticker_data, watchlist_manager)
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur traitement candidat {symbol}: {e}")
    
    def _add_symbol_to_main_watchlist(
        self,
        symbol: str,
        ticker_data: dict,
        watchlist_manager: WatchlistManager
    ):
        """
        Ajoute un symbole à la watchlist principale.
        
        Args:
            symbol: Symbole à ajouter
            ticker_data: Données du ticker
            watchlist_manager: Gestionnaire de watchlist
        """
        try:
            # Vérifier que le symbole n'est pas déjà dans la watchlist
            if self.data_manager.get_funding_data(symbol):
                return  # Déjà présent
            
            # Construire les données du symbole
            funding_rate = ticker_data.get("fundingRate")
            volume24h = ticker_data.get("volume24h")
            next_funding_time = ticker_data.get("nextFundingTime")
            
            if funding_rate is not None:
                funding = float(funding_rate)
                volume = float(volume24h) if volume24h is not None else 0.0
                funding_time_remaining = watchlist_manager.calculate_funding_time_remaining(next_funding_time)
                
                # Calculer le spread si disponible
                spread_pct = 0.0
                bid1_price = ticker_data.get("bid1Price")
                ask1_price = ticker_data.get("ask1Price")
                if bid1_price and ask1_price:
                    try:
                        bid = float(bid1_price)
                        ask = float(ask1_price)
                        if bid > 0 and ask > 0:
                            mid = (ask + bid) / 2
                            if mid > 0:
                                spread_pct = (ask - bid) / mid
                    except (ValueError, TypeError):
                        pass
                
                # Ajouter à la watchlist via le DataManager
                self.data_manager.update_funding_data(symbol, funding, volume, funding_time_remaining, spread_pct, None)
                
                # Ajouter aux listes par catégorie
                category = category_of_symbol(symbol, self.data_manager.symbol_categories)
                self.data_manager.add_symbol_to_category(symbol, category)
                
                # Mettre à jour les données originales
                if next_funding_time:
                    self.data_manager.update_original_funding_data(symbol, next_funding_time)
                
                self.logger.info(f"✅ Symbole {symbol} ajouté à la watchlist principale")
                
        except Exception as e:
            self.logger.error(f"❌ Erreur ajout symbole {symbol}: {e}")
