#!/usr/bin/env python3
"""
Script de test pour vérifier le FundingCloseManager.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from funding_close_manager import FundingCloseManager
from bybit_client import BybitClient
from logging_setup import setup_logging
from config import get_settings

def test_funding_close_manager():
    """Test du FundingCloseManager."""
    logger = setup_logging()
    
    try:
        # Récupérer la configuration
        settings = get_settings()
        testnet = settings.get("testnet", True)
        
        # Créer le client Bybit
        client = BybitClient(
            testnet=testnet,
            api_key=settings["api_key"],
            api_secret=settings["api_secret"],
            logger=logger
        )
        
        # Créer le FundingCloseManager
        funding_manager = FundingCloseManager(
            testnet=testnet,
            logger=logger,
            bybit_client=client
        )
        
        # Démarrer le manager
        funding_manager.start()
        
        # Vérifier les positions surveillées
        monitored = funding_manager.get_monitored_positions()
        logger.info(f"📊 Positions surveillées: {monitored}")
        
        # Simuler l'ajout d'une position
        test_symbol = "FUSDT"
        funding_manager.add_position_to_monitor(test_symbol)
        
        monitored = funding_manager.get_monitored_positions()
        logger.info(f"📊 Positions surveillées après ajout: {monitored}")
        
        # Attendre un peu
        import time
        time.sleep(5)
        
        # Arrêter le manager
        funding_manager.stop()
        
        logger.info("✅ Test FundingCloseManager terminé")
        
    except Exception as e:
        logger.error(f"❌ Erreur test: {e}")

if __name__ == "__main__":
    test_funding_close_manager()
