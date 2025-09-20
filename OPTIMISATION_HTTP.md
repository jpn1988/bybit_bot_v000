# Optimisation des Clients HTTP - Connexions Persistantes

## Problème Résolu

Avant cette optimisation, le bot créait un nouveau client HTTP à chaque requête avec `with httpx.Client()`, ce qui obligeait à refaire la connexion TLS à chaque fois. Cela ajoutait une latence inutile et consommait plus de CPU.

## Solution Implémentée

### 1. Gestionnaire de Clients HTTP Persistants (`src/http_client_manager.py`)

- **Pattern Singleton** : Une seule instance du gestionnaire pour toute l'application
- **Clients réutilisables** : 
  - `httpx.Client` pour les appels synchrones
  - `httpx.AsyncClient` pour les appels asynchrones
  - `aiohttp.ClientSession` pour les appels aiohttp
- **Configuration optimisée** :
  - `max_keepalive_connections=20` : Maintient 20 connexions ouvertes
  - `max_connections=100` : Pool maximum de 100 connexions
  - `keepalive_expiry=30.0` : Garde les connexions ouvertes 30 secondes
- **Fermeture automatique** : Nettoyage automatique via `atexit`

### 2. Refactorisation des Appels HTTP

#### Avant :
```python
with httpx.Client(timeout=timeout) as client:
    response = client.get(url, params=params)
```

#### Après :
```python
client = get_http_client(timeout=timeout)
response = client.get(url, params=params)
```

### 3. Fichiers Modifiés

- **`src/http_client_manager.py`** : Nouveau gestionnaire de clients persistants
- **`src/bybit_client.py`** : 1 occurrence refactorisée
- **`src/instruments.py`** : 1 occurrence refactorisée  
- **`src/bot.py`** : 4 occurrences refactorisées
- **`src/main.py`** : Ajout du nettoyage automatique

## Avantages

### Performance
- **Réduction de la latence** : Plus de handshake TLS à chaque requête
- **Économie CPU** : Moins d'établissement/fermeture de connexions
- **Réutilisation des connexions** : Pool de connexions maintenu

### Fiabilité
- **Fermeture propre** : Nettoyage automatique des ressources
- **Gestion d'erreurs** : Récupération automatique en cas de connexion fermée
- **Thread-safe** : Gestion sécurisée des accès concurrents

## Utilisation

### Client Synchrone
```python
from http_client_manager import get_http_client

client = get_http_client(timeout=10)
response = client.get("https://api.example.com/data")
```

### Client Asynchrone
```python
from http_client_manager import get_async_http_client

async def fetch_data():
    client = await get_async_http_client(timeout=10)
    response = await client.get("https://api.example.com/data")
```

### Fermeture Manuelle (optionnel)
```python
from http_client_manager import close_all_http_clients

# Fermeture explicite si nécessaire
close_all_http_clients()
```

## Tests de Validation

```bash
# Test du gestionnaire
cd src
python -c "from http_client_manager import get_http_client; client = get_http_client(); print('✅ Client créé:', type(client).__name__)"

# Test de réutilisation
python -c "from http_client_manager import get_http_client; print('✅ Même instance:', get_http_client() is get_http_client())"

# Test de requête HTTP
python -c "from http_client_manager import get_http_client; resp = get_http_client().get('https://httpbin.org/get'); print('✅ Status:', resp.status_code)"
```

## Impact sur le Code Existant

- **Compatibilité** : Aucun changement dans la logique métier
- **Interface identique** : Les appels HTTP fonctionnent exactement pareil
- **Transparence** : L'optimisation est invisible pour l'utilisateur final
- **Maintenance** : Code plus propre et centralisé

## Notes Techniques

- Les clients sont créés à la demande (lazy loading)
- Le nettoyage automatique via `atexit` garantit la fermeture propre
- En cas d'erreur de connexion, un nouveau client est automatiquement créé
- Compatible avec tous les patterns d'usage existants du code

Cette optimisation améliore les performances du bot sans aucun impact sur la fonctionnalité existante.
