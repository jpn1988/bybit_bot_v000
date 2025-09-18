# 🚀 Optimisations Volatilité - Bot Bybit

## Résumé des améliorations

Ce document détaille les optimisations de performance appliquées au calcul de volatilité du bot Bybit pour réduire drastiquement le temps de traitement.

## 🎯 Objectif

Réduire fortement le temps de calcul de volatilité en parallélisant les appels API avec async/await, tout en respectant le rate limiting (concurrence contrôlée).

## 📊 Problème initial

**Avant optimisation :**
```python
# Traitement séquentiel - TRÈS LENT
for symbol in symbols_data:
    vol_pct = compute_5m_range_pct(bybit_client, symbol)  # Un appel à la fois
```

- 50 symboles = 15-25 secondes
- 100 symboles = 30-50 secondes
- Chaque symbole attend le précédent

## ✅ Solution implémentée

**Après optimisation :**
```python
# Traitement parallèle contrôlé (semaphore) + rate limiter
sem = asyncio.Semaphore(5)
async def compute_volatility_batch_async(bybit_client, symbols, timeout=10):
    async with aiohttp.ClientSession() as session:
        async def limited(sym):
            async with sem:
                return await _compute_single_volatility_async(session, base_url, sym)
        results = await asyncio.gather(*[limited(s) for s in symbols], return_exceptions=True)
```

- 50 symboles = typiquement 2-6 secondes (selon réseau/API)
- 100 symboles = typiquement 4-12 secondes (selon réseau/API)
- Symboles traités en parallèle avec concurrence plafonnée (5)

## 🔧 Modifications techniques

### 1. Nouvelle fonction async dans `volatility.py`

```python
async def compute_volatility_batch_async(bybit_client, symbols: List[str], timeout: int = 10) -> Dict[str, Optional[float]]:
    """
    Calcule la volatilité 5 minutes pour une liste de symboles en parallèle.
    OPTIMISATION: Utilise aiohttp et asyncio.gather() pour paralléliser les appels API.
    """
```

**Fonctionnalités :**
- `aiohttp.ClientSession` pour les requêtes HTTP asynchrones
- `asyncio.gather()` pour exécuter les tâches en parallèle
- Concurrence plafonnée via `asyncio.Semaphore(5)`
- Rate limiter global pour lisser les appels
- Gestion d'erreur robuste avec `return_exceptions=True`
- Même logique de calcul que la version synchrone

### 2. Fonction helper async

```python
async def _compute_single_volatility_async(session: aiohttp.ClientSession, base_url: str, symbol: str) -> Optional[float]:
    """
    Calcule la volatilité pour un seul symbole de manière asynchrone.
    Fonction helper pour la parallélisation.
    """
```

**Caractéristiques :**
- Réutilise la session HTTP pour l'efficacité
- Même logique de calcul (plage high-low sur 5 bougies 1m)
- Gestion d'erreur identique

### 3. Refactorisation de `filter_by_volatility()`

**Nouvelle approche :**
```python
async def filter_by_volatility_async(...):
    # Séparer cache / à calculer
    # Calcul batch async avec semaphore
```

**Améliorations :**
- Séparation intelligente entre cache et calcul
- Traitement par batch de tous les symboles non-cachés
- Mise à jour du cache en une seule fois
- Logs informatifs sur le traitement parallèle

### 4. Compatibilité maintenue

```python
def filter_by_volatility(...):
    return asyncio.run(filter_by_volatility_async(...))
```

**Avantages :**
- Aucun changement d'interface publique
- Compatibilité totale avec le code existant
- Transition transparente vers l'async

## 📈 Résultats de performance

### Temps de calcul
- 50 symboles : 2-6 secondes (indicatif)
- Amélioration : 60-90% selon conditions réseau

### Scalabilité
- 100 symboles : 4-12 secondes (indicatif)
- Parallélisation contrôlée

### Utilisation des ressources
- Avant : 1 requête à la fois, CPU inutilisé
- Après : Parallélisation contrôlée (5 simultanées), CPU et réseau mieux utilisés

## 🛡️ Gestion d'erreur

### Robustesse
```python
results = await asyncio.gather(*tasks, return_exceptions=True)
for i, result in enumerate(results):
    if isinstance(result, Exception):
        volatility_results[symbol] = None
```

**Caractéristiques :**
- `return_exceptions=True` : Une erreur sur un symbole n'arrête pas les autres
- Fallback sur `None` pour les symboles en erreur
- Logs informatifs sur les échecs
- Cache mis à jour seulement pour les succès

### Rate limiting
- Timeout configurable (défaut: 10 secondes)
- Session HTTP réutilisée pour l'efficacité
- Gestion des erreurs HTTP (status >= 400)
- Gestion des erreurs API (retCode != 0)
- Rate limiter configurable via env (`PUBLIC_HTTP_MAX_CALLS_PER_SEC`, `PUBLIC_HTTP_WINDOW_SECONDS`)

## 🔄 Cache intelligent

### Optimisation du cache
```python
if cached_data and is_cache_valid(...):
    use cache
else:
    symbols_to_calculate.append(symbol)
```

**Avantages :**
- Évite les recalculs inutiles
- Traite seulement les symboles non-cachés en parallèle
- TTL de 60-120 secondes pour la fraîcheur des données

## 📦 Dépendances

```txt
aiohttp
```

## 🚀 Utilisation

### Aucun changement requis
```bash
python src/bot.py
```

### Logs informatifs
```
🔎 Calcul volatilité async (parallèle, sem=5) pour 50 symboles…
✅ Calcul volatilité async: gardés=45 | rejetés=5 (seuils: min=0.20% | max=0.70%)
```

## 📝 Notes techniques

### Compatibilité
- Compatible testnet et production
- Interface publique inchangée

### Performance
- Parallélisation limitée par la bande passante réseau et le rate limit
- Session HTTP réutilisée pour l'efficacité
- Timeout configurable pour éviter les blocages
- Gestion gracieuse des erreurs partielles

### Maintenance
- Code modulaire avec fonctions helper
- Documentation alignée au code actuel
- Logs informatifs pour le debugging
