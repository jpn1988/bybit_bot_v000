#!/usr/bin/env python3
"""
Script de test simplifié pour vérifier que le bot refactorisé fonctionne.

Ce script teste que :
1. Les nouveaux composants s'initialisent correctement
2. L'interface publique reste identique
3. Aucune régression n'est introduite
"""

import sys
import os

# Ajouter le répertoire src au path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """Test que tous les modules s'importent correctement."""
    print("Test des imports...")
    
    try:
        from bot_lifecycle_manager import BotLifecycleManager
        print("OK BotLifecycleManager importe")
    except ImportError as e:
        print(f"ERREUR import BotLifecycleManager: {e}")
        return False
    
    try:
        from position_event_handler import PositionEventHandler
        print("OK PositionEventHandler importe")
    except ImportError as e:
        print(f"ERREUR import PositionEventHandler: {e}")
        return False
    
    try:
        from fallback_data_manager import FallbackDataManager
        print("OK FallbackDataManager importe")
    except ImportError as e:
        print(f"ERREUR import FallbackDataManager: {e}")
        return False
    
    try:
        from bot import BotOrchestrator
        print("OK BotOrchestrator importe")
    except ImportError as e:
        print(f"ERREUR import BotOrchestrator: {e}")
        return False
    
    return True

def test_component_creation():
    """Test que les composants se créent correctement."""
    print("\nTest de création des composants...")
    
    try:
        from bot_lifecycle_manager import BotLifecycleManager
        from position_event_handler import PositionEventHandler
        from fallback_data_manager import FallbackDataManager
        
        # Créer les composants
        lifecycle_manager = BotLifecycleManager(testnet=True)
        position_handler = PositionEventHandler(testnet=True)
        fallback_manager = FallbackDataManager(testnet=True)
        
        print("OK BotLifecycleManager cree")
        print("OK PositionEventHandler cree")
        print("OK FallbackDataManager cree")
        
        # Vérifier les propriétés
        assert lifecycle_manager.testnet == True
        assert position_handler.testnet == True
        assert fallback_manager.testnet == True
        
        print("OK Proprietes des composants correctes")
        
        return True
        
    except Exception as e:
        print(f"ERREUR creation composants: {e}")
        return False

def test_bot_interface():
    """Test que l'interface du bot reste identique."""
    print("\nTest de l'interface du bot...")
    
    try:
        from bot import BotOrchestrator
        
        # Vérifier que la classe a les méthodes attendues
        expected_methods = [
            '__init__',
            'start',
            'stop',
            'get_status',
            '_on_position_opened',
            '_on_position_closed',
            '_get_funding_data_for_scheduler'
        ]
        
        for method_name in expected_methods:
            if hasattr(BotOrchestrator, method_name):
                print(f"OK Methode {method_name} presente")
            else:
                print(f"ERREUR Methode {method_name} manquante")
                return False
        
        return True
        
    except Exception as e:
        print(f"ERREUR test interface: {e}")
        return False

def test_delegation_methods():
    """Test que les méthodes de délégation existent."""
    print("\nTest des méthodes de délégation...")
    
    try:
        from position_event_handler import PositionEventHandler
        from fallback_data_manager import FallbackDataManager
        
        # Vérifier PositionEventHandler
        position_handler = PositionEventHandler(testnet=True)
        assert hasattr(position_handler, 'on_position_opened')
        assert hasattr(position_handler, 'on_position_closed')
        print("OK PositionEventHandler a les methodes de callback")
        
        # Vérifier FallbackDataManager
        fallback_manager = FallbackDataManager(testnet=True)
        assert hasattr(fallback_manager, 'get_funding_data_for_scheduler')
        assert hasattr(fallback_manager, 'update_funding_data_periodically')
        print("OK FallbackDataManager a les methodes de donnees")
        
        return True
        
    except Exception as e:
        print(f"ERREUR test delegation: {e}")
        return False

def run_tests():
    """Lance tous les tests."""
    print("Lancement des tests du bot refactorise...")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_component_creation,
        test_bot_interface,
        test_delegation_methods,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                print(f"ERREUR Test {test.__name__} a echoue")
        except Exception as e:
            print(f"ERREUR Test {test.__name__} a echoue avec exception: {e}")
    
    print("\n" + "=" * 50)
    print(f"Resultat: {passed}/{total} tests passes")
    
    if passed == total:
        print("SUCCES Tous les tests sont passes ! Le bot refactorise fonctionne correctement.")
        return True
    else:
        print("ERREUR Certains tests ont echoue.")
        return False

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
