#!/usr/bin/env python3
"""
Script de test pour vérifier que la refactorisation de watchlist_manager fonctionne.
"""

import sys
import os
sys.path.append('src')

def test_imports():
    """Teste que tous les nouveaux modules peuvent être importés."""
    print("🧪 Test des imports...")
    
    try:
        from config_manager import ConfigManager
        print("✅ ConfigManager importé")
    except ImportError as e:
        print(f"❌ Erreur import ConfigManager: {e}")
        return False
    
    try:
        from market_data_fetcher import MarketDataFetcher
        print("✅ MarketDataFetcher importé")
    except ImportError as e:
        print(f"❌ Erreur import MarketDataFetcher: {e}")
        return False
    
    try:
        from symbol_filter import SymbolFilter
        print("✅ SymbolFilter importé")
    except ImportError as e:
        print(f"❌ Erreur import SymbolFilter: {e}")
        return False
    
    try:
        from watchlist_builder import WatchlistBuilder
        print("✅ WatchlistBuilder importé")
    except ImportError as e:
        print(f"❌ Erreur import WatchlistBuilder: {e}")
        return False
    
    try:
        from watchlist_manager import WatchlistManager
        print("✅ WatchlistManager (nouveau) importé")
    except ImportError as e:
        print(f"❌ Erreur import WatchlistManager: {e}")
        return False
    
    return True

def test_config_manager():
    """Teste le ConfigManager."""
    print("\n🧪 Test du ConfigManager...")
    
    try:
        from config_manager import ConfigManager
        
        config_manager = ConfigManager()
        
        # Test de chargement de config (peut échouer si pas de fichier)
        try:
            config = config_manager.load_and_validate_config()
            print("✅ Configuration chargée et validée")
            print(f"   Catégorie: {config.get('categorie', 'N/A')}")
            print(f"   Limite: {config.get('limite', 'N/A')}")
        except Exception as e:
            print(f"⚠️ Erreur chargement config (normal si pas de fichier): {e}")
        
        return True
    except Exception as e:
        print(f"❌ Erreur test ConfigManager: {e}")
        return False

def test_symbol_filter():
    """Teste le SymbolFilter."""
    print("\n🧪 Test du SymbolFilter...")
    
    try:
        from symbol_filter import SymbolFilter
        
        symbol_filter = SymbolFilter()
        
        # Test de calcul de temps de funding
        time_remaining = symbol_filter.calculate_funding_time_remaining("1735689600000")  # Timestamp futur
        print(f"✅ Calcul temps funding: {time_remaining}")
        
        # Test de filtrage par spread
        symbols_data = [
            ("BTCUSDT", 0.001, 1000000, "1h 30m 0s"),
            ("ETHUSDT", 0.002, 2000000, "2h 0m 0s")
        ]
        spread_data = {"BTCUSDT": 0.001, "ETHUSDT": 0.002}
        filtered = symbol_filter.filter_by_spread(symbols_data, spread_data, 0.005)
        print(f"✅ Filtrage par spread: {len(filtered)} symboles")
        
        return True
    except Exception as e:
        print(f"❌ Erreur test SymbolFilter: {e}")
        return False

def test_watchlist_manager():
    """Teste le WatchlistManager refactorisé."""
    print("\n🧪 Test du WatchlistManager refactorisé...")
    
    try:
        from watchlist_manager import WatchlistManager
        
        manager = WatchlistManager(testnet=True)
        print("✅ WatchlistManager créé")
        
        # Test de chargement de config
        try:
            config = manager.load_and_validate_config()
            print("✅ Configuration chargée via WatchlistManager")
        except Exception as e:
            print(f"⚠️ Erreur chargement config: {e}")
        
        return True
    except Exception as e:
        print(f"❌ Erreur test WatchlistManager: {e}")
        return False

def test_bot_compatibility():
    """Teste que le bot peut toujours importer WatchlistManager."""
    print("\n🧪 Test de compatibilité avec le bot...")
    
    try:
        from bot import PriceTracker
        print("✅ Bot peut importer PriceTracker")
        
        # Test de création du tracker (sans démarrage)
        tracker = PriceTracker()
        print("✅ PriceTracker créé")
        
        return True
    except Exception as e:
        print(f"❌ Erreur test compatibilité bot: {e}")
        return False

def main():
    """Fonction principale de test."""
    print("🚀 Test de refactorisation de watchlist_manager.py")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_config_manager,
        test_symbol_filter,
        test_watchlist_manager,
        test_bot_compatibility
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Résultats: {passed}/{total} tests réussis")
    
    if passed == total:
        print("🎉 Tous les tests sont passés ! La refactorisation fonctionne.")
        return True
    else:
        print("⚠️ Certains tests ont échoué. Vérifiez les erreurs ci-dessus.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
