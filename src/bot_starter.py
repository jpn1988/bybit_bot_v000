#!/usr/bin/env python3
"""
Démarreur du bot Bybit - Version refactorisée.

🎯 RESPONSABILITÉ : Démarrer tous les composants du bot

Cette classe est appelée au démarrage par BotOrchestrator pour lancer
tous les composants actifs (WebSocket, monitoring, affichage, etc.).

📝 CE QUE FAIT CE FICHIER :
1. display_startup_summary() : Affiche le résumé de démarrage
   - Filtres appliqués (funding, volume, spread, volatilité)
   - Nombre de symboles sélectionnés
   - Statistiques des données chargées

2. start_bot_components() : Démarre tous les composants en parallèle
   - Démarre volatility_tracker (refresh automatique)
   - Démarre display_manager (affichage du tableau)
   - Démarre ws_manager (connexions WebSocket)
   - Démarre monitoring_manager (surveillance des opportunités)
   
   ⚠️ IMPORTANT : Cette méthode est ASYNCHRONE (await)

3. get_startup_stats() : Retourne les stats de démarrage
   - Nombre de symboles linear/inverse
   - Volume total, funding moyen, etc.

🔗 APPELÉ PAR : bot.py (BotOrchestrator.start(), lignes 147-160)

📚 POUR EN SAVOIR PLUS : Consultez GUIDE_DEMARRAGE_BOT.md
"""

import time
from typing import Dict, Any
from logging_setup import setup_logging
from volatility_tracker import VolatilityTracker
from display_manager import DisplayManager
from ws_manager import WebSocketManager
from data_manager import DataManager
from monitoring_manager import MonitoringManager


class BotStarter:
    """
    Démarreur du bot Bybit.

    Responsabilités :
    - Démarrage des composants du bot
    - Configuration de la surveillance
    - Gestion du résumé de démarrage
    """

    def __init__(self, testnet: bool, logger=None):
        """
        Initialise le démarreur du bot.

        Args:
            testnet: Utiliser le testnet (True) ou le marché réel (False)
            logger: Logger pour les messages (optionnel)
        """
        self.testnet = testnet
        self.logger = logger or setup_logging()

    async def start_bot_components(
        self,
        volatility_tracker: VolatilityTracker,
        display_manager: DisplayManager,
        ws_manager: WebSocketManager,
        data_manager: DataManager,
        monitoring_manager: MonitoringManager,
        base_url: str,
        perp_data: Dict,
    ):
        """
        Démarre tous les composants du bot.

        Args:
            volatility_tracker: Tracker de volatilité
            display_manager: Gestionnaire d'affichage
            ws_manager: Gestionnaire WebSocket
            data_manager: Gestionnaire de données
            monitoring_manager: Gestionnaire de surveillance
            base_url: URL de base de l'API
            perp_data: Données des perpétuels
        """
        try:
            # Démarrer le tracker de volatilité (arrière-plan)
            self._start_volatility_tracker(volatility_tracker)

            # Démarrer l'affichage
            await self._start_display_manager(display_manager)

            # Démarrer les connexions WebSocket
            await self._start_websocket_connections(ws_manager, data_manager)

            # Vérifier les positions existantes au démarrage
            await self._check_existing_positions(monitoring_manager)

            # Configurer la surveillance des candidats
            self._setup_candidate_monitoring(
                monitoring_manager, base_url, perp_data
            )

            # Démarrer le mode surveillance continue
            await self._start_continuous_monitoring(
                monitoring_manager, base_url, perp_data
            )

        except Exception as e:
            self.logger.error(f"❌ Erreur démarrage composants: {e}")
            raise

    def _start_volatility_tracker(self, volatility_tracker: VolatilityTracker):
        """Démarre le tracker de volatilité."""
        volatility_tracker.start_refresh_task()

    async def _check_existing_positions(self, monitoring_manager: MonitoringManager):
        """
        Vérifie les positions existantes au démarrage.
        
        Args:
            monitoring_manager: Gestionnaire de surveillance
        """
        try:
            self.logger.info("🔍 Vérification des positions existantes au démarrage...")
            
            # Vérifier si le monitoring_manager a un bybit_client
            if hasattr(monitoring_manager, 'bybit_client') and monitoring_manager.bybit_client:
                # Récupérer les positions existantes
                positions = monitoring_manager.bybit_client.get_positions(category="linear", settleCoin="USDT")
                
                if positions and positions.get("result", {}).get("list"):
                    existing_positions = positions["result"]["list"]
                    active_positions = [pos for pos in existing_positions if float(pos.get("size", 0)) > 0]
                    
                    if active_positions:
                        self.logger.info(f"📈 {len(active_positions)} position(s) existante(s) détectée(s) au démarrage:")
                        for pos in active_positions:
                            symbol = pos.get("symbol", "N/A")
                            size = pos.get("size", "0")
                            side = pos.get("side", "N/A")
                            self.logger.info(f"   - {symbol}: {side} {size}")
                        
                        # Notifier le monitoring_manager des positions existantes
                        if hasattr(monitoring_manager, 'handle_existing_positions'):
                            await monitoring_manager.handle_existing_positions(active_positions)
                    else:
                        self.logger.info("ℹ️ Aucune position active détectée au démarrage")
                else:
                    self.logger.info("ℹ️ Aucune position trouvée au démarrage")
            else:
                self.logger.warning("⚠️ Impossible de vérifier les positions - bybit_client non disponible")
                
        except Exception as e:
            self.logger.error(f"❌ Erreur vérification positions existantes: {e}")
            # Ne pas faire échouer le démarrage pour cette erreur

    async def _start_display_manager(self, display_manager: DisplayManager):
        """Démarre le gestionnaire d'affichage."""
        await display_manager.start_display_loop()

    async def _start_websocket_connections(
        self, ws_manager: WebSocketManager, data_manager: DataManager
    ):
        """Démarre les connexions WebSocket."""
        linear_symbols = data_manager.storage.get_linear_symbols()
        inverse_symbols = data_manager.storage.get_inverse_symbols()

        if linear_symbols or inverse_symbols:
            await ws_manager.start_connections(linear_symbols, inverse_symbols)

    def _setup_candidate_monitoring(
        self,
        monitoring_manager: MonitoringManager,
        base_url: str,
        perp_data: Dict,
    ):
        """Configure la surveillance des candidats - délégation directe à
        MonitoringManager."""
        monitoring_manager.setup_candidate_monitoring(base_url, perp_data)

    async def _start_continuous_monitoring(
        self,
        monitoring_manager: MonitoringManager,
        base_url: str,
        perp_data: Dict,
    ):
        """Démarre la surveillance continue."""
        await monitoring_manager.start_continuous_monitoring(
            base_url, perp_data
        )

    def display_startup_summary(
        self, config: Dict, perp_data: Dict, data_manager: DataManager
    ):
        """
        Affiche le résumé de démarrage structuré.

        Args:
            config: Configuration du bot
            perp_data: Données des perpétuels
            data_manager: Gestionnaire de données
        """
        # Informations du bot
        bot_info = {
            "name": "BYBIT BOT",
            "version": "0.9.0",
            "environment": "Testnet" if self.testnet else "Mainnet",
            "mode": "Funding Sniping",
        }

        # Statistiques de filtrage
        total_symbols = perp_data.get("total", 0)
        linear_count = len(data_manager.storage.get_linear_symbols())
        inverse_count = len(data_manager.storage.get_inverse_symbols())
        final_count = linear_count + inverse_count

        filter_results = {
            "stats": {
                "total_symbols": total_symbols,
                "after_funding_volume": final_count,
                "after_spread": final_count,
                "after_volatility": final_count,
                "final_count": final_count,
            }
        }

        # Statut WebSocket
        ws_status = {
            "connected": bool(linear_count or inverse_count),
            "symbols_count": final_count,
            "category": config.get("categorie", "linear"),
        }

        # Ajouter l'intervalle de métriques à la config
        config["metrics_interval"] = 5

        # Afficher un résumé simple
        self.logger.info("✅ Initialisation terminée - Bot opérationnel")

    def get_startup_stats(
        self, data_manager: DataManager
    ) -> Dict[str, Any]:
        """
        Retourne les statistiques de démarrage.

        Args:
            data_manager: Gestionnaire de données

        Returns:
            Dictionnaire contenant les statistiques
        """
        linear_symbols = data_manager.storage.get_linear_symbols()
        inverse_symbols = data_manager.storage.get_inverse_symbols()

        return {
            "linear_count": len(linear_symbols),
            "inverse_count": len(inverse_symbols),
            "total_symbols": len(linear_symbols) + len(inverse_symbols),
            "startup_time": time.time(),
        }
