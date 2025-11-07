# 📚 Guide des Context Managers

## 🎯 Vue d'ensemble

Les context managers permettent une gestion automatique des ressources et un code plus propre. Le bot Bybit implémente le support des context managers pour toutes ses classes principales.

## 🚀 Utilisation Asynchrone (Recommandée)

### BotOrchestrator

```python
import asyncio
from factories.bot_factory import BotFactory
from logging_setup import setup_logging

async def main():
    logger = setup_logging()
    factory = BotFactory(logger=logger)
    bot = factory.create_bot(testnet=True)
    
    # Utilisation du context manager asynchrone
    async with bot as bot_instance:
        print("Bot démarré automatiquement")
        # Le bot fonctionne ici
        await asyncio.sleep(10)
        print("Bot en cours d'exécution...")
    
    # Le bot s'arrête automatiquement ici

asyncio.run(main())
```

### AsyncBotRunner

```python
import asyncio
from factories.bot_factory import BotFactory
from logging_setup import setup_logging

async def main():
    logger = setup_logging()
    factory = BotFactory(logger=logger)
    runner = factory.create_async_runner(testnet=True)
    
    # Utilisation du context manager asynchrone
    async with runner as runner_instance:
        print("AsyncBotRunner démarré automatiquement")
        # L'event loop est géré automatiquement
        await asyncio.sleep(10)
        print("Runner en cours d'exécution...")
    
    # Le runner s'arrête automatiquement ici

asyncio.run(main())
```

## 🔄 Utilisation Synchrone

### DataManager

```python
from factories.bot_factory import BotFactory
from logging_setup import setup_logging

def main():
    logger = setup_logging()
    factory = BotFactory(logger=logger)
    bot = factory.create_bot(testnet=True)
    
    # Utilisation du context manager synchrone
    with bot.data_manager as data_manager:
        print("DataManager dans le contexte")
        # Opérations de données ici
        print("Gestion des données...")
    
    # Nettoyage automatique des ressources

main()
```

### MonitoringManager

```python
from factories.bot_factory import BotFactory
from logging_setup import setup_logging

def main():
    logger = setup_logging()
    factory = BotFactory(logger=logger)
    bot = factory.create_bot(testnet=True)
    
    # Utilisation du context manager synchrone
    with bot.monitoring_manager as monitoring_manager:
        print("MonitoringManager dans le contexte")
        # Opérations de monitoring ici
        print("Surveillance en cours...")
    
    # Arrêt automatique de la surveillance

main()
```

## 🔗 Context Managers Imbriqués

```python
import asyncio
from factories.bot_factory import BotFactory
from logging_setup import setup_logging

async def main():
    logger = setup_logging()
    factory = BotFactory(logger=logger)
    bot = factory.create_bot(testnet=True)
    
    # Context manager principal
    async with bot as bot_instance:
        print("Bot principal démarré")
        
        # Context manager pour les données
        with bot_instance.data_manager as data_manager:
            print("DataManager dans le contexte")
            
            # Context manager pour le monitoring
            with bot_instance.monitoring_manager as monitoring_manager:
                print("MonitoringManager dans le contexte")
                
                # Opérations complexes avec gestion automatique
                print("Opérations complexes...")
                await asyncio.sleep(5)
                
                print("Opérations terminées")
            
            print("MonitoringManager nettoyé")
        
        print("DataManager nettoyé")
    
    print("Bot principal arrêté")

asyncio.run(main())
```

## 🛡️ Gestion d'Erreurs

Les context managers nettoient automatiquement les ressources même en cas d'exception :

```python
import asyncio
from factories.bot_factory import BotFactory
from logging_setup import setup_logging

async def main():
    logger = setup_logging()
    factory = BotFactory(logger=logger)
    bot = factory.create_bot(testnet=True)
    
    try:
        async with bot as bot_instance:
            print("Bot démarré")
            await asyncio.sleep(2)
            
            # Simulation d'une erreur
            raise ValueError("Erreur intentionnelle")
            
    except ValueError as e:
        print(f"Erreur capturée: {e}")
        print("Le bot a été arrêté automatiquement malgré l'erreur")

asyncio.run(main())
```

## 📋 Avantages des Context Managers

### ✅ Gestion Automatique des Ressources
- **Démarrage automatique** : Le bot démarre à l'entrée du contexte
- **Arrêt automatique** : Le bot s'arrête à la sortie du contexte
- **Nettoyage garanti** : Les ressources sont nettoyées même en cas d'erreur

### ✅ Code Plus Propre
- **Moins de code boilerplate** : Pas besoin de gérer manuellement start/stop
- **Structure claire** : Les limites du contexte sont visibles
- **Gestion d'erreurs simplifiée** : Les exceptions sont propagées naturellement

### ✅ Sécurité Renforcée
- **Pas de fuites de ressources** : Garantie de nettoyage
- **Gestion d'erreurs robuste** : Les erreurs n'empêchent pas le nettoyage
- **État cohérent** : Le bot est toujours dans un état valide

## 🔧 Implémentation Technique

### Méthodes Asynchrones
- `__aenter__()` : Point d'entrée asynchrone
- `__aexit__()` : Point de sortie asynchrone

### Méthodes Synchrones
- `__enter__()` : Point d'entrée synchrone
- `__exit__()` : Point de sortie synchrone

### Gestion des Exceptions
- Les exceptions sont propagées par défaut (`return False`)
- Le nettoyage se fait même en cas d'exception
- Les erreurs de nettoyage sont loggées mais n'empêchent pas la sortie

## 🎯 Bonnes Pratiques

### 1. Utilisez les Context Managers Asynchrones
```python
# ✅ Bon
async with bot as bot_instance:
    # Utilisation du bot
    pass

# ❌ Évitez
bot.start()
try:
    # Utilisation du bot
    pass
finally:
    bot.stop()
```

### 2. Imbriquez les Context Managers
```python
# ✅ Bon - Gestion fine des ressources
async with bot as bot_instance:
    with bot_instance.data_manager as data_manager:
        # Opérations spécifiques aux données
        pass
```

### 3. Gérez les Exceptions Appropriément
```python
# ✅ Bon - Laissez les exceptions se propager
async with bot as bot_instance:
    # Le context manager gère le nettoyage
    raise SomeError("Erreur métier")
```

### 4. Utilisez des Noms Descriptifs
```python
# ✅ Bon
async with bot as trading_bot:
    # Utilisation claire du bot
    pass
```

## 🚨 Limitations

### Context Managers Synchrones
- Les context managers synchrones pour `BotOrchestrator` et `AsyncBotRunner` ne démarrent pas automatiquement
- Utilisez les versions asynchrones pour un démarrage automatique

### Gestion des Exceptions
- Les erreurs de nettoyage sont loggées mais n'empêchent pas la sortie
- Les exceptions métier sont propagées normalement

## 📖 Exemples Complets

Voir le fichier `examples/context_manager_usage.py` pour des exemples complets d'utilisation des context managers.

## 🔗 Voir Aussi

- [Guide de démarrage](GUIDE_DEMARRAGE_BOT.md)
- [Documentation de l'API](API_DOCUMENTATION.md)
- [Exemples d'utilisation](examples/)
