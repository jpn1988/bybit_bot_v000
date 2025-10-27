#!/usr/bin/env python3
"""
Script de test pour diagnostiquer les problèmes de fermeture après funding.
"""

import sys
import os
import time
import asyncio

# Ajouter le répertoire src au path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from bot import BotOrchestrator
from logging_setup import setup_logging

async def test_funding_close():
    """Test de la fermeture automatique après funding."""
    logger = setup_logging()
    logger.info("🧪 Démarrage du test de fermeture après funding")
    
    try:
        # Créer l'orchestrateur
        orchestrator = BotOrchestrator()
        
        # Attendre un peu pour l'initialisation
        await asyncio.sleep(2)
        
        # Vérifier que le FundingCloseManager est initialisé
        if orchestrator.funding_close_manager:
            logger.info("✅ FundingCloseManager initialisé")
            
            # Tester avec un symbole fictif
            test_symbol = "BTCUSDT"
            orchestrator.funding_close_manager.add_position_to_monitor(test_symbol)
            
            # Attendre un peu
            await asyncio.sleep(1)
            
            # Tester la détection de funding
            orchestrator.funding_close_manager.test_funding_detection(test_symbol)
            
            # Afficher le statut
            monitored = orchestrator.funding_close_manager.get_monitored_positions()
            logger.info(f"📊 Positions surveillées: {monitored}")
            
        else:
            logger.error("❌ FundingCloseManager non initialisé")
            
        # Vérifier le PositionMonitor
        if orchestrator.position_monitor:
            logger.info("✅ PositionMonitor initialisé")
            logger.info(f"📊 PositionMonitor running: {orchestrator.position_monitor.is_running()}")
        else:
            logger.error("❌ PositionMonitor non initialisé")
            
        # Vérifier le PositionEventHandler
        if orchestrator._position_event_handler:
            logger.info("✅ PositionEventHandler initialisé")
            if hasattr(orchestrator._position_event_handler, 'funding_close_manager'):
                logger.info("✅ PositionEventHandler a le FundingCloseManager")
            else:
                logger.error("❌ PositionEventHandler n'a pas le FundingCloseManager")
        else:
            logger.error("❌ PositionEventHandler non initialisé")
            
    except Exception as e:
        logger.error(f"❌ Erreur lors du test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_funding_close())
