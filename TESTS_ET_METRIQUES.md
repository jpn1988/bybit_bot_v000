# Tests Automatiques et Métriques - Bot Bybit

## 🧪 Tests Automatiques

### Installation des dépendances de test

```bash
pip install pytest pytest-mock pytest-asyncio
```

### Exécution des tests

```bash
# Tous les tests
python run_tests.py

# Test spécifique
python run_tests.py test_bybit_client.py
python run_tests.py test_config.py
python run_tests.py test_filtering.py
python run_tests.py test_metrics.py

# Avec pytest directement
pytest tests/ -v
```

### Tests implémentés

#### 1. **Test de connexion testnet et récupération du solde** (`test_bybit_client.py`)
- ✅ Initialisation du client avec credentials valides
- ✅ Gestion des erreurs sans credentials
- ✅ URLs testnet/mainnet correctes
- ✅ Récupération du solde avec succès (mocké)
- ✅ Gestion des erreurs HTTP et API
- ✅ Authentification échouée

#### 2. **Test de vérification du filtrage des paires** (`test_filtering.py`)
- ✅ Filtrage par catégorie (linear/inverse/both)
- ✅ Filtres include/exclude
- ✅ Filtre regex (insensible à la casse)
- ✅ Gestion des regex invalides
- ✅ Limite du nombre de résultats
- ✅ Combinaison de plusieurs filtres
- ✅ Résultats vides

#### 3. **Test de chargement et validation de la config** (`test_config.py`)
- ✅ Chargement avec variables d'environnement valides
- ✅ Valeurs par défaut
- ✅ Overrides via variables d'environnement
- ✅ Conversion des chaînes vides en None
- ✅ Gestion des valeurs numériques invalides
- ✅ Détection des variables d'environnement inconnues

## 📊 Système de Métriques

### Métriques collectées

#### **API Calls**
- Nombre total d'appels API
- Nombre d'erreurs API
- Taux d'erreur (pourcentage)
- Latence moyenne (millisecondes)

#### **Filtres**
- Nombre de paires gardées par filtre
- Nombre de paires rejetées par filtre
- Taux de succès des filtres (pourcentage)
- Détails par type de filtre (funding, spread, volatilité, etc.)

#### **WebSocket**
- Nombre de connexions établies
- Nombre de reconnexions
- Nombre d'erreurs WebSocket

#### **Système**
- Uptime du bot (heures)
- Dernière mise à jour des métriques

### Affichage des métriques

Les métriques sont automatiquement affichées dans les logs toutes les **5 minutes** avec le format suivant :

```
📊 MÉTRIQUES BOT:
   ⏱️  Uptime: 2.3h
   🔌 API: 45 appels | 2.2% erreurs | 125ms latence
   🎯 Filtres: 25 gardées | 120 rejetées | 17.2% succès
   🌐 WebSocket: 3 connexions | 1 reconnexions | 0 erreurs
   📈 Détails par filtre:
      funding_volume_time: 15 gardées | 30 rejetées | 33.3% succès
      spread: 12 gardées | 3 rejetées | 80.0% succès
      volatility: 10 gardées | 2 rejetées | 83.3% succès
```

### Configuration du monitoring

Le monitoring des métriques est configuré dans `src/bot.py` :

```python
# Démarrer le monitoring des métriques (toutes les 5 minutes)
start_metrics_monitoring(interval_minutes=5)
```

### API des métriques

#### Enregistrement manuel
```python
from metrics import record_api_call, record_filter_result, record_ws_connection, record_ws_error

# Enregistrer un appel API
record_api_call(latency=0.5, success=True)

# Enregistrer les résultats d'un filtre
record_filter_result("funding", kept=10, rejected=5)

# Enregistrer une connexion WebSocket
record_ws_connection(connected=True)

# Enregistrer une erreur WebSocket
record_ws_error()
```

#### Récupération des métriques
```python
from metrics import get_metrics_summary

metrics = get_metrics_summary()
print(f"Uptime: {metrics['uptime_seconds']}s")
print(f"API calls: {metrics['api_calls_total']}")
print(f"Error rate: {metrics['api_error_rate_percent']}%")
```

#### Affichage immédiat
```python
from metrics_monitor import log_metrics_now

# Forcer l'affichage des métriques maintenant
log_metrics_now()
```

## 🔧 Intégration dans le code existant

### Client Bybit (`src/bybit_client.py`)
- ✅ Enregistrement automatique des appels API
- ✅ Mesure de la latence
- ✅ Détection des succès/erreurs

### Bot principal (`src/bot.py`)
- ✅ Enregistrement des résultats de filtres
- ✅ Monitoring des connexions WebSocket
- ✅ Démarrage automatique du monitoring

### Modules de métriques
- ✅ `src/metrics.py` : Collecteur de métriques thread-safe
- ✅ `src/metrics_monitor.py` : Monitoring périodique et affichage

## 📈 Avantages

### **Tests automatiques**
- ✅ Vérification automatique des changements
- ✅ Détection précoce des régressions
- ✅ Documentation vivante du comportement attendu
- ✅ Confiance dans les déploiements

### **Métriques de monitoring**
- ✅ Visibilité sur la santé du bot
- ✅ Détection des problèmes de performance
- ✅ Optimisation basée sur les données
- ✅ Alertes proactives sur les erreurs

## 🚀 Utilisation

1. **Installer les dépendances** :
   ```bash
   pip install -r requirements.txt
   ```

2. **Exécuter les tests** :
   ```bash
   python run_tests.py
   ```

3. **Lancer le bot** (les métriques sont automatiques) :
   ```bash
   python src/bot.py
   ```

4. **Surveiller les logs** pour voir les métriques toutes les 5 minutes.

## 📝 Notes

- Les tests utilisent des mocks pour éviter les appels API réels
- Les métriques sont thread-safe et ne ralentissent pas le bot
- Le monitoring peut être configuré pour des intervalles différents
- Toutes les métriques sont en mémoire (pas de base de données requise)
