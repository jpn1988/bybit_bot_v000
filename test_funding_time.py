#!/usr/bin/env python3
"""
Test rapide pour vérifier le calcul du temps de funding.
"""

import sys
import time
sys.path.append('src')

def test_funding_time_calculation():
    """Teste le calcul du temps de funding."""
    print("🧪 Test du calcul du temps de funding...")
    
    try:
        from watchlist_manager import WatchlistManager
        
        wm = WatchlistManager(testnet=True)
        
        # Test avec un timestamp futur (1 heure)
        future_ts = str(int((time.time() + 3600) * 1000))
        result = wm.calculate_funding_time_remaining(future_ts)
        print(f"✅ Timestamp futur (1h): {result}")
        
        # Test avec un timestamp passé
        past_ts = str(int((time.time() - 3600) * 1000))
        result = wm.calculate_funding_time_remaining(past_ts)
        print(f"✅ Timestamp passé: {result}")
        
        # Test avec None
        result = wm.calculate_funding_time_remaining(None)
        print(f"✅ None: {result}")
        
        return True
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def test_bot_import():
    """Teste que le bot peut importer WatchlistManager."""
    print("\n🧪 Test import bot...")
    
    try:
        from bot import PriceTracker
        print("✅ Bot importé avec succès")
        return True
    except Exception as e:
        print(f"❌ Erreur import bot: {e}")
        return False

if __name__ == "__main__":
    success1 = test_funding_time_calculation()
    success2 = test_bot_import()
    
    if success1 and success2:
        print("\n🎉 Tous les tests sont passés !")
    else:
        print("\n⚠️ Certains tests ont échoué.")
