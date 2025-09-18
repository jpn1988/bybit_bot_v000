#!/usr/bin/env python3
"""WebSocket privée Bybit v5 PRO - Runner persistant avec authentification et reconnexion."""

import os
import signal
from config import get_settings
from logging_setup import setup_logging
from ws_private import PrivateWSClient


class PrivateWSRunner:
    """Runner WebSocket privée Bybit v5, basé sur PrivateWSClient (réutilisable)."""

    def __init__(self):
        self.logger = setup_logging()
        # Configuration du signal handler pour Ctrl+C
        signal.signal(signal.SIGINT, self._signal_handler)

        # Configuration
        settings = get_settings()
        self.testnet = settings['testnet']
        self.api_key = settings['api_key']
        self.api_secret = settings['api_secret']

        # Vérifier les clés API
        if not self.api_key or not self.api_secret:
            self.logger.error("⛔ Clés API manquantes : ajoute BYBIT_API_KEY et BYBIT_API_SECRET dans .env")
            exit(1)

        # Channels par défaut (configurable via env)
        default_channels = "wallet,order"
        env_channels = os.getenv("WS_PRIV_CHANNELS", default_channels)
        self.channels = [ch.strip() for ch in env_channels.split(",") if ch.strip()]

        self.client = PrivateWSClient(
            testnet=self.testnet,
            api_key=self.api_key,
            api_secret=self.api_secret,
            channels=self.channels,
            logger=self.logger,
        )

    def _signal_handler(self, signum, frame):
        """Gestionnaire de signal pour Ctrl+C."""
        self.logger.info("🧹 Arrêt demandé par l'utilisateur (Ctrl+C)")
        self.client.close()
        exit(0)

    def run(self):
        self.logger.info("🚀 Démarrage WebSocket privée (runner)")
        self.logger.info(f"📂 Configuration chargée (testnet={self.testnet}, channels={self.channels})")
        self.logger.info(f"🔑 Clé API: {'présente' if self.api_key else 'absente'}")
        self.client.run()


def main():
    """Fonction principale."""
    runner = PrivateWSRunner()
    runner.run()


if __name__ == "__main__":
    main()
