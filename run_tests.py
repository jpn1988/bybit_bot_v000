#!/usr/bin/env python3
"""Script pour exécuter les tests du bot Bybit."""

import subprocess
import sys
import os
from pathlib import Path


def run_tests():
    """Exécute les tests avec pytest."""
    print("🧪 Exécution des tests du bot Bybit...")
    print("=" * 50)
    
    # Vérifier que pytest est installé
    try:
        import pytest
        print(f"✅ pytest version {pytest.__version__} trouvé")
    except ImportError:
        print("❌ pytest non trouvé. Installez-le avec: pip install pytest pytest-mock pytest-asyncio")
        return False
    
    # Changer vers le répertoire du projet
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    # Commande pytest
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "--color=yes"
    ]
    
    print(f"📁 Répertoire de travail: {project_root}")
    print(f"🔧 Commande: {' '.join(cmd)}")
    print("=" * 50)
    
    try:
        # Exécuter les tests
        result = subprocess.run(cmd, check=False)
        
        if result.returncode == 0:
            print("\n✅ Tous les tests sont passés avec succès!")
            return True
        else:
            print(f"\n❌ Certains tests ont échoué (code de retour: {result.returncode})")
            return False
            
    except Exception as e:
        print(f"\n❌ Erreur lors de l'exécution des tests: {e}")
        return False


def run_specific_test(test_name):
    """Exécute un test spécifique."""
    print(f"🧪 Exécution du test: {test_name}")
    print("=" * 50)
    
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    cmd = [
        sys.executable, "-m", "pytest",
        f"tests/{test_name}",
        "-v",
        "--tb=short",
        "--color=yes"
    ]
    
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Test spécifique
        test_file = sys.argv[1]
        success = run_specific_test(test_file)
    else:
        # Tous les tests
        success = run_tests()
    
    sys.exit(0 if success else 1)
