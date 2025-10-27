#!/usr/bin/env python3
"""
Gestionnaire du cycle de vie du bot Bybit.

Ce module gère le cycle de vie complet du bot :
- Initialisation des composants
- Démarrage et arrêt
- Gestion des tâches asynchrones
- Monitoring de santé

Responsabilité unique : Gestion du cycle de vie du bot.
"""

import asyncio
import time
from typing import Dict, Any, Optional, Callable
from logging_setup import setup_logging
from config.constants import DEFAULT_FUNDING_UPDATE_INTERVAL
from config.urls import URLConfig


class BotLifecycleManager:
    """
    Gestionnaire du cycle de vie du bot Bybit.
    
    Responsabilités :
    - Initialisation des composants
    - Démarrage et arrêt du bot
    - Gestion des tâches asynchrones
    - Monitoring de santé
    """

    def __init__(
        self,
        testnet: bool,
        logger=None,
        health_monitor=None,
        shutdown_manager=None,
        thread_manager=None,
    ):
        """
        Initialise le gestionnaire du cycle de vie.
        
        Args:
            testnet: Utiliser le testnet (True) ou le marché réel (False)
            logger: Logger pour les messages (optionnel)
            health_monitor: Moniteur de santé (optionnel)
            shutdown_manager: Gestionnaire d'arrêt (optionnel)
            thread_manager: Gestionnaire de threads (optionnel)
        """
        self.testnet = testnet
        self.logger = logger or setup_logging()
        self.running = True
        self.start_time = time.time()
        
        # Composants de cycle de vie
        self._health_monitor = health_monitor
        self._shutdown_manager = shutdown_manager
        self._thread_manager = thread_manager
        
        # Tâches asynchrones
        self._funding_update_task: Optional[asyncio.Task] = None
        
        # Callbacks
        self._on_funding_update_callback: Optional[Callable] = None

    def set_health_monitor(self, health_monitor):
        """Définit le moniteur de santé."""
        self._health_monitor = health_monitor

    def set_shutdown_manager(self, shutdown_manager):
        """Définit le gestionnaire d'arrêt."""
        self._shutdown_manager = shutdown_manager

    def set_thread_manager(self, thread_manager):
        """Définit le gestionnaire de threads."""
        self._thread_manager = thread_manager

    def set_on_funding_update_callback(self, callback: Callable):
        """Définit le callback pour la mise à jour des funding."""
        self._on_funding_update_callback = callback

    async def start_lifecycle(self, components: Dict[str, Any]):
        """
        Démarre le cycle de vie du bot.
        
        Args:
            components: Dictionnaire des composants du bot
        """
        self.logger.info("🔄 Démarrage du cycle de vie du bot...")
        
        # Démarrer la tâche de mise à jour périodique des données de funding
        if self._on_funding_update_callback:
            self._funding_update_task = asyncio.create_task(
                self._periodic_funding_update()
            )
        
        # Démarrer le monitoring des métriques
        from metrics_monitor import start_metrics_monitoring
        start_metrics_monitoring(interval_minutes=5)
        
        self.logger.info("✅ Cycle de vie du bot démarré")

    async def keep_bot_alive(self, components: Dict[str, Any]):
        """
        Maintient le bot en vie avec une boucle d'attente et monitoring mémoire.
        
        Args:
            components: Dictionnaire des composants du bot
        """
        self.logger.info("🔄 Bot opérationnel - surveillance continue...")
        self.logger.info(f"🔍 État initial: running={self.running}, composants={len(components)}")

        try:
            while self.running:
                self.logger.debug(f"🔄 Boucle de surveillance active (running={self.running})")
                # Vérifier que tous les composants principaux sont toujours actifs
                if self._health_monitor and not self._health_monitor.check_components_health(
                    components.get("monitoring_manager"),
                    components.get("display_manager"),
                    components.get("volatility_tracker"),
                ):
                    self.logger.warning(
                        "⚠️ Un composant critique s'est arrêté, redémarrage..."
                    )
                    # Optionnel: redémarrer les composants défaillants

                # Monitoring mémoire périodique
                if self._health_monitor and self._health_monitor.should_check_memory():
                    self._health_monitor.monitor_memory_usage()

                # Attendre avec vérification d'interruption
                await asyncio.sleep(1.0)

        except asyncio.CancelledError:
            self.logger.info("🛑 Arrêt demandé par l'utilisateur")
            self.running = False
        except Exception as e:
            self.logger.error(f"❌ Erreur dans la boucle principale: {e}")
            import traceback
            traceback.print_exc()
            self.running = False

    async def stop_lifecycle(self, components: Dict[str, Any]):
        """
        Arrête le cycle de vie du bot.
        
        Args:
            components: Dictionnaire des composants du bot
        """
        self.logger.info("🛑 Arrêt du cycle de vie du bot...")
        self.running = False

        # Annuler la tâche de mise à jour des funding
        if self._funding_update_task and not self._funding_update_task.done():
            self._funding_update_task.cancel()
            try:
                await self._funding_update_task
            except asyncio.CancelledError:
                pass

        # Utiliser ShutdownManager pour l'arrêt centralisé
        if self._shutdown_manager:
            try:
                # Préparer le dictionnaire des managers pour ShutdownManager
                managers = {
                    "monitoring_manager": components.get("monitoring_manager"),
                    "display_manager": components.get("display_manager"),
                    "ws_manager": components.get("ws_manager"),
                    "volatility_tracker": components.get("volatility_tracker"),
                    "metrics_monitor": components.get("metrics_monitor"),
                }

                # Utiliser ShutdownManager pour l'arrêt asynchrone
                await self._shutdown_manager.stop_all_managers_async(managers)

                self.logger.info("✅ Cycle de vie arrêté proprement via ShutdownManager")

            except Exception as e:
                self.logger.error(f"❌ Erreur lors de l'arrêt: {e}")

    async def _periodic_funding_update(self):
        """Met à jour périodiquement les données de funding via l'API REST."""
        self.logger.info("🔄 Tâche de mise à jour périodique des funding démarrée")
        
        while self.running:
            try:
                # Attendre selon l'intervalle configuré
                await asyncio.sleep(DEFAULT_FUNDING_UPDATE_INTERVAL)
                
                if not self.running:
                    break
                
                self.logger.debug("🔄 Mise à jour périodique des données de funding...")
                
                # Appeler le callback de mise à jour
                if self._on_funding_update_callback:
                    await self._on_funding_update_callback()
                    
            except asyncio.CancelledError:
                self.logger.info("🛑 Tâche de mise à jour des funding annulée")
                break
            except Exception as e:
                self.logger.error(f"❌ Erreur mise à jour périodique des funding: {e}")
                # Continuer même en cas d'erreur
                await asyncio.sleep(10)  # Attendre un peu avant de réessayer

    def get_uptime(self) -> float:
        """Retourne le temps de fonctionnement en secondes."""
        return time.time() - self.start_time

    def is_running(self) -> bool:
        """Vérifie si le bot est en cours d'exécution."""
        return self.running

    def stop(self):
        """Arrête le bot de manière synchrone."""
        self.running = False
