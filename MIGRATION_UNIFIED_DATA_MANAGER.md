# Migration - unified_data_manager.py

## ✅ Changement effectué

Le fichier `unified_data_manager.py` a été **simplifié de 47%** : de **473 lignes à 251 lignes**.

## 🎯 Objectif

Supprimer les alias de compatibilité qui créaient de la confusion et favoriser l'accès direct aux composants spécialisés via les propriétés `fetcher`, `storage`, et `validator`.

---

## 📋 Migration des APIs

### ❌ ANCIENNE API (supprimée)

```python
# Accès indirect via les alias
funding_map = data_manager.fetch_funding_map(url, "linear", 10)
spread_data = data_manager.fetch_spread_data(url, symbols, 10, "linear")

# Alias dépréciés
data_manager.update_funding_data(symbol, funding, volume, ...)
data = data_manager.get_funding_data(symbol)

# Propriétés legacy
categories = data_manager.symbol_categories
linear = data_manager.linear_symbols
```

### ✅ NOUVELLE API (à utiliser)

```python
# Accès DIRECT aux composants via les propriétés
funding_map = data_manager.fetcher.fetch_funding_map(url, "linear", 10)
spread_data = data_manager.fetcher.fetch_spread_data(url, symbols, 10, "linear")

# Value Objects (API moderne)
data_manager.storage.set_funding_data_object(FundingData(...))
funding_obj = data_manager.storage.get_funding_data_object(symbol)

# Accès direct au storage
categories = data_manager.storage.symbol_categories
linear = data_manager.storage.get_linear_symbols()
```

---

## 🔄 Guide de migration détaillé

### 1. Récupération de données (DataFetcher)

| Ancien | Nouveau |
|--------|---------|
| `data_manager.fetch_funding_map(...)` | `data_manager.fetcher.fetch_funding_map(...)` |
| `data_manager.fetch_spread_data(...)` | `data_manager.fetcher.fetch_spread_data(...)` |
| `data_manager.fetch_funding_data_parallel(...)` | `data_manager.fetcher.fetch_funding_data_parallel(...)` |

### 2. Stockage de données (DataStorage)

| Ancien | Nouveau |
|--------|---------|
| `data_manager.update_funding_data(...)` | `data_manager.storage.set_funding_data_object(FundingData(...))` |
| `data_manager.get_funding_data(symbol)` | `data_manager.storage.get_funding_data_object(symbol)` |
| `data_manager.get_all_funding_data()` | `data_manager.storage.get_all_funding_data_objects()` |
| `data_manager.update_realtime_data(...)` | `data_manager.storage.update_realtime_data(...)` |
| `data_manager.get_realtime_data(symbol)` | `data_manager.storage.get_realtime_data(symbol)` |
| `data_manager.update_original_funding_data(...)` | `data_manager.storage.update_original_funding_data(...)` |
| `data_manager.get_original_funding_data(symbol)` | `data_manager.storage.get_original_funding_data(symbol)` |

### 3. Gestion des symboles (DataStorage)

| Ancien | Nouveau |
|--------|---------|
| `data_manager.set_symbol_lists(linear, inverse)` | `data_manager.storage.set_symbol_lists(linear, inverse)` |
| `data_manager.get_linear_symbols()` | `data_manager.storage.get_linear_symbols()` |
| `data_manager.get_inverse_symbols()` | `data_manager.storage.get_inverse_symbols()` |
| `data_manager.get_all_symbols()` | `data_manager.storage.get_all_symbols()` |
| `data_manager.add_symbol_to_category(...)` | `data_manager.storage.add_symbol_to_category(...)` |
| `data_manager.remove_symbol_from_category(...)` | `data_manager.storage.remove_symbol_from_category(...)` |

### 4. Propriétés (DataStorage)

| Ancien | Nouveau |
|--------|---------|
| `data_manager.symbol_categories` | `data_manager.storage.symbol_categories` |
| `data_manager.linear_symbols` | `data_manager.storage.linear_symbols` |
| `data_manager.inverse_symbols` | `data_manager.storage.inverse_symbols` |
| `data_manager.funding_data` | `data_manager.storage.funding_data` |
| `data_manager.realtime_data` | `data_manager.storage.realtime_data` |

---

## 📦 Value Objects recommandés

Privilégiez l'utilisation des **Value Objects** pour manipuler les données :

### Exemple avec FundingData

```python
from models.funding_data import FundingData

# Créer un Value Object
funding_obj = FundingData(
    symbol="BTCUSDT",
    funding_rate=0.0001,
    volume_24h=1000000000,
    next_funding_time="1h 30m",
    spread_pct=0.001,
    volatility_pct=0.003
)

# Stocker
data_manager.storage.set_funding_data_object(funding_obj)

# Récupérer
funding_obj = data_manager.storage.get_funding_data_object("BTCUSDT")

# Accéder aux propriétés
print(funding_obj.symbol)           # "BTCUSDT"
print(funding_obj.funding_rate)     # 0.0001
print(funding_obj.volume_24h)       # 1000000000
```

---

## 📊 Fichiers modifiés

Les fichiers suivants ont été mis à jour pour utiliser la nouvelle API :

1. ✅ `src/watchlist_helpers/data_preparer.py`
2. ✅ `src/watchlist_helpers/filter_applier.py`
3. ✅ `src/bot_starter.py`
4. ✅ `src/candidate_monitor.py`
5. ✅ `src/opportunity_detector.py`
6. ✅ `src/opportunity_manager.py`
7. ✅ `src/callback_manager.py`
8. ✅ `src/display_manager.py`
9. ✅ `src/table_formatter.py`
10. ✅ `tests/test_unified_data_manager.py`

---

## ✅ Avantages de la nouvelle API

### 1. **Clarté**
- Il est évident quel composant est utilisé (`fetcher`, `storage`, `validator`)
- Pas de confusion entre les différentes méthodes

### 2. **Lisibilité**
- Moins de code dans `unified_data_manager.py` (251 lignes vs 473)
- Code plus facile à maintenir

### 3. **Cohérence**
- Une seule façon de faire les choses (pas d'alias)
- Pattern uniforme : `data_manager.composant.méthode()`

### 4. **Type Safety**
- Les Value Objects offrent une meilleure validation des données
- Les propriétés sont typées

---

## 🧪 Tests

Tous les tests unitaires passent après la migration :

```bash
$ python -m pytest tests/test_unified_data_manager.py -v
============================= 21 passed in 2.70s ==============================
```

---

## 📚 Documentation complémentaire

- [`ARCHITECTURE.md`](ARCHITECTURE.md) - Architecture globale du bot
- [`unified_data_manager_README.md`](src/unified_data_manager_README.md) - Documentation technique détaillée
- [`models/funding_data.py`](src/models/funding_data.py) - Documentation des Value Objects

---

**Date de migration** : 9 octobre 2025  
**Auteur** : Refactoring pour améliorer la lisibilité du code

