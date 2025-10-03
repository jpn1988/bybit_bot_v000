#!/usr/bin/env python3
"""
Point d'entrée asynchrone pour le bot Bybit.

Cette classe lance le BotOrchestrator dans un event loop asyncio.
"""

import asyncio
import signal
import sys
from bot_orchestrator_refactored import BotOrchestrator
from logging_setup import setup_logging


class AsyncBotRunner:
    """
    Lance le BotOrchestrator dans un event loop asyncio.
    """
    def __init__(self):
        self.logger = setup_logging()
        self.orchestrator = BotOrchestrator()
        self.running = True

    async def start(self):
        """Démarre le bot de manière asynchrone."""
        self.logger.info("Démarrage du bot Bybit (mode asynchrone)...")
        try:
            # Configurer le signal handler pour l'arrêt propre (Windows compatible)
            try:
                loop = asyncio.get_running_loop()
                for sig in (signal.SIGINT, signal.SIGTERM):
                    loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
            except NotImplementedError:
                # Sur Windows, les signal handlers ne sont pas supportés
                self.logger.debug("Signal handlers non supportés sur cette plateforme")

            await self.orchestrator.start()
        except asyncio.CancelledError:
            self.logger.info("Bot arrêté par annulation de tâche.")
        except Exception as e:
            self.logger.error(f"Erreur critique dans le runner asynchrone: {e}", exc_info=True)
        finally:
            self.logger.info("Bot Bybit arrêté.")

    async def stop(self):
        """Arrête le bot de manière asynchrone."""
        if self.running:
            self.running = False
            self.logger.info("Signal d'arrêt reçu, arrêt propre du bot...")
            # Utiliser la nouvelle méthode stop() du orchestrateur refactorisé
            self.orchestrator.stop()
            # Annuler toutes les tâches restantes pour permettre l'arrêt de l'event loop
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            self.logger.info("Toutes les tâches asynchrones ont été annulées.")
            sys.exit(0)  # Forcer la sortie après l'arrêt propre


async def main_async():
    runner = AsyncBotRunner()
    await runner.start()


if __name__ == "__main__":
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nArrêt demandé par l'utilisateur (KeyboardInterrupt)")
    except Exception as e:
        print(f"Erreur inattendue: {e}")