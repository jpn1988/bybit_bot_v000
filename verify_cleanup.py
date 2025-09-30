#!/usr/bin/env python3
"""
Script de vérification du nettoyage des commentaires "(silencieux)".
"""

import sys
import os
sys.path.append('src')

def verify_cleanup():
    """Vérifie que tous les commentaires '(silencieux)' ont été supprimés."""
    print("🧹 Vérification du nettoyage des commentaires '(silencieux)'...")
    
    # Rechercher tous les commentaires "(silencieux)" restants
    silent_comments = []
    
    for root, dirs, files in os.walk('src'):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        for line_num, line in enumerate(lines, 1):
                            if '# ' in line and 'silencieux' in line:
                                silent_comments.append(f"{file_path}:{line_num}: {line.strip()}")
                except Exception as e:
                    print(f"⚠️ Erreur lecture {file_path}: {e}")
    
    if silent_comments:
        print(f"❌ {len(silent_comments)} commentaires '(silencieux)' trouvés:")
        for comment in silent_comments:
            print(f"   {comment}")
        return False
    else:
        print("✅ Aucun commentaire '(silencieux)' trouvé - nettoyage réussi !")
        return True

def test_imports():
    """Teste que tous les modules peuvent être importés."""
    print("\n🧪 Test des imports après nettoyage...")
    
    modules_to_test = [
        'bot',
        'watchlist_manager', 
        'volatility_tracker',
        'ws_manager',
        'metrics_monitor',
        'http_client_manager',
        'ws_public'
    ]
    
    failed_imports = []
    
    for module in modules_to_test:
        try:
            __import__(module)
            print(f"✅ {module}")
        except ImportError as e:
            failed_imports.append(f"{module}: {e}")
            print(f"❌ {module}: {e}")
    
    if failed_imports:
        print(f"\n⚠️ {len(failed_imports)} imports échoués")
        return False
    else:
        print("\n🎉 Tous les imports réussis !")
        return True

def main():
    """Fonction principale."""
    print("🚀 Vérification du nettoyage des commentaires")
    print("=" * 50)
    
    cleanup_ok = verify_cleanup()
    imports_ok = test_imports()
    
    print("\n" + "=" * 50)
    if cleanup_ok and imports_ok:
        print("🎉 SUCCÈS : Tous les commentaires '(silencieux)' ont été supprimés")
        print("   et tous les modules peuvent être importés correctement !")
        return True
    else:
        print("⚠️ ÉCHEC : Des problèmes ont été détectés")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
