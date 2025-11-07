#!/usr/bin/env python3
"""
Exemples d'utilisation des context managers pour le bot Bybit.

Ce fichier démontre comment utiliser les context managers pour une gestion
automatique des ressources et un code plus propre.
"""

import asyncio
import sys
import os

# Ajouter le répertoire src au path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from logging_setup import setup_logging
from factories.bot_factory import BotFactory


async def example_async_bot_context_manager():
    """
    Exemple d'utilisation du context manager asynchrone pour BotOrchestrator.
    
    Le bot démarre automatiquement à l'entrée du contexte et s'arrête
    automatiquement à la sortie, même en cas d'exception.
    """
    print("🚀 Exemple: Context Manager Asynchrone pour BotOrchestrator")
    print("=" * 60)
    
    # Configuration du logging
    logger = setup_logging()
    
    # Création du bot via factory
    factory = BotFactory(logger=logger)
    bot = factory.create_bot(testnet=True)
    
    try:
        # Utilisation du context manager asynchrone
        async with bot as bot_instance:
            print("✅ Bot démarré automatiquement via context manager")
            print("📊 Bot en cours d'exécution...")
            
            # Simuler une utilisation du bot
            await asyncio.sleep(2)
            
            print("📈 Simulation d'opérations de trading...")
            await asyncio.sleep(1)
            
            print("✅ Opérations terminées")
            
    except Exception as e:
        print(f"❌ Erreur dans le contexte: {e}")
    
    print("🛑 Bot arrêté automatiquement via context manager")
    print()


async def example_async_runner_context_manager():
    """
    Exemple d'utilisation du context manager asynchrone pour AsyncBotRunner.
    
    L'AsyncBotRunner gère automatiquement l'event loop et le cycle de vie du bot.
    """
    print("🚀 Exemple: Context Manager Asynchrone pour AsyncBotRunner")
    print("=" * 60)
    
    # Configuration du logging
    logger = setup_logging()
    
    # Création du runner via factory
    factory = BotFactory(logger=logger)
    runner = factory.create_async_runner(testnet=True)
    
    try:
        # Utilisation du context manager asynchrone
        async with runner as runner_instance:
            print("✅ AsyncBotRunner démarré automatiquement via context manager")
            print("📊 Event loop géré automatiquement...")
            
            # Simuler une utilisation du runner
            await asyncio.sleep(2)
            
            print("📈 Simulation d'opérations de trading...")
            await asyncio.sleep(1)
            
            print("✅ Opérations terminées")
            
    except Exception as e:
        print(f"❌ Erreur dans le contexte: {e}")
    
    print("🛑 AsyncBotRunner arrêté automatiquement via context manager")
    print()


def example_sync_data_manager_context():
    """
    Exemple d'utilisation du context manager synchrone pour DataManager.
    
    Le DataManager peut être utilisé dans un contexte synchrone pour
    la gestion des ressources de données.
    """
    print("🚀 Exemple: Context Manager Synchrone pour DataManager")
    print("=" * 60)
    
    # Configuration du logging
    logger = setup_logging()
    
    # Création du bot via factory
    factory = BotFactory(logger=logger)
    bot = factory.create_bot(testnet=True)
    
    # Utilisation du context manager synchrone
    with bot.data_manager as data_manager:
        print("✅ DataManager entré dans le contexte")
        print("📊 Gestion des ressources de données...")
        
        # Simuler des opérations de données
        print("📈 Simulation d'opérations de données...")
        
        print("✅ Opérations de données terminées")
    
    print("🛑 DataManager sorti du contexte (nettoyage automatique)")
    print()


def example_sync_monitoring_manager_context():
    """
    Exemple d'utilisation du context manager synchrone pour MonitoringManager.
    
    Le MonitoringManager peut être utilisé dans un contexte synchrone pour
    la gestion des ressources de monitoring.
    """
    print("🚀 Exemple: Context Manager Synchrone pour MonitoringManager")
    print("=" * 60)
    
    # Configuration du logging
    logger = setup_logging()
    
    # Création du bot via factory
    factory = BotFactory(logger=logger)
    bot = factory.create_bot(testnet=True)
    
    # Utilisation du context manager synchrone
    with bot.monitoring_manager as monitoring_manager:
        print("✅ MonitoringManager entré dans le contexte")
        print("🔍 Gestion des ressources de monitoring...")
        
        # Simuler des opérations de monitoring
        print("📈 Simulation d'opérations de monitoring...")
        
        print("✅ Opérations de monitoring terminées")
    
    print("🛑 MonitoringManager sorti du contexte (nettoyage automatique)")
    print()


async def example_nested_context_managers():
    """
    Exemple d'utilisation imbriquée de context managers.
    
    Démontre comment utiliser plusieurs context managers ensemble
    pour une gestion fine des ressources.
    """
    print("🚀 Exemple: Context Managers Imbriqués")
    print("=" * 60)
    
    # Configuration du logging
    logger = setup_logging()
    
    # Création du bot via factory
    factory = BotFactory(logger=logger)
    bot = factory.create_bot(testnet=True)
    
    try:
        # Context manager principal (bot)
        async with bot as bot_instance:
            print("✅ Bot principal démarré")
            
            # Context manager pour les données
            with bot_instance.data_manager as data_manager:
                print("✅ DataManager dans le contexte du bot")
                
                # Context manager pour le monitoring
                with bot_instance.monitoring_manager as monitoring_manager:
                    print("✅ MonitoringManager dans le contexte du bot")
                    
                    # Simuler des opérations complexes
                    print("📊 Opérations complexes avec gestion automatique des ressources...")
                    await asyncio.sleep(1)
                    
                    print("✅ Opérations complexes terminées")
                
                print("🛑 MonitoringManager nettoyé")
            
            print("🛑 DataManager nettoyé")
            
    except Exception as e:
        print(f"❌ Erreur dans les contextes imbriqués: {e}")
    
    print("🛑 Bot principal arrêté")
    print()


async def example_error_handling_in_context():
    """
    Exemple de gestion d'erreurs dans les context managers.
    
    Démontre que les context managers nettoient automatiquement
    les ressources même en cas d'exception.
    """
    print("🚀 Exemple: Gestion d'Erreurs dans Context Managers")
    print("=" * 60)
    
    # Configuration du logging
    logger = setup_logging()
    
    # Création du bot via factory
    factory = BotFactory(logger=logger)
    bot = factory.create_bot(testnet=True)
    
    try:
        # Utilisation du context manager avec une erreur intentionnelle
        async with bot as bot_instance:
            print("✅ Bot démarré via context manager")
            print("📊 Bot en cours d'exécution...")
            
            # Simuler une opération normale
            await asyncio.sleep(1)
            
            # Simuler une erreur intentionnelle
            print("💥 Simulation d'une erreur...")
            raise ValueError("Erreur intentionnelle pour tester le nettoyage")
            
    except ValueError as e:
        print(f"❌ Erreur capturée: {e}")
        print("✅ Le context manager a nettoyé les ressources malgré l'erreur")
    
    print("🛑 Bot arrêté automatiquement malgré l'erreur")
    print()


async def main():
    """
    Fonction principale qui exécute tous les exemples.
    """
    print("🎯 EXEMPLES D'UTILISATION DES CONTEXT MANAGERS")
    print("=" * 80)
    print()
    
    # Exemples asynchrones
    await example_async_bot_context_manager()
    await example_async_runner_context_manager()
    await example_nested_context_managers()
    await example_error_handling_in_context()
    
    # Exemples synchrones
    example_sync_data_manager_context()
    example_sync_monitoring_manager_context()
    
    print("🎉 Tous les exemples terminés avec succès!")


if __name__ == "__main__":
    # Exécution des exemples
    asyncio.run(main())
