#!/usr/bin/env python3
"""
Gestionnaire des événements de position pour le bot Bybit.

Ce module gère tous les événements liés aux positions :
- Ouverture de positions
- Fermeture de positions
- Basculement WebSocket vers symbole unique
- Restauration de la watchlist complète

Responsabilité unique : Gestion des événements de position.
"""

import asyncio
import threading
from typing import Dict, Any, List, Optional, Callable
from logging_setup import setup_logging


class PositionEventHandler:
    """
    Gestionnaire des événements de position pour le bot Bybit.
    
    Responsabilités :
    - Gestion des callbacks d'ouverture/fermeture de positions
    - Basculement WebSocket vers symbole unique
    - Restauration de la watchlist complète
    - Coordination avec les managers concernés
    """

    def __init__(
        self,
        testnet: bool,
        logger=None,
        monitoring_manager=None,
        ws_manager=None,
        display_manager=None,
        data_manager=None,
        funding_close_manager=None,
    ):
        """
        Initialise le gestionnaire d'événements de position.
        
        Args:
            testnet: Utiliser le testnet (True) ou le marché réel (False)
            logger: Logger pour les messages (optionnel)
            monitoring_manager: Gestionnaire de monitoring (optionnel)
            ws_manager: Gestionnaire WebSocket (optionnel)
            display_manager: Gestionnaire d'affichage (optionnel)
            data_manager: Gestionnaire de données (optionnel)
            funding_close_manager: Gestionnaire de fermeture de funding (optionnel)
        """
        self.testnet = testnet
        self.logger = logger or setup_logging()
        
        # Références aux managers
        self.monitoring_manager = monitoring_manager
        self.ws_manager = ws_manager
        self.display_manager = display_manager
        self.data_manager = data_manager
        self.funding_close_manager = funding_close_manager

    def set_monitoring_manager(self, monitoring_manager):
        """Définit le gestionnaire de monitoring."""
        self.monitoring_manager = monitoring_manager

    def set_ws_manager(self, ws_manager):
        """Définit le gestionnaire WebSocket."""
        self.ws_manager = ws_manager

    def set_display_manager(self, display_manager):
        """Définit le gestionnaire d'affichage."""
        self.display_manager = display_manager

    def set_data_manager(self, data_manager):
        """Définit le gestionnaire de données."""
        self.data_manager = data_manager

    def set_funding_close_manager(self, funding_close_manager):
        """Définit le gestionnaire de fermeture de funding."""
        self.funding_close_manager = funding_close_manager

    def on_position_opened(self, symbol: str, position_data: Dict[str, Any]):
        """
        Callback appelé lors de l'ouverture d'une position.
        
        Args:
            symbol: Symbole de la position ouverte
            position_data: Données de la position
        """
        try:
            self.logger.info(f"📈 Position ouverte détectée: {symbol}")
            
            # Ajouter la position active
            if self.monitoring_manager:
                self.monitoring_manager.add_active_position(symbol)
            
            # Basculer vers le symbole unique seulement si c'est la première position
            if self.ws_manager and len(self.monitoring_manager.get_active_positions()) == 1:
                self._switch_to_single_symbol(symbol)
            
            # Filtrer l'affichage vers le symbole unique
            if self.display_manager:
                self.display_manager.set_symbol_filter({symbol})
            
            # Ajouter la position à la surveillance du funding
            if self.funding_close_manager:
                self.funding_close_manager.add_position_to_monitor(symbol)
            
            self.logger.info(f"⏸️ Watchlist en pause - Position ouverte sur {symbol}")
            
        except Exception as e:
            self.logger.error(f"❌ Erreur callback position ouverte: {e}")

    def on_position_closed(self, symbol: str, position_data: Dict[str, Any]):
        """
        Callback appelé lors de la fermeture d'une position.
        
        Args:
            symbol: Symbole de la position fermée
            position_data: Données de la position
        """
        try:
            self.logger.info(f"📉 Position fermée détectée: {symbol}")
            
            # Retirer la position active
            if self.monitoring_manager:
                self.monitoring_manager.remove_active_position(symbol)
            
            # Restaurer la watchlist complète seulement si plus de positions actives
            if (self.ws_manager and self.data_manager and 
                not self.monitoring_manager.has_active_positions()):
                self._restore_full_watchlist()
            
            # Restaurer l'affichage de tous les symboles
            if self.display_manager:
                self.display_manager.clear_symbol_filter()
            
            # Retirer la position de la surveillance du funding
            if self.funding_close_manager:
                self.funding_close_manager.remove_position_from_monitor(symbol)
            
            self.logger.info("▶️ Watchlist reprise - Position fermée")
            
        except Exception as e:
            self.logger.error(f"❌ Erreur callback position fermée: {e}")

    def _switch_to_single_symbol(self, symbol: str):
        """Bascule vers un symbole unique dans le WebSocket."""
        # Déterminer la catégorie du symbole
        category = "linear" if symbol.endswith("USDT") else "inverse"
        
        # Basculer vers le symbole unique (asynchrone)
        asyncio.create_task(
            self.ws_manager.switch_to_single_symbol(symbol, category)
        )

    def _restore_full_watchlist(self):
        """Restaure la watchlist complète dans le WebSocket."""
        linear_symbols = self.data_manager.storage.get_linear_symbols()
        inverse_symbols = self.data_manager.storage.get_inverse_symbols()
        
        # Restaurer la watchlist complète (synchrone)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Si on est dans un contexte async, utiliser create_task
                asyncio.create_task(
                    self.ws_manager.restore_full_watchlist(linear_symbols, inverse_symbols)
                )
            else:
                # Si on est dans un contexte sync, utiliser run
                loop.run_until_complete(
                    self.ws_manager.restore_full_watchlist(linear_symbols, inverse_symbols)
                )
        except RuntimeError:
            # Pas de loop event, créer un nouveau thread
            def run_async():
                asyncio.run(
                    self.ws_manager.restore_full_watchlist(linear_symbols, inverse_symbols)
                )
            thread = threading.Thread(target=run_async, daemon=True)
            thread.start()

    def remove_position_from_scheduler(self, symbol: str, scheduler):
        """
        Retire une position du scheduler.
        
        Args:
            symbol: Symbole de la position
            scheduler: Instance du scheduler
        """
        if scheduler:
            try:
                scheduler.remove_position(symbol)
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur retrait position du scheduler: {e}")

    def get_active_positions_count(self) -> int:
        """Retourne le nombre de positions actives."""
        if self.monitoring_manager:
            return len(self.monitoring_manager.get_active_positions())
        return 0

    def has_active_positions(self) -> bool:
        """Vérifie s'il y a des positions actives."""
        if self.monitoring_manager:
            return self.monitoring_manager.has_active_positions()
        return False
