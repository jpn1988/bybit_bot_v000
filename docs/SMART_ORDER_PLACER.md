# 📋 Documentation SmartOrderPlacer

## 🎯 Vue d'ensemble

Le `SmartOrderPlacer` est un système intelligent de placement d'ordres qui garantit des ordres **100% maker** avec des prix dynamiques basés sur la liquidité du marché. Il remplace les placements d'ordres directs par une logique sophistiquée qui optimise l'exécution et minimise les frais.

## 🏗️ Architecture

```
SmartOrderPlacer
├── LiquidityClassifier     # Classification de la liquidité du marché
├── DynamicPriceCalculator  # Calcul des prix dynamiques
├── OrderResult            # Structure de résultat des ordres
└── SmartOrderPlacer       # Classe principale
```

## 📊 Composants principaux

### 1. LiquidityClassifier

**Rôle** : Analyse l'order book pour déterminer le niveau de liquidité du marché.

**Méthodes** :
- `classify_liquidity(orderbook)` : Retourne `high_liquidity`, `medium_liquidity`, ou `low_liquidity`

**Logique de classification** :
```python
# Calcul du spread relatif
relative_spread = (best_ask - best_bid) / best_bid

# Calcul du volume des 10 premiers niveaux
top_10_volume = sum(volume for level in orderbook[:10])

# Classification
if relative_spread < 0.001 and top_10_volume > 1000000:
    return "high_liquidity"    # Offset: 0.02%
elif relative_spread < 0.005 and top_10_volume > 100000:
    return "medium_liquidity"  # Offset: 0.05%
else:
    return "low_liquidity"     # Offset: 0.10%
```

### 2. DynamicPriceCalculator

**Rôle** : Calcule le prix optimal pour un ordre maker basé sur la liquidité.

**Méthodes** :
- `compute_dynamic_price(symbol, side, orderbook)` : Retourne `(price, liquidity_level, offset_percent)`

**Logique de calcul** :
```python
# Classification de la liquidité
liquidity = LiquidityClassifier.classify_liquidity(orderbook)

# Récupération de l'offset correspondant
offset = MAKER_OFFSET_LEVELS[liquidity]

# Calcul du prix
if side == "Buy":
    price = best_bid * (1 + offset)  # Au-dessus du bid
else:
    price = best_ask * (1 - offset)  # En-dessous de l'ask
```

### 3. OrderResult

**Structure** : NamedTuple contenant le résultat d'un placement d'ordre.

```python
OrderResult = NamedTuple('OrderResult', [
    ('success', bool),           # Succès de l'opération
    ('order_id', Optional[str]), # ID de l'ordre (si succès)
    ('price', Optional[float]),  # Prix de l'ordre
    ('offset_percent', Optional[float]), # Offset appliqué
    ('liquidity_level', Optional[str]),  # Niveau de liquidité
    ('retry_count', int),        # Nombre de tentatives
    ('execution_time', Optional[float])  # Temps d'exécution
])
```

## 🔄 Cycle de vie d'un ordre

### 1. Placement initial
```python
# 1. Récupération de l'order book
orderbook = self._get_cached_orderbook(symbol, category)

# 2. Calcul du prix dynamique
price, liquidity_level, offset_percent = self._compute_dynamic_price(symbol, side, orderbook)

# 3. Placement de l'ordre avec PostOnly
response = self._place_order_sync(symbol, side, qty, price, category)
```

### 2. Vérification du minimum
```python
# Vérification que l'ordre respecte le minimum de 5 USDT
min_order_value_usdt = 5.0
order_value = float(qty) * float(formatted_price)

if order_value < min_order_value_usdt:
    # Ajustement automatique de la quantité
    required_qty = min_order_value_usdt / float(formatted_price)
    qty = self._format_quantity_for_symbol(symbol, required_qty)
```

### 3. Surveillance et refresh
```python
# Attente de l'exécution (5 secondes max)
if not self._wait_for_execution(order_id, symbol, category, price, offset_percent, liquidity_level, retry):
    # Annulation et remplacement avec prix ajusté
    self.bybit_client.cancel_order(symbol, order_id, category)
    new_price = self._adjust_price_for_retry(current_price, side, base_offset, retry)
    # Nouvelle tentative...
```

## ⚙️ Configuration

### Paramètres clés

```python
# Intervalles de refresh
ORDER_REFRESH_INTERVAL = 5  # secondes
MAX_RETRIES = 3             # tentatives max

# Offsets par niveau de liquidité
MAKER_OFFSET_LEVELS = {
    "high_liquidity": 0.0002,    # 0.02%
    "medium_liquidity": 0.0005,  # 0.05%
    "low_liquidity": 0.0010      # 0.10%
}

# Minimum requis par Bybit
MIN_ORDER_VALUE_USDT = 5.0
```

### Cache des données

```python
# Cache pour les order books (évite les appels API répétés)
self._orderbook_cache = {}

# Cache pour les informations d'instruments (tickSize, etc.)
self._instrument_cache = {}
```

## 🚀 Utilisation

### Intégration dans SchedulerManager

```python
# Initialisation
self.smart_placer = SmartOrderPlacer(bybit_client, logger)

# Placement d'ordre perp
result = self.smart_placer.place_order_with_refresh(
    symbol=symbol,
    side=side,
    qty=qty,
    category="linear"
)

if result.success:
    self.logger.info(f"✅ Ordre perp placé: {result.order_id}")
else:
    self.logger.error(f"❌ Échec placement perp: {result}")
```

### Intégration dans SpotHedgeManager

```python
# Placement d'ordre spot
result = self.smart_placer.place_order_with_refresh(
    symbol=symbol,
    side=side,
    qty=spot_qty,
    category="spot"
)

if result.success:
    self.logger.info(f"✅ Hedge spot placé: {result.order_id}")
```

## 📈 Avantages

### 1. **100% Maker**
- Tous les ordres utilisent `PostOnly` ou `timeInForce="PostOnly"`
- Aucun risque de devenir taker
- Frais réduits (maker rebate)

### 2. **Prix dynamiques**
- Adaptation automatique à la liquidité du marché
- Meilleure probabilité d'exécution
- Optimisation des spreads

### 3. **Refresh intelligent**
- Annulation automatique des ordres non exécutés
- Ajustement des prix pour les retries
- Limitation du nombre de tentatives

### 4. **Respect des limites**
- Vérification du minimum de 5 USDT
- Formatage correct des prix et quantités
- Gestion des erreurs Bybit

## 🔧 Maintenance

### Logs importants

```python
# Placement d'ordre
[MAKER-OPEN] {symbol} {side} | price={price} | offset={offset} | retry={n}

# Exécution réussie
[MAKER-OPEN] Executed fully after {time}s ✅

# Échec après retries
[MAKER-OPEN] Échec placement {symbol} (retry {n}): {error}
```

### Monitoring

- **Taux de succès** : Pourcentage d'ordres exécutés
- **Temps d'exécution** : Durée moyenne d'exécution
- **Retries** : Nombre moyen de tentatives par ordre
- **Liquidité** : Distribution des niveaux de liquidité

## 🐛 Dépannage

### Erreurs courantes

1. **"Order does not meet minimum order value 5USDT"**
   - **Cause** : Quantité trop petite après formatage
   - **Solution** : Ajustement automatique de la quantité

2. **"Order quantity has too many decimals"**
   - **Cause** : Précision incorrecte pour le symbole
   - **Solution** : Formatage selon les règles Bybit

3. **"Order value exceeded lower limit"**
   - **Cause** : Valeur d'ordre insuffisante
   - **Solution** : Vérification et ajustement du minimum

### Debug

```python
# Activation des logs détaillés
self.logger.setLevel(logging.DEBUG)

# Vérification du cache
print(f"Order book cache: {len(self._orderbook_cache)} entrées")
print(f"Instrument cache: {len(self._instrument_cache)} entrées")
```

## 📚 Exemples d'utilisation

### Exemple complet

```python
# Initialisation
smart_placer = SmartOrderPlacer(bybit_client, logger)

# Placement d'ordre
result = smart_placer.place_order_with_refresh(
    symbol="BTCUSDT",
    side="Buy",
    qty="0.001",
    category="linear"
)

# Vérification du résultat
if result.success:
    print(f"✅ Ordre placé: {result.order_id}")
    print(f"💰 Prix: {result.price}")
    print(f"📊 Liquidité: {result.liquidity_level}")
    print(f"⏱️ Temps: {result.execution_time}s")
else:
    print(f"❌ Échec après {result.retry_count} tentatives")
```

## 🔮 Évolutions futures

### Améliorations possibles

1. **Machine Learning** : Prédiction de la liquidité basée sur l'historique
2. **Multi-exchange** : Support d'autres exchanges
3. **Stratégies avancées** : Ordres iceberg, TWAP, etc.
4. **Analytics** : Dashboard de performance en temps réel

### Configuration avancée

```python
# Configuration par symbole
SYMBOL_CONFIGS = {
    "BTCUSDT": {
        "min_offset": 0.0001,
        "max_offset": 0.0010,
        "refresh_interval": 3
    },
    "ETHUSDT": {
        "min_offset": 0.0002,
        "max_offset": 0.0020,
        "refresh_interval": 5
    }
}
```

---

## 📞 Support

Pour toute question ou problème :
1. Vérifier les logs détaillés
2. Consulter la documentation Bybit
3. Tester avec des montants faibles
4. Contacter l'équipe de développement

**Version** : 1.0.0  
**Dernière mise à jour** : 2025-10-30  
**Auteur** : Équipe de développement Bybit Bot
