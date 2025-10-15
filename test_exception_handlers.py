#!/usr/bin/env python3
"""
Script de test pour démontrer les handlers globaux d'exceptions.

Ce script teste les 3 cas d'usage :
1. Exception dans un thread standard
2. Exception dans une tâche asyncio
3. Exception dans une coroutine fire-and-forget
"""

import asyncio
import threading
import time
import sys
import os

# Ajouter le répertoire src au path pour l'import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from logging_setup import setup_logging
from thread_exception_handler import install_global_exception_handlers


def test_thread_exception():
    """Test : Exception dans un thread standard."""
    print("\n🧵 TEST 1 : Exception dans un thread standard")
    print("─" * 60)
    
    def worker():
        time.sleep(0.5)
        raise ValueError("Oups ! Erreur dans le thread worker")
    
    thread = threading.Thread(target=worker, name="TestWorkerThread")
    thread.start()
    thread.join()
    
    print("✅ Thread terminé (vérifiez le log ci-dessus)")


async def test_asyncio_task_exception():
    """Test : Exception dans une tâche asyncio."""
    print("\n⚡ TEST 2 : Exception dans une tâche asyncio")
    print("─" * 60)
    
    async def failing_task():
        await asyncio.sleep(0.5)
        raise RuntimeError("Oups ! Erreur dans la tâche async")
    
    # Créer la tâche sans await (fire-and-forget)
    task = asyncio.create_task(failing_task())
    
    # Attendre que la tâche termine
    try:
        await task
    except RuntimeError:
        pass  # Exception attendue
    
    print("✅ Tâche asyncio terminée (vérifiez le log ci-dessus)")


async def test_asyncio_fire_and_forget():
    """Test : Exception dans une coroutine fire-and-forget."""
    print("\n🚀 TEST 3 : Exception dans une coroutine fire-and-forget")
    print("─" * 60)
    
    async def background_task():
        await asyncio.sleep(0.3)
        raise TypeError("Oups ! Erreur dans la tâche background")
    
    # Lancer sans await ni référence (fire-and-forget)
    asyncio.create_task(background_task())
    
    # Attendre que la tâche ait le temps de s'exécuter
    await asyncio.sleep(1.0)
    
    print("✅ Tâche fire-and-forget terminée (vérifiez le log ci-dessus)")


async def main():
    """Fonction principale de test."""
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "TEST DES HANDLERS D'EXCEPTIONS" + " " * 28 + "║")
    print("╚" + "═" * 78 + "╝")
    
    # Initialiser le logger
    logger = setup_logging()
    
    # Installer les handlers globaux
    print("\n📦 Installation des handlers globaux...")
    install_global_exception_handlers(logger)
    print("✅ Handlers installés\n")
    
    # Test 1 : Thread exception
    test_thread_exception()
    await asyncio.sleep(1)
    
    # Test 2 : Asyncio task exception
    await test_asyncio_task_exception()
    await asyncio.sleep(1)
    
    # Test 3 : Fire-and-forget exception
    await test_asyncio_fire_and_forget()
    
    print("\n" + "═" * 80)
    print("✅ TOUS LES TESTS TERMINÉS")
    print("═" * 80)
    print("\n📝 Vérifiez que les 3 exceptions ont été loggées ci-dessus :")
    print("   1. ValueError dans le thread 'TestWorkerThread'")
    print("   2. RuntimeError dans la tâche asyncio")
    print("   3. TypeError dans la tâche fire-and-forget")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Test interrompu par l'utilisateur")

