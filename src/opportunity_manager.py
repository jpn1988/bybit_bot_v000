#!/usr/bin/env python3
"""
Gestionnaire d'opportunités pour le bot Bybit - Version refactorisée.

Cette classe coordonne les composants spécialisés :
- OpportunityScanner : Détection des nouvelles opportunités
- OpportunityIntegrator : Intégration dans la watchlist
- Gestion des callbacks et notifications

Responsabilité unique : Coordination entre les composants d'opportunités.
"""

import asyncio
from typing import List, Dict, Optional, Callable
from logging_setup import setup_logging
from data_manager import DataManager
from watchlist_manager import WatchlistManager
from volatility_tracker import VolatilityTracker
from opportunity_scanner import OpportunityScanner
from opportunity_integrator import OpportunityIntegrator


class OpportunityManager:
    """
    Gestionnaire d'opportunités pour le bot Bybit - Version refactorisée.

    Cette classe coordonne les composants spécialisés :
    - OpportunityScanner : Détection des nouvelles opportunités
    - OpportunityIntegrator : Intégration dans la watchlist
    - Gestion des callbacks et notifications

    Responsabilité unique : Coordination entre les composants d'opportunités.
    """

    def __init__(
        self,
        data_manager: DataManager,
        watchlist_manager: WatchlistManager = None,
        volatility_tracker: VolatilityTracker = None,
        testnet: bool = True,
        logger=None,
    ):
        """
        Initialise le gestionnaire d'opportunités.

        Args:
            data_manager: Gestionnaire de données
            watchlist_manager: Gestionnaire de watchlist (optionnel)
            volatility_tracker: Tracker de volatilité (optionnel)
            testnet: Utiliser le testnet (True) ou le marché réel (False)
            logger: Logger pour les messages (optionnel)
        """
        self.data_manager = data_manager
        self.watchlist_manager = watchlist_manager
        self.volatility_tracker = volatility_tracker
        self.testnet = testnet
        self.logger = logger or setup_logging()

        # Référence au WebSocket pour optimisation
        self.ws_manager = None

        # Callback pour les nouvelles opportunités
        self._on_new_opportunity_callback: Optional[Callable] = None

        # Initialiser les composants spécialisés
        self._initialize_components()

    def _initialize_components(self):
        """Initialise les composants spécialisés."""
        self.scanner = OpportunityScanner(
            watchlist_manager=self.watchlist_manager,
            volatility_tracker=self.volatility_tracker,
            testnet=self.testnet,
            logger=self.logger,
        )

        self.integrator = OpportunityIntegrator(
            data_manager=self.data_manager,
            watchlist_manager=self.watchlist_manager,
            logger=self.logger,
        )

    # ===== MÉTHODES DE CONFIGURATION =====

    def set_ws_manager(self, ws_manager):
        """
        Définit le gestionnaire WebSocket principal.

        Args:
            ws_manager: Gestionnaire WebSocket principal
        """
        self.ws_manager = ws_manager
        # Transférer au scanner pour optimisation
        self.scanner.set_ws_manager(ws_manager)

    def set_on_new_opportunity_callback(self, callback: Callable):
        """
        Définit le callback pour les nouvelles opportunités.

        Args:
            callback: Fonction à appeler lors de nouvelles opportunités
        """
        self._on_new_opportunity_callback = callback
        # Transférer à l'intégrateur
        self.integrator.set_on_new_opportunity_callback(callback)

    # ===== MÉTHODES DE SCAN ET DÉTECTION =====

    def scan_for_opportunities(
        self, base_url: str, perp_data: Dict
    ) -> Optional[Dict]:
        """
        Scanne le marché pour trouver de nouvelles opportunités.

        Délègue au composant OpportunityScanner spécialisé.

        Args:
            base_url: URL de base de l'API
            perp_data: Données des perpétuels

        Returns:
            Dict avec les opportunités trouvées ou None
        """
        return self.scanner.scan_for_opportunities(base_url, perp_data)

    def integrate_opportunities(self, opportunities: Dict):
        """
        Intègre les nouvelles opportunités détectées.

        Délègue au composant OpportunityIntegrator spécialisé.

        Args:
            opportunities: Dict avec les opportunités à intégrer
        """
        self.integrator.integrate_opportunities(opportunities)

    # ===== MÉTHODES DE GESTION DES OPPORTUNITÉS =====

    def on_new_opportunity(
        self,
        linear_symbols: List[str],
        inverse_symbols: List[str],
        ws_manager,
        watchlist_manager: WatchlistManager,
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
                # Le WebSocket est déjà actif et gère automatiquement
                # tous les symboles via ses souscriptions existantes
                self.logger.info(
                    f"🎯 Nouvelles opportunités détectées: "
                    f"{len(linear_symbols)} linear, {len(inverse_symbols)} inverse "
                    f"(WebSocket déjà actif)"
                )
            else:
                # CORRECTIF ARCH-001: Utiliser create_task avec gestion d'exceptions
                import asyncio
                try:
                    # Essayer d'obtenir la boucle actuelle et créer une tâche
                    loop = asyncio.get_running_loop()
                    task = loop.create_task(
                        self.start_websocket_connections_async(
                            ws_manager, linear_symbols, inverse_symbols
                        )
                    )
                    # CORRECTIF: Ajouter un callback pour gérer les exceptions
                    task.add_done_callback(self._handle_task_exception)
                    self.logger.info(
                        f"🎯 Nouvelles opportunités intégrées: "
                        f"{len(linear_symbols)} linear, {len(inverse_symbols)} inverse"
                    )
                except RuntimeError:
                    # Pas de loop en cours = contexte synchrone, logger un warning
                    self.logger.warning(
                        "⚠️ ARCH-001: Impossible de démarrer WebSocket depuis contexte sync.\n"
                        "Nouvelles opportunités détectées mais WebSocket non démarré.\n"
                        "Utilisez on_new_opportunity_async() depuis un contexte await."
                    )
        except Exception as e:
            self.logger.warning(
                f"⚠️ Erreur intégration nouvelles opportunités: {e}"
            )

    async def on_new_opportunity_async(
        self,
        linear_symbols: List[str],
        inverse_symbols: List[str],
        ws_manager,
        watchlist_manager: WatchlistManager,
    ):
        """
        Version async pure pour nouvelles opportunités.
        
        CORRECTIF ARCH-001: Cette méthode utilise async/await pur sans
        tentatives de création d'event loops imbriquées.

        Args:
            linear_symbols: Nouveaux symboles linear
            inverse_symbols: Nouveaux symboles inverse
            ws_manager: Gestionnaire WebSocket
            watchlist_manager: Gestionnaire de watchlist
        """
        try:
            if ws_manager.running:
                self.logger.info(
                    f"🎯 Nouvelles opportunités détectées: "
                    f"{len(linear_symbols)} linear, {len(inverse_symbols)} inverse "
                    f"(WebSocket déjà actif)"
                )
            else:
                # Démarrer WebSocket avec await (contexte async garanti)
                await self.start_websocket_connections_async(
                    ws_manager, linear_symbols, inverse_symbols
                )
                self.logger.info(
                    f"🎯 Nouvelles opportunités intégrées: "
                    f"{len(linear_symbols)} linear, {len(inverse_symbols)} inverse"
                )
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur intégration opportunités: {e}")

    def _handle_task_exception(self, task):
        """
        Gère les exceptions des tâches asyncio.
        
        CORRECTIF : Capture les erreurs des tâches fire-and-forget
        pour éviter les erreurs silencieuses.

        Args:
            task: Tâche asyncio terminée
        """
        try:
            # Récupérer le résultat de la tâche
            # Cela lèvera l'exception si la tâche a échoué
            task.result()
        except asyncio.CancelledError:
            # Annulation normale, pas d'erreur
            self.logger.debug("🔄 Tâche WebSocket annulée normalement")
        except Exception as e:
            # Capturer et logger toute exception avec contexte
            self.logger.error(
                f"❌ Erreur critique dans la tâche WebSocket: {e}\n"
                f"   Type: {type(e).__name__}\n"
                f"   Tâche: {task.get_name() if hasattr(task, 'get_name') else 'Unknown'}",
                exc_info=True
            )
            # Optionnel: Notifier un système de monitoring externe
            # self._notify_monitoring_system(e)

    async def start_websocket_connections_async(
        self, ws_manager, linear_symbols: List[str], inverse_symbols: List[str]
    ):
        """
        Version async pure pour démarrer les connexions WebSocket.
        
        Args:
            ws_manager: Gestionnaire WebSocket
            linear_symbols: Symboles linear à surveiller
            inverse_symbols: Symboles inverse à surveiller
            
        Returns:
            asyncio.Task: Tâche créée pour les connexions WebSocket
        """
        import asyncio
        
        task = asyncio.create_task(
            ws_manager.start_connections(linear_symbols, inverse_symbols)
        )
        task.add_done_callback(self._handle_task_exception)
        return task


    def on_candidate_ticker(
        self,
        symbol: str,
        ticker_data: dict,
        watchlist_manager: WatchlistManager,
    ):
        """
        Callback appelé pour les tickers des candidats.

        Délègue au composant OpportunityIntegrator spécialisé.

        Args:
            symbol: Symbole candidat
            ticker_data: Données du ticker
            watchlist_manager: Gestionnaire de watchlist
        """
        self.integrator.add_symbol_to_watchlist(
            symbol, ticker_data, watchlist_manager
        )

