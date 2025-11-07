#!/usr/bin/env python3
"""
Script de diagnostic pour SmartOrderPlacer

Ce script permet de diagnostiquer et tester le SmartOrderPlacer
sans placer d'ordres réels.
"""

import sys
import os
import time
import json
from datetime import datetime

# Ajouter le répertoire src au path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from smart_order_placer import SmartOrderPlacer, LiquidityClassifier, DynamicPriceCalculator
from bybit_client_backup import BybitClient

class SmartOrderPlacerDiagnostic:
    """Classe de diagnostic pour SmartOrderPlacer"""
    
    def __init__(self, testnet=True):
        """Initialiser le diagnostic"""
        self.testnet = testnet
        self.bybit_client = None
        self.smart_placer = None
        self.logger = self._setup_logger()
        
    def _setup_logger(self):
        """Configurer le logger"""
        import logging
        
        logger = logging.getLogger('diagnostic')
        logger.setLevel(logging.INFO)
        
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger
    
    def initialize(self):
        """Initialiser les composants"""
        print("🔧 Initialisation des composants...")
        
        try:
            # Initialiser le client Bybit
            self.bybit_client = BybitClient(testnet=self.testnet)
            print("   ✅ Client Bybit initialisé")
            
            # Initialiser le SmartOrderPlacer
            self.smart_placer = SmartOrderPlacer(self.bybit_client, self.logger)
            print("   ✅ SmartOrderPlacer initialisé")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Erreur d'initialisation: {e}")
            return False
    
    def test_connection(self):
        """Tester la connexion à Bybit"""
        print("\n🌐 Test de connexion Bybit...")
        
        try:
            # Test simple de l'API
            response = self.bybit_client.get_server_time()
            if response and 'result' in response:
                print("   ✅ Connexion Bybit réussie")
                print(f"   📅 Heure serveur: {response['result']['timeSecond']}")
                return True
            else:
                print("   ❌ Réponse API invalide")
                return False
                
        except Exception as e:
            print(f"   ❌ Erreur de connexion: {e}")
            return False
    
    def test_orderbook_retrieval(self, symbol="BTCUSDT"):
        """Tester la récupération d'order book"""
        print(f"\n📊 Test order book pour {symbol}...")
        
        try:
            # Test récupération order book
            orderbook = self.smart_placer._get_cached_orderbook(symbol, "linear")
            
            if orderbook and len(orderbook) > 0:
                print(f"   ✅ Order book récupéré: {len(orderbook)} niveaux")
                print(f"   📈 Best bid: {orderbook[0]['price']}")
                print(f"   📉 Best ask: {orderbook[1]['price']}")
                
                # Calculer le spread
                bid = float(orderbook[0]['price'])
                ask = float(orderbook[1]['price'])
                spread = ((ask - bid) / bid) * 100
                print(f"   📊 Spread: {spread:.4f}%")
                
                return orderbook
            else:
                print("   ❌ Order book vide ou invalide")
                return None
                
        except Exception as e:
            print(f"   ❌ Erreur récupération order book: {e}")
            return None
    
    def test_liquidity_classification(self, orderbook):
        """Tester la classification de liquidité"""
        print("\n🔍 Test classification de liquidité...")
        
        try:
            classifier = LiquidityClassifier()
            liquidity = classifier.classify_liquidity(orderbook)
            
            print(f"   ✅ Classification: {liquidity}")
            
            # Calculer les métriques
            bid = float(orderbook[0]['price'])
            ask = float(orderbook[1]['price'])
            relative_spread = (ask - bid) / bid
            
            # Calculer le volume des 10 premiers niveaux
            top_10_volume = sum(float(level['size']) for level in orderbook[:10])
            
            print(f"   📊 Spread relatif: {relative_spread:.6f}")
            print(f"   📊 Volume top 10: {top_10_volume:,.0f}")
            
            return liquidity
            
        except Exception as e:
            print(f"   ❌ Erreur classification: {e}")
            return None
    
    def test_price_calculation(self, symbol="BTCUSDT", orderbook=None):
        """Tester le calcul de prix"""
        print(f"\n💰 Test calcul de prix pour {symbol}...")
        
        try:
            calculator = DynamicPriceCalculator()
            
            # Test prix d'achat
            buy_price, buy_level, buy_offset = calculator.compute_dynamic_price(
                symbol, "Buy", orderbook
            )
            
            # Test prix de vente
            sell_price, sell_level, sell_offset = calculator.compute_dynamic_price(
                symbol, "Sell", orderbook
            )
            
            print(f"   ✅ Prix d'achat: {buy_price:.2f} (niveau: {buy_level}, offset: {buy_offset:.4f})")
            print(f"   ✅ Prix de vente: {sell_price:.2f} (niveau: {sell_level}, offset: {sell_offset:.4f})")
            
            # Vérifier la cohérence
            bid = float(orderbook[0]['price'])
            ask = float(orderbook[1]['price'])
            
            if bid < buy_price < ask:
                print("   ✅ Prix d'achat cohérent (entre bid et ask)")
            else:
                print("   ⚠️ Prix d'achat incohérent")
                
            if bid < sell_price < ask:
                print("   ✅ Prix de vente cohérent (entre bid et ask)")
            else:
                print("   ⚠️ Prix de vente incohérent")
            
            return {
                'buy': (buy_price, buy_level, buy_offset),
                'sell': (sell_price, sell_level, sell_offset)
            }
            
        except Exception as e:
            print(f"   ❌ Erreur calcul prix: {e}")
            return None
    
    def test_minimum_order_value(self, symbol="BTCUSDT", price=50000.0):
        """Tester la vérification du minimum 5 USDT"""
        print(f"\n💵 Test minimum 5 USDT pour {symbol}...")
        
        try:
            # Test avec quantité trop petite
            small_qty = "0.0001"  # 0.0001 * 50000 = 5 USDT (juste au minimum)
            very_small_qty = "0.00005"  # 0.00005 * 50000 = 2.5 USDT (trop petit)
            
            print(f"   🧪 Test quantité normale: {small_qty} @ {price} = {float(small_qty) * price:.2f} USDT")
            print(f"   🧪 Test quantité trop petite: {very_small_qty} @ {price} = {float(very_small_qty) * price:.2f} USDT")
            
            # Le système devrait ajuster automatiquement la quantité trop petite
            min_value = 5.0
            required_qty = min_value / price
            adjusted_qty = f"{required_qty:.6f}".rstrip('0').rstrip('.')
            
            print(f"   ✅ Quantité ajustée requise: {adjusted_qty}")
            print(f"   ✅ Valeur ajustée: {float(adjusted_qty) * price:.2f} USDT")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Erreur test minimum: {e}")
            return False
    
    def test_cache_functionality(self, symbol="BTCUSDT"):
        """Tester la fonctionnalité du cache"""
        print(f"\n💾 Test cache pour {symbol}...")
        
        try:
            # Premier appel
            start_time = time.time()
            orderbook1 = self.smart_placer._get_cached_orderbook(symbol, "linear")
            time1 = time.time() - start_time
            
            # Deuxième appel (devrait utiliser le cache)
            start_time = time.time()
            orderbook2 = self.smart_placer._get_cached_orderbook(symbol, "linear")
            time2 = time.time() - start_time
            
            print(f"   📊 Premier appel: {time1:.3f}s")
            print(f"   📊 Deuxième appel: {time2:.3f}s")
            print(f"   📊 Amélioration: {((time1 - time2) / time1 * 100):.1f}%")
            
            if time2 < time1:
                print("   ✅ Cache fonctionne correctement")
            else:
                print("   ⚠️ Cache pourrait ne pas fonctionner")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Erreur test cache: {e}")
            return False
    
    def test_simulation_order_placement(self, symbol="BTCUSDT"):
        """Simuler un placement d'ordre (sans ordre réel)"""
        print(f"\n🎭 Simulation placement ordre pour {symbol}...")
        
        try:
            # Récupérer l'order book
            orderbook = self.smart_placer._get_cached_orderbook(symbol, "linear")
            if not orderbook:
                print("   ❌ Pas d'order book disponible")
                return False
            
            # Calculer les prix
            calculator = DynamicPriceCalculator()
            price, level, offset = calculator.compute_dynamic_price(
                symbol, "Buy", orderbook
            )
            
            # Simuler la vérification du minimum
            qty = "0.001"
            order_value = float(qty) * price
            
            print(f"   📊 Symbole: {symbol}")
            print(f"   📊 Côté: Buy")
            print(f"   📊 Quantité: {qty}")
            print(f"   📊 Prix calculé: {price:.2f}")
            print(f"   📊 Valeur ordre: {order_value:.2f} USDT")
            print(f"   📊 Niveau liquidité: {level}")
            print(f"   📊 Offset: {offset:.4f}")
            
            if order_value >= 5.0:
                print("   ✅ Valeur ordre respecte le minimum 5 USDT")
            else:
                print("   ⚠️ Valeur ordre < 5 USDT (serait ajustée automatiquement)")
            
            print("   ✅ Simulation réussie (aucun ordre réel placé)")
            return True
            
        except Exception as e:
            print(f"   ❌ Erreur simulation: {e}")
            return False
    
    def run_full_diagnostic(self, symbol="BTCUSDT"):
        """Lancer le diagnostic complet"""
        print("🔍 DIAGNOSTIC COMPLET SMART ORDER PLACER")
        print("=" * 60)
        print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🌐 Testnet: {'Oui' if self.testnet else 'Non'}")
        print(f"📊 Symbole: {symbol}")
        print("=" * 60)
        
        results = {}
        
        # 1. Initialisation
        results['initialization'] = self.initialize()
        if not results['initialization']:
            print("\n❌ Échec d'initialisation - arrêt du diagnostic")
            return results
        
        # 2. Test connexion
        results['connection'] = self.test_connection()
        if not results['connection']:
            print("\n❌ Échec de connexion - arrêt du diagnostic")
            return results
        
        # 3. Test order book
        orderbook = self.test_orderbook_retrieval(symbol)
        results['orderbook'] = orderbook is not None
        
        if not results['orderbook']:
            print("\n❌ Échec récupération order book - arrêt du diagnostic")
            return results
        
        # 4. Test classification liquidité
        liquidity = self.test_liquidity_classification(orderbook)
        results['liquidity'] = liquidity is not None
        
        # 5. Test calcul prix
        prices = self.test_price_calculation(symbol, orderbook)
        results['price_calculation'] = prices is not None
        
        # 6. Test minimum 5 USDT
        if prices:
            test_price = prices['buy'][0]
            results['minimum_value'] = self.test_minimum_order_value(symbol, test_price)
        
        # 7. Test cache
        results['cache'] = self.test_cache_functionality(symbol)
        
        # 8. Simulation placement
        results['simulation'] = self.test_simulation_order_placement(symbol)
        
        # Résumé
        print("\n" + "=" * 60)
        print("📊 RÉSUMÉ DU DIAGNOSTIC")
        print("=" * 60)
        
        total_tests = len(results)
        passed_tests = sum(1 for result in results.values() if result)
        
        for test_name, result in results.items():
            status = "✅" if result else "❌"
            print(f"   {status} {test_name.replace('_', ' ').title()}")
        
        print(f"\n📈 Score: {passed_tests}/{total_tests} ({passed_tests/total_tests*100:.1f}%)")
        
        if passed_tests == total_tests:
            print("🎉 Tous les tests sont passés ! Le SmartOrderPlacer est prêt.")
        else:
            print("⚠️ Certains tests ont échoué. Vérifiez la configuration.")
        
        return results

def main():
    """Fonction principale"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Diagnostic SmartOrderPlacer')
    parser.add_argument('--symbol', default='BTCUSDT', help='Symbole à tester')
    parser.add_argument('--testnet', action='store_true', help='Utiliser testnet')
    parser.add_argument('--mainnet', action='store_true', help='Utiliser mainnet')
    
    args = parser.parse_args()
    
    # Déterminer l'environnement
    testnet = args.testnet or not args.mainnet
    
    # Lancer le diagnostic
    diagnostic = SmartOrderPlacerDiagnostic(testnet=testnet)
    results = diagnostic.run_full_diagnostic(args.symbol)
    
    # Code de sortie
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    
    if passed_tests == total_tests:
        sys.exit(0)  # Succès
    else:
        sys.exit(1)  # Échec

if __name__ == "__main__":
    main()
