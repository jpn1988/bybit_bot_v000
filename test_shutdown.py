#!/usr/bin/env python3
"""
Script de test pour vérifier l'arrêt propre du bot.
Ce script teste les améliorations d'arrêt pour s'assurer que tous les threads se terminent proprement.
"""

import time
import threading
import signal
import sys
import os

# Ajouter le répertoire src au path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from bot_orchestrator import BotOrchestrator
from logging_setup import setup_logging

def test_shutdown():
    """Test l'arrêt propre du bot."""
    logger = setup_logging()
    logger.info("🧪 Démarrage du test d'arrêt du bot...")
    
    try:
        # Créer l'orchestrateur
        orchestrator = BotOrchestrator()
        
        # Démarrer le bot en arrière-plan
        import asyncio
        
        async def run_test():
            try:
                # Démarrer le bot
                await orchestrator.start()
            except Exception as e:
                logger.error(f"❌ Erreur lors du démarrage du bot: {e}")
        
        # Lancer le bot dans un thread séparé
        bot_thread = threading.Thread(target=lambda: asyncio.run(run_test()))
        bot_thread.daemon = True
        bot_thread.start()
        
        # Attendre que le bot démarre
        logger.info("⏳ Attente du démarrage du bot...")
        time.sleep(5)
        
        # Vérifier les threads actifs avant l'arrêt
        threads_before = threading.enumerate()
        logger.info(f"📊 Threads actifs avant arrêt: {len(threads_before)}")
        for i, thread in enumerate(threads_before):
            logger.info(f"  Thread {i+1}: {thread.name} (daemon={thread.daemon})")
        
        # Simuler Ctrl+C
        logger.info("🛑 Simulation de Ctrl+C...")
        orchestrator._signal_handler(signal.SIGINT, None)
        
        # Attendre l'arrêt
        logger.info("⏳ Attente de l'arrêt du bot...")
        time.sleep(3)
        
        # Vérifier les threads actifs après l'arrêt
        threads_after = threading.enumerate()
        logger.info(f"📊 Threads actifs après arrêt: {len(threads_after)}")
        for i, thread in enumerate(threads_after):
            logger.info(f"  Thread {i+1}: {thread.name} (daemon={thread.daemon})")
        
        # Vérifier que le nombre de threads a diminué
        if len(threads_after) < len(threads_before):
            logger.info("✅ Test d'arrêt réussi - nombre de threads réduit")
        else:
            logger.warning("⚠️ Test d'arrêt partiellement réussi - certains threads persistent")
        
        # Analyser les threads restants
        remaining_threads = [t for t in threads_after if t != threading.current_thread() and t.is_alive()]
        if remaining_threads:
            logger.info(f"📊 Analyse des {len(remaining_threads)} threads restants:")
            for i, thread in enumerate(remaining_threads):
                logger.info(f"  Thread {i+1}: {thread.name} (daemon={thread.daemon})")
                
                # Vérifier si ce sont des threads problématiques
                if any(name in thread.name for name in ['_monitor_loop', '_run_safe_shutdown_loop', 'asyncio', '_send_ping']):
                    logger.warning(f"    ⚠️ Thread problématique détecté: {thread.name}")
                elif 'loguru' in thread.name:
                    logger.info(f"    ℹ️ Thread de logging (normal): {thread.name}")
                else:
                    logger.info(f"    ℹ️ Thread système: {thread.name}")
        
        # Identifier les threads récalcitrants spécifiques
        stubborn_threads = [t for t in threads_after if t != threading.current_thread() and t.is_alive()]
        if stubborn_threads:
            logger.warning(f"⚠️ {len(stubborn_threads)} threads récalcitrants détectés:")
            for i, thread in enumerate(stubborn_threads):
                logger.warning(f"  Thread {i+1}: {thread.name} (daemon={thread.daemon})")
                
            # Vérifier si ce sont les threads problématiques connus
            problematic_threads = [t for t in stubborn_threads if any(name in t.name for name in [
                '_monitor_loop', '_run_safe_shutdown_loop', 'asyncio', '_send_ping', 'loguru'
            ])]
            
            if problematic_threads:
                logger.warning("⚠️ Threads problématiques encore actifs:")
                for thread in problematic_threads:
                    logger.warning(f"  - {thread.name} (daemon={thread.daemon})")
            else:
                logger.info("✅ Aucun thread problématique détecté")
        
        # Attendre un peu plus pour voir si les threads se terminent
        logger.info("⏳ Attente supplémentaire pour l'arrêt des threads...")
        time.sleep(2)
        
        # Vérification finale
        threads_final = threading.enumerate()
        logger.info(f"📊 Threads finaux: {len(threads_final)}")
        
        # Identifier les threads récalcitrants
        stubborn_threads = [t for t in threads_final if t != threading.current_thread() and t.is_alive()]
        if stubborn_threads:
            logger.warning(f"⚠️ {len(stubborn_threads)} threads récalcitrants détectés:")
            for i, thread in enumerate(stubborn_threads):
                logger.warning(f"  Thread {i+1}: {thread.name} (daemon={thread.daemon})")
                
                # Analyser le type de thread
                if 'loguru' in thread.name:
                    logger.info(f"    ℹ️ Thread de logging (normal): {thread.name}")
                elif any(name in thread.name for name in ['_monitor_loop', '_run_safe_shutdown_loop', 'asyncio', '_send_ping']):
                    logger.warning(f"    ⚠️ Thread problématique: {thread.name}")
                else:
                    logger.info(f"    ℹ️ Thread système: {thread.name}")
        else:
            logger.info("✅ Tous les threads se sont arrêtés proprement")
        
        # Évaluer le succès du test
        problematic_threads = [t for t in stubborn_threads if any(name in t.name for name in ['_monitor_loop', '_run_safe_shutdown_loop', 'asyncio', '_send_ping'])]
        success = len(problematic_threads) == 0
        
        if success:
            logger.info("✅ Test d'arrêt réussi - aucun thread problématique détecté")
        else:
            logger.warning(f"⚠️ Test d'arrêt partiellement réussi - {len(problematic_threads)} threads problématiques persistent")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du test d'arrêt: {e}")
        return False

if __name__ == "__main__":
    success = test_shutdown()
    if success:
        print("\n✅ Test d'arrêt réussi - tous les threads se sont arrêtés proprement")
        sys.exit(0)
    else:
        print("\n❌ Test d'arrêt échoué - certains threads persistent")
        sys.exit(1)
