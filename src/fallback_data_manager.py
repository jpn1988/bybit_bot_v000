#!/usr/bin/env python3
"""
Gestionnaire de fallback des données pour le bot Bybit.

Ce module gère la logique de fallback des données :
- Récupération des données de funding via API REST
- Filtrage des données pour la watchlist
- Mise à jour des données de funding
- Gestion des données originales

Responsabilité unique : Gestion du fallback des données REST.
"""

from typing import Dict, Any, Optional, Callable
from logging_setup import setup_logging
from config.urls import URLConfig
from interfaces.fallback_data_manager_interface import FallbackDataManagerInterface


class FallbackDataManager(FallbackDataManagerInterface):
    """
    Gestionnaire de fallback des données pour le bot Bybit.

    Responsabilités :
    - Récupération des données de funding via API REST
    - Filtrage des données pour la watchlist
    - Mise à jour des données de funding
    - Gestion des données originales
    """

    def __init__(
        self,
        testnet: bool,
        logger=None,
        data_manager=None,
        watchlist_manager=None,
    ):
        """
        Initialise le gestionnaire de fallback des données.

        Args:
            testnet: Utiliser le testnet (True) ou le marché réel (False)
            logger: Logger pour les messages (optionnel)
            data_manager: Gestionnaire de données (optionnel)
            watchlist_manager: Gestionnaire de watchlist (optionnel)
        """
        self.testnet = testnet
        self.logger = logger or setup_logging()
        self.data_manager = data_manager
        self.watchlist_manager = watchlist_manager

    def set_data_manager(self, data_manager):
        """Définit le gestionnaire de données."""
        self.data_manager = data_manager

    def set_watchlist_manager(self, watchlist_manager):
        """Définit le gestionnaire de watchlist."""
        self.watchlist_manager = watchlist_manager

    async def update_funding_data_periodically(self):
        """
        Met à jour périodiquement les données de funding via l'API REST.

        Cette méthode est appelée par le BotLifecycleManager.
        """
        try:
            self.logger.debug("🔄 Mise à jour périodique des données de funding...")

            # Récupérer les données de funding via l'API REST (version async)
            base_url = URLConfig.get_api_url(self.testnet)
            funding_data = await self.data_manager.fetcher.fetch_funding_map_async(base_url, "linear", 10)

            if funding_data:
                filtered_funding_data = self._filter_funding_data_for_watchlist(funding_data)

                if filtered_funding_data:
                    self.data_manager._update_funding_data(filtered_funding_data)
                    if self.watchlist_manager:
                        self.data_manager._update_original_funding_data(self.watchlist_manager)
                    self.logger.debug(f"✅ Données de funding mises à jour: {len(filtered_funding_data)} symboles")
                else:
                    self.logger.debug("⚠️ Aucun symbole de la watchlist trouvé dans les données de funding")
            else:
                self.logger.warning("⚠️ Aucune donnée de funding récupérée")

        except Exception as e:
            self.logger.error(f"❌ Erreur mise à jour périodique des funding: {e}")

    def _filter_funding_data_for_watchlist(self, funding_data: Dict) -> Dict:
        """
        Filtre les données de funding pour ne garder que les symboles de la watchlist.

        Args:
            funding_data: Données de funding complètes

        Returns:
            Dict: Données filtrées
        """
        if not self.watchlist_manager:
            return funding_data

        watchlist_symbols = set(self.watchlist_manager.get_selected_symbols())
        return {
            symbol: data for symbol, data in funding_data.items()
            if symbol in watchlist_symbols
        }

    def get_funding_data_for_scheduler(self) -> Dict[str, Dict[str, Any]]:
        """
        Récupère les données de funding formatées pour le Scheduler.
        Calcule dynamiquement le temps restant à partir des timestamps temps réel.

        Returns:
            Dict avec les données de funding formatées pour chaque symbole
        """
        funding_data = {}
        if not self.watchlist_manager:
            return funding_data

        selected_symbols = self.watchlist_manager.get_selected_symbols()
        self.logger.debug(f"[SCHEDULER] Symboles sélectionnés: {len(selected_symbols)}")

        for symbol in selected_symbols:
            funding_info = self._get_symbol_funding_data(symbol)
            if funding_info:
                funding_data[symbol] = funding_info

        self.logger.debug(f"[SCHEDULER] Données récupérées: {len(funding_data)} symboles")
        return funding_data

    def _get_symbol_funding_data(self, symbol: str) -> Dict[str, Any]:
        """Récupère les données de funding pour un symbole spécifique."""
        # Récupérer les données temps réel (mises à jour via WebSocket)
        realtime_info = self.data_manager.storage.get_realtime_data(symbol)

        if realtime_info and realtime_info.get("next_funding_time"):
            # Calculer le temps restant à partir du timestamp temps réel
            next_funding_timestamp = realtime_info["next_funding_time"]
            funding_time_str = self.watchlist_manager.calculate_funding_time_remaining(next_funding_timestamp)

            funding_data = {
                'next_funding_time': funding_time_str,  # Recalculé dynamiquement
                'funding_rate': realtime_info.get('funding_rate'),
                'volume_24h': realtime_info.get('volume24h')
            }
            self.logger.debug(f"[SCHEDULER] {symbol}: {funding_time_str} (temps réel)")
            return funding_data
        else:
            # Fallback sur les données originales si pas de données temps réel
            return self._get_fallback_funding_data(symbol)

    def _get_fallback_funding_data(self, symbol: str) -> Dict[str, Any]:
        """Récupère les données de funding en fallback depuis les données originales."""
        funding_obj = self.data_manager.storage.get_funding_data_object(symbol)
        if funding_obj:
            original_timestamp = self.data_manager.storage.get_original_funding_data(symbol)
            if original_timestamp:
                funding_time_str = self.watchlist_manager.calculate_funding_time_remaining(original_timestamp)
            else:
                funding_time_str = funding_obj.next_funding_time

            funding_data = {
                'next_funding_time': funding_time_str,
                'funding_rate': funding_obj.funding_rate,
                'volume_24h': funding_obj.volume_24h
            }
            self.logger.debug(f"[SCHEDULER] {symbol}: {funding_time_str} (fallback)")
            return funding_data
        else:
            self.logger.debug(f"[SCHEDULER] Aucune donnée pour {symbol}")
            return None

    def update_funding_data_from_dict(self, funding_data: Dict):
        """
        Met à jour les données de funding depuis un dictionnaire externe.

        Args:
            funding_data: Dictionnaire des données de funding à mettre à jour
        """
        if self.data_manager:
            self.data_manager.update_funding_data_from_dict(funding_data)

    def get_fallback_summary(self) -> Dict[str, Any]:
        """
        Retourne un résumé du fallback des données.

        Returns:
            Dict contenant les statistiques du fallback
        """
        return {
            "testnet": self.testnet,
            "data_manager_available": self.data_manager is not None,
            "watchlist_manager_available": self.watchlist_manager is not None,
            "selected_symbols_count": len(self.watchlist_manager.get_selected_symbols()) if self.watchlist_manager else 0,
        }
