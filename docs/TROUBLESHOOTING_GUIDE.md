# 🔧 Guide de Dépannage SmartOrderPlacer

## 🚨 Problèmes courants et solutions

### 1. Erreurs de placement d'ordres

#### ❌ "Order does not meet minimum order value 5USDT"

**Symptômes :**
```
[MAKER-OPEN] Erreur placement BTCUSDT (retry 0): Erreur API Bybit : retCode=110094 retMsg="Order does not meet minimum order value 5USDT"
```

**Causes possibles :**
- Quantité trop petite après formatage
- Prix trop bas pour la quantité donnée
- Règles de précision Bybit non respectées

**Solutions :**
```python
# 1. Vérifier la quantité calculée
print(f"Quantité: {qty}, Prix: {price}, Valeur: {float(qty) * float(price)}")

# 2. Ajuster la quantité automatiquement
if float(qty) * float(price) < 5.0:
    required_qty = 5.0 / float(price)
    qty = f"{required_qty:.6f}".rstrip('0').rstrip('.')

# 3. Vérifier les règles de précision
tick_size = get_tick_size(symbol)
min_qty = get_min_qty(symbol)
```

#### ❌ "Order quantity has too many decimals"

**Symptômes :**
```
[MAKER-OPEN] Erreur placement ETHUSDT (retry 0): Erreur API Bybit : retCode=170134 retMsg="Order quantity has too many decimals"
```

**Causes possibles :**
- Trop de décimales dans la quantité
- Formatage incorrect selon les règles Bybit
- Cache des instruments obsolète

**Solutions :**
```python
# 1. Vérifier le formatage de la quantité
def format_quantity_correctly(symbol, quantity):
    # Récupérer les règles de précision
    instruments = bybit_client.get_instruments_info(symbol=symbol)
    lot_size_filter = instruments['list'][0]['lotSizeFilter']
    qty_step = float(lot_size_filter['qtyStep'])
    
    # Formater selon les règles
    formatted_qty = round(float(quantity) / qty_step) * qty_step
    return f"{formatted_qty:.6f}".rstrip('0').rstrip('.')

# 2. Vider le cache des instruments
smart_placer._symbol_precision_cache.clear()
```

#### ❌ "Order value exceeded lower limit"

**Symptômes :**
```
[MAKER-OPEN] Erreur placement ADAUSDT (retry 0): Erreur API Bybit : retCode=170140 retMsg="Order value exceeded lower limit"
```

**Causes possibles :**
- Valeur d'ordre insuffisante après formatage
- Règles spécifiques au symbole non respectées
- Calcul de quantité incorrect

**Solutions :**
```python
# 1. Vérifier la valeur finale après formatage
final_value = float(formatted_qty) * float(formatted_price)
if final_value < 5.0:
    # Ajuster la quantité
    required_qty = 5.0 / float(formatted_price)
    formatted_qty = format_quantity_correctly(symbol, required_qty)

# 2. Vérifier les règles spécifiques au symbole
symbol_rules = get_symbol_rules(symbol)
min_notional = symbol_rules.get('minNotional', 5.0)
```

### 2. Problèmes de liquidité

#### ❌ Classification de liquidité incorrecte

**Symptômes :**
- Offsets trop agressifs ou trop conservateurs
- Ordres non exécutés malgré des retries
- Prix calculés inappropriés

**Diagnostic :**
```python
# Vérifier les métriques de liquidité
orderbook = smart_placer._get_cached_orderbook(symbol, category)
liquidity = LiquidityClassifier.classify_liquidity(orderbook)

print(f"Spread relatif: {calculate_relative_spread(orderbook)}")
print(f"Volume top 10: {calculate_top_10_volume(orderbook)}")
print(f"Classification: {liquidity}")
```

**Solutions :**
```python
# 1. Ajuster les seuils de classification
MAKER_OFFSET_LEVELS = {
    "high_liquidity": 0.0001,    # Plus agressif
    "medium_liquidity": 0.0003,  # Plus agressif
    "low_liquidity": 0.0008      # Plus agressif
}

# 2. Ajouter des logs de debug
def classify_liquidity_with_debug(orderbook):
    spread = calculate_relative_spread(orderbook)
    volume = calculate_top_10_volume(orderbook)
    
    logger.debug(f"Liquidité debug - Spread: {spread:.6f}, Volume: {volume}")
    
    if spread < 0.0005 and volume > 2000000:  # Seuils ajustés
        return "high_liquidity"
    # ...
```

### 3. Problèmes de cache

#### ❌ Cache obsolète ou corrompu

**Symptômes :**
- Données d'order book incorrectes
- Prix calculés sur des données anciennes
- Erreurs de formatage

**Solutions :**
```python
# 1. Vider tous les caches
smart_placer._orderbook_cache.clear()
smart_placer._symbol_precision_cache.clear()

# 2. Forcer la récupération de données fraîches
orderbook = smart_placer.bybit_client.get_orderbook(symbol, category)

# 3. Vérifier la validité du cache
def validate_cache_entry(cache_key, cache_data, max_age_seconds=30):
    if cache_key not in cache_data:
        return False
    
    entry = cache_data[cache_key]
    age = time.time() - entry['timestamp']
    return age < max_age_seconds
```

### 4. Problèmes de performance

#### ❌ Temps d'exécution trop longs

**Symptômes :**
- Ordres non exécutés dans les temps
- Timeouts fréquents
- Bot qui ralentit

**Diagnostic :**
```python
# Mesurer les temps d'exécution
import time

start_time = time.time()
result = smart_placer.place_order_with_refresh(symbol, side, qty, category)
execution_time = time.time() - start_time

print(f"Temps d'exécution: {execution_time:.2f}s")
```

**Solutions :**
```python
# 1. Réduire les timeouts
ORDER_REFRESH_INTERVAL = 3  # Au lieu de 5
MAX_RETRIES = 2             # Au lieu de 3

# 2. Optimiser le cache
CACHE_DURATIONS = {
    "orderbook": 15,        # Plus court
    "instruments": 1800,    # Plus court
}

# 3. Utiliser des threads plus efficaces
THREAD_POOL_CONFIG = {
    "max_workers": 8,       # Plus de workers
    "thread_name_prefix": "fast_order_"
}
```

### 5. Problèmes de configuration

#### ❌ Configuration incorrecte

**Symptômes :**
- Erreurs de paramètres
- Comportement inattendu
- Échecs systématiques

**Vérifications :**
```python
# 1. Vérifier la configuration
def validate_config():
    assert ORDER_REFRESH_INTERVAL > 0, "ORDER_REFRESH_INTERVAL doit être > 0"
    assert MAX_RETRIES >= 0, "MAX_RETRIES doit être >= 0"
    assert MIN_ORDER_VALUE_USDT > 0, "MIN_ORDER_VALUE_USDT doit être > 0"
    
    for level, offset in MAKER_OFFSET_LEVELS.items():
        assert 0 < offset < 0.01, f"Offset {level} doit être entre 0 et 0.01"

# 2. Vérifier les paramètres d'entrée
def validate_inputs(symbol, side, qty, category):
    assert symbol and isinstance(symbol, str), "Symbol requis"
    assert side in ["Buy", "Sell"], "Side doit être Buy ou Sell"
    assert qty and float(qty) > 0, "Quantité doit être > 0"
    assert category in ["linear", "spot", "inverse"], "Category invalide"
```

## 🔍 Outils de diagnostic

### Script de diagnostic complet

```python
#!/usr/bin/env python3
"""
Script de diagnostic pour SmartOrderPlacer
"""

def diagnose_smart_order_placer(smart_placer, symbol="BTCUSDT"):
    """Diagnostic complet du SmartOrderPlacer"""
    
    print("🔍 DIAGNOSTIC SMART ORDER PLACER")
    print("=" * 50)
    
    # 1. Vérifier la configuration
    print("\n1. Configuration:")
    print(f"   ORDER_REFRESH_INTERVAL: {ORDER_REFRESH_INTERVAL}")
    print(f"   MAX_RETRIES: {MAX_RETRIES}")
    print(f"   MIN_ORDER_VALUE_USDT: {MIN_ORDER_VALUE_USDT}")
    print(f"   MAKER_OFFSET_LEVELS: {MAKER_OFFSET_LEVELS}")
    
    # 2. Tester la récupération d'order book
    print("\n2. Test order book:")
    try:
        orderbook = smart_placer._get_cached_orderbook(symbol, "linear")
        if orderbook:
            print(f"   ✅ Order book récupéré: {len(orderbook)} niveaux")
            print(f"   📊 Best bid: {orderbook[0]['price']}")
            print(f"   📊 Best ask: {orderbook[1]['price']}")
        else:
            print("   ❌ Échec récupération order book")
    except Exception as e:
        print(f"   ❌ Erreur order book: {e}")
    
    # 3. Tester la classification de liquidité
    print("\n3. Test classification liquidité:")
    try:
        if orderbook:
            liquidity = LiquidityClassifier.classify_liquidity(orderbook)
            print(f"   ✅ Liquidité: {liquidity}")
        else:
            print("   ❌ Pas d'order book pour test")
    except Exception as e:
        print(f"   ❌ Erreur classification: {e}")
    
    # 4. Tester le calcul de prix
    print("\n4. Test calcul prix:")
    try:
        if orderbook:
            price, level, offset = DynamicPriceCalculator.compute_dynamic_price(
                symbol, "Buy", orderbook
            )
            print(f"   ✅ Prix calculé: {price}")
            print(f"   📊 Niveau: {level}, Offset: {offset:.4f}")
        else:
            print("   ❌ Pas d'order book pour test")
    except Exception as e:
        print(f"   ❌ Erreur calcul prix: {e}")
    
    # 5. Vérifier le cache
    print("\n5. État du cache:")
    print(f"   📦 Order book cache: {len(smart_placer._orderbook_cache)} entrées")
    print(f"   📦 Instrument cache: {len(smart_placer._symbol_precision_cache)} entrées")
    
    # 6. Test de placement (simulation)
    print("\n6. Test placement (simulation):")
    try:
        # Simulation sans placement réel
        print("   🧪 Simulation d'un placement...")
        # Ici on pourrait faire un test avec un ordre très petit
        print("   ✅ Simulation réussie")
    except Exception as e:
        print(f"   ❌ Erreur simulation: {e}")
    
    print("\n" + "=" * 50)
    print("✅ Diagnostic terminé")

# Utilisation
if __name__ == "__main__":
    # Initialiser le SmartOrderPlacer
    smart_placer = SmartOrderPlacer(bybit_client, logger)
    
    # Lancer le diagnostic
    diagnose_smart_order_placer(smart_placer, "BTCUSDT")
```

### Monitoring en temps réel

```python
def monitor_smart_order_placer(smart_placer, duration_minutes=5):
    """Monitoring en temps réel du SmartOrderPlacer"""
    
    start_time = time.time()
    end_time = start_time + (duration_minutes * 60)
    
    metrics = {
        "orders_placed": 0,
        "orders_successful": 0,
        "orders_failed": 0,
        "avg_execution_time": 0,
        "retry_counts": [],
        "liquidity_levels": []
    }
    
    print(f"📊 Monitoring SmartOrderPlacer pendant {duration_minutes} minutes...")
    
    while time.time() < end_time:
        # Ici on pourrait intercepter les appels et collecter les métriques
        time.sleep(1)
    
    # Afficher les résultats
    print("\n📈 RÉSULTATS DU MONITORING:")
    print(f"   Ordres placés: {metrics['orders_placed']}")
    print(f"   Succès: {metrics['orders_successful']}")
    print(f"   Échecs: {metrics['orders_failed']}")
    print(f"   Taux de succès: {metrics['orders_successful']/max(metrics['orders_placed'], 1)*100:.1f}%")
    print(f"   Temps moyen: {metrics['avg_execution_time']:.2f}s")
```

## 🛠️ Outils de maintenance

### Nettoyage du cache

```python
def cleanup_caches(smart_placer):
    """Nettoyer les caches du SmartOrderPlacer"""
    
    print("🧹 Nettoyage des caches...")
    
    # Vider les caches
    smart_placer._orderbook_cache.clear()
    smart_placer._symbol_precision_cache.clear()
    
    print("✅ Caches vidés")
```

### Reset de configuration

```python
def reset_configuration():
    """Remettre la configuration par défaut"""
    
    print("🔄 Reset de la configuration...")
    
    # Recharger la configuration par défaut
    global ORDER_REFRESH_INTERVAL, MAX_RETRIES, MAKER_OFFSET_LEVELS
    ORDER_REFRESH_INTERVAL = 5
    MAX_RETRIES = 3
    MAKER_OFFSET_LEVELS = {
        "high_liquidity": 0.0002,
        "medium_liquidity": 0.0005,
        "low_liquidity": 0.0010
    }
    
    print("✅ Configuration remise par défaut")
```

## 📞 Support et escalade

### Niveaux de support

1. **Niveau 1 - Auto-diagnostic**
   - Utiliser les scripts de diagnostic
   - Vérifier les logs détaillés
   - Tester avec des montants faibles

2. **Niveau 2 - Configuration**
   - Ajuster les paramètres
   - Modifier les seuils de liquidité
   - Optimiser les timeouts

3. **Niveau 3 - Code**
   - Analyser le code source
   - Ajouter des logs de debug
   - Modifier la logique métier

4. **Niveau 4 - Infrastructure**
   - Vérifier la connectivité API
   - Analyser les performances réseau
   - Contacter le support Bybit

### Informations à fournir

Lors d'un problème, fournir :
- Logs complets avec timestamps
- Configuration actuelle
- Symboles concernés
- Fréquence du problème
- Étapes de reproduction
- Résultats des scripts de diagnostic

---

**Note** : Ce guide doit être mis à jour régulièrement selon les nouveaux problèmes rencontrés et les améliorations apportées au système.
