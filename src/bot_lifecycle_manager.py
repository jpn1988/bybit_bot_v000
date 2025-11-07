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
from interfaces.lifecycle_manager_interface import LifecycleManagerInterface


class BotLifecycleManager(LifecycleManagerInterface):
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
        self.metrics_monitor = None

        # Callbacks
        self._on_funding_update_callback: Optional[Callable] = None
        self._summary_interval = 60
        self._last_summary_ts = 0.0

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

    def _log_periodic_summary(self, components: Dict[str, Any]):
        """Émet un résumé d'état toutes les 60 secondes."""
        now = time.time()
        if now - self._last_summary_ts < self._summary_interval:
            return

        self._last_summary_ts = now
        active_components = sum(1 for component in components.values() if component)
        uptime = int(self.get_uptime())
        self.logger.info(
            f"[LIFECYCLE] Summary uptime={uptime}s running={self.running} composants_actifs={active_components}"
        )

    async def start_lifecycle(self, components: Dict[str, Any]):
        """
        Démarre le cycle de vie du bot.

        Args:
            components: Dictionnaire des composants du bot
        """
        self.logger.info("[LIFECYCLE] Démarrage du cycle de vie du bot...")

        # Démarrer la tâche de mise à jour périodique des données de funding
        if self._on_funding_update_callback:
            self._funding_update_task = asyncio.create_task(
                self._periodic_funding_update()
            )

        # Démarrer le monitoring des métriques (centralisé)
        import metrics_monitor as metrics_module

        monitor = self.metrics_monitor or metrics_module.metrics_monitor

        if monitor and getattr(monitor, "running", False):
            self.logger.debug("✅ Moniteur de métriques déjà actif, réutilisation de l'instance existante")
        else:
            monitor = metrics_module.start_metrics_monitoring(interval_minutes=5)
            self.logger.info("[METRICS] MetricsMonitor started")

        self.metrics_monitor = monitor
        components["metrics_monitor"] = self.metrics_monitor

        self.logger.info("[LIFECYCLE] Cycle de vie du bot démarré")

    async def keep_bot_alive(self, components: Dict[str, Any]):
        """
        Maintient le bot en vie avec une boucle d'attente et monitoring mémoire.

        Args:
            components: Dictionnaire des composants du bot
        """
        self.logger.info("[LIFECYCLE] Bot opérationnel - surveillance continue...")
        self.logger.debug(f"🔍 État initial: running={self.running}, composants={len(components)}")

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
                        "[LIFECYCLE] ⚠️ Un composant critique s'est arrêté, redémarrage..."
                    )
                    # Optionnel: redémarrer les composants défaillants

                # Monitoring mémoire périodique
                if self._health_monitor and self._health_monitor.should_check_memory():
                    self._health_monitor.monitor_memory_usage()

                # Attendre avec vérification d'interruption
                self._log_periodic_summary(components)
                await asyncio.sleep(1.0)

        except asyncio.CancelledError:
            self.logger.info("[LIFECYCLE] Arrêt demandé par l'utilisateur")
            self.running = False
        except Exception as e:
            self.logger.error(f"[LIFECYCLE] ❌ Erreur dans la boucle principale: {e}")
            import traceback
            traceback.print_exc()
            self.running = False

    async def stop_lifecycle(self, components: Dict[str, Any]):
        """
        Arrête le cycle de vie du bot.

        Args:
            components: Dictionnaire des composants du bot
        """
        self.logger.info("[LIFECYCLE] Arrêt du cycle de vie du bot...")
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
                await self._shutdown_manager.stop_all(managers)

                self.logger.info("[LIFECYCLE] Cycle de vie arrêté proprement via ShutdownManager")

            except Exception as e:
                self.logger.error(f"[LIFECYCLE] ❌ Erreur lors de l'arrêt: {e}")

        # Nettoyer la référence au moniteur de métriques
        self.metrics_monitor = None

    async def _periodic_funding_update(self):
        """Met à jour périodiquement les données de funding via l'API REST."""
        self.logger.debug("🔄 Tâche de mise à jour périodique des funding démarrée")

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
                self.logger.debug("🛑 Tâche de mise à jour des funding annulée")
                break
            except Exception as e:
                self.logger.error(f"[FUNDING] ❌ Erreur mise à jour périodique des funding: {e}")
                # Continuer même en cas d'erreur
                await asyncio.sleep(10)  # Attendre un peu avant de réessayer

    def get_uptime(self) -> float:
        """Retourne le temps de fonctionnement en secondes."""
        return time.time() - self.start_time

    def is_running(self) -> bool:
        """Vérifie si le bot est en cours d'exécution."""
        return self.running

    def get_metrics_monitor(self):
        """Retourne l'instance du moniteur de métriques active."""
        return self.metrics_monitor

    def stop(self):
        """Arrête le bot de manière synchrone."""
        self.running = False
