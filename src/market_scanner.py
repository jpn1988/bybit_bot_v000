#!/usr/bin/env python3
"""
Scanner de marché pour le bot Bybit.

Cette classe est responsable uniquement du scan périodique du marché
pour détecter de nouvelles opportunités.
"""

import asyncio
import time
from typing import Optional, Callable, Dict
from logging_setup import setup_logging
from config.timeouts import ScanIntervalConfig


class MarketScanner:
    """
    Scanner de marché pour détecter périodiquement de nouvelles opportunités.
    
    Responsabilité unique : Gérer le cycle de scan périodique du marché.
    """

    def __init__(self, scan_interval: int = None, logger=None):
        """
        Initialise le scanner de marché.

        Args:
            scan_interval: Intervalle entre chaque scan en secondes 
            (utilise ScanIntervalConfig.MARKET_SCAN par défaut)
            logger: Logger pour les messages (optionnel)
        """
        self.logger = logger or setup_logging()
        self._scan_interval = scan_interval if scan_interval is not None else ScanIntervalConfig.MARKET_SCAN
        self._scan_running = False
        self._scan_task: Optional[asyncio.Task] = None
        self._last_scan_time = 0
        
        # Callback pour effectuer le scan
        self._scan_callback: Optional[Callable] = None

    def set_scan_callback(self, callback: Callable):
        """
        Définit le callback à appeler lors de chaque scan.
        
        Le callback doit être une fonction asynchrone qui prend
        les paramètres (base_url, perp_data) et retourne les opportunités trouvées.

        Args:
            callback: Fonction asynchrone de scan
        """
        self._scan_callback = callback

    async def start_scanning(self, base_url: str, perp_data: Dict):
        """
        Démarre le scan périodique du marché.

        Args:
            base_url: URL de base de l'API Bybit
            perp_data: Données des perpétuels
        """
        if self._scan_task and not self._scan_task.done():
            self.logger.warning("⚠️ Scan du marché déjà actif")
            return

        self._scan_running = True
        self._scan_task = asyncio.create_task(
            self._scanning_loop(base_url, perp_data)
        )
        self.logger.info("🔍 Scanner de marché démarré")

    async def stop_scanning(self):
        """Arrête le scan périodique du marché."""
        if not self._scan_running:
            return

        self._scan_running = False

        # Annuler la tâche de surveillance
        if self._scan_task and not self._scan_task.done():
            try:
                self._scan_task.cancel()
                try:
                    await asyncio.wait_for(self._scan_task, timeout=3.0)
                except asyncio.TimeoutError:
                    self.logger.warning(
                        "⚠️ Tâche scan n'a pas pu être annulée dans les temps"
                    )
                except asyncio.CancelledError:
                    pass  # Annulation normale
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur annulation tâche scan: {e}")

        self._scan_task = None
        self.logger.info("🔍 Scanner de marché arrêté")

    async def _scanning_loop(self, base_url: str, perp_data: Dict):
        """Boucle de surveillance périodique asynchrone."""
        while self._scan_running:
            try:
                # Vérification immédiate pour arrêt rapide
                if not self._scan_running:
                    self.logger.info("🛑 Arrêt du scanner demandé")
                    break

                current_time = time.time()

                # Effectuer un scan si l'intervalle est écoulé
                if self._should_perform_scan(current_time):
                    await self._perform_scan(base_url, perp_data)
                    self._last_scan_time = current_time

                    # Vérifier après le scan pour arrêt rapide
                    if not self._scan_running:
                        break

                # Attendre avec vérification d'interruption
                await self._wait_with_interrupt_check(10)

            except asyncio.CancelledError:
                self.logger.info("🛑 Scanner annulé")
                break
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur dans la boucle de scan: {e}")
                if not self._scan_running:
                    break
                # Attendre avant de continuer pour éviter une boucle d'erreur
                await asyncio.sleep(10)
                continue

    def _should_perform_scan(self, current_time: float) -> bool:
        """Vérifie s'il est temps d'effectuer un nouveau scan."""
        return self._scan_running and (
            current_time - self._last_scan_time >= self._scan_interval
        )

    async def _wait_with_interrupt_check(self, seconds: int):
        """Attend avec vérification d'interruption."""
        for _ in range(seconds):
            if not self._scan_running:
                break
            await asyncio.sleep(1)

    async def _perform_scan(self, base_url: str, perp_data: Dict):
        """
        Effectue un scan complet du marché.
        
        Args:
            base_url: URL de base de l'API
            perp_data: Données des perpétuels
        """
        if not self._scan_running or not self._scan_callback:
            return

        try:
            # Appeler le callback de scan
            await self._scan_callback(base_url, perp_data)
            
        except Exception as e:
            # Ne pas logger si on est en train de s'arrêter
            if self._scan_running:
                self.logger.warning(f"⚠️ Erreur lors du scan: {e}")

    def is_running(self) -> bool:
        """
        Vérifie si le scanner est en cours d'exécution.

        Returns:
            True si en cours d'exécution
        """
        return self._scan_running

    def set_scan_interval(self, interval: int):
        """
        Modifie l'intervalle de scan.

        Args:
            interval: Nouvel intervalle en secondes
        """
        self._scan_interval = interval
        self.logger.info(f"📊 Intervalle de scan défini à {interval}s")

