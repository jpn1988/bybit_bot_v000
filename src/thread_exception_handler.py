#!/usr/bin/env python3
"""
Gestionnaire global des exceptions non capturées dans les threads et asyncio.

╔═══════════════════════════════════════════════════════════════════╗
║                    📖 GUIDE DE LECTURE                            ║
╚═══════════════════════════════════════════════════════════════════╝

Ce module installe des handlers globaux pour capturer les exceptions qui
échappent aux blocs try/except dans les threads et les tâches asyncio.

🎯 POURQUOI C'EST IMPORTANT :

Sans ces handlers :
- Une exception dans un thread peut tuer le thread silencieusement
- Une exception dans une tâche asyncio peut passer inaperçue
- Le bot continue à tourner avec des composants cassés sans le savoir

Avec ces handlers :
- ✅ Toutes les exceptions sont loggées avec contexte complet
- ✅ Stack trace complète pour faciliter le debugging
- ✅ Nom du thread/tâche pour identifier la source
- ✅ Pas de crash silencieux

🔍 COMPRENDRE CE FICHIER EN 2 MINUTES :

1. global_thread_exception_handler() (lignes 45-79)
   └─> Capte les exceptions dans les threads standard

2. global_asyncio_exception_handler() (lignes 81-113)
   └─> Capte les exceptions dans les tâches asyncio

3. install_global_exception_handlers() (lignes 115-141)
   └─> Fonction à appeler au démarrage du bot

📚 EXEMPLE D'UTILISATION :

```python
from thread_exception_handler import install_global_exception_handlers

# Au démarrage du bot
install_global_exception_handlers(logger)

# Maintenant tous les threads et tâches asyncio sont protégés
```

🛡️ CAS D'USAGE COUVERTS :

Thread standard :
```python
def worker():
    raise ValueError("Oups!")  # Sera loggée automatiquement

threading.Thread(target=worker).start()
```

Tâche asyncio :
```python
async def task():
    raise ValueError("Oups!")  # Sera loggée automatiquement

asyncio.create_task(task())
```

📖 RÉFÉRENCES :
- threading.excepthook: https://docs.python.org/3/library/threading.html#threading.excepthook
- asyncio exception handler: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.set_exception_handler
"""

import threading
import asyncio
import sys
from typing import Optional
from logging_setup import setup_logging


def global_thread_exception_handler(args):
    """
    Handler global pour les exceptions non capturées dans les threads.

    Ce handler est appelé automatiquement par Python lorsqu'une exception
    échappe à un thread sans être capturée par un try/except.

    Il log l'exception avec le contexte complet : nom du thread, type d'exception,
    message et stack trace complète.

    Args:
        args: ExceptHookArgs contenant :
            - exc_type: Type de l'exception (ex: ValueError)
            - exc_value: Instance de l'exception
            - exc_traceback: Traceback Python complet
            - thread: Thread où l'exception s'est produite

    Example:
        ```python
        # Cette exception sera automatiquement loggée
        def worker():
            raise ValueError("Erreur dans le thread")

        threading.Thread(target=worker, name="MonWorker").start()
        # → Log: "⚠️ Exception non capturée dans thread MonWorker: ValueError: Erreur dans le thread"
        ```

    Note:
        - Ce handler ne STOP PAS le thread (comportement normal Python)
        - Il ne fait que logger pour traçabilité
        - Le thread meurt après l'exception (comportement normal)
    """
    logger = setup_logging()

    # Extraire les informations de l'exception
    thread_name = args.thread.name if args.thread else "Unknown"
    exc_type_name = args.exc_type.__name__ if args.exc_type else "Unknown"
    exc_message = str(args.exc_value) if args.exc_value else ""

    # Logger l'exception avec contexte complet
    logger.error(
        f"⚠️ Exception non capturée dans thread '{thread_name}': "
        f"{exc_type_name}: {exc_message}",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
    )

    # Optionnel : Afficher aussi sur stderr pour debugging
    if hasattr(sys, 'stderr') and sys.stderr:
        print(
            f"\n⚠️ THREAD EXCEPTION [{thread_name}]: {exc_type_name}: {exc_message}",
            file=sys.stderr
        )


def global_asyncio_exception_handler(loop, context):
    """
    Handler global pour les exceptions dans la boucle événementielle asyncio.

    Ce handler est appelé lorsqu'une exception se produit dans :
    - Une tâche créée avec asyncio.create_task() sans await
    - Un callback de la boucle événementielle
    - Une coroutine fire-and-forget

    Il log l'exception avec le contexte asyncio complet.

    Args:
        loop: Event loop asyncio où l'exception s'est produite
        context: Dict contenant :
            - 'message': Message descriptif
            - 'exception': Instance de l'exception (si disponible)
            - 'future'/'task': Tâche/future où l'erreur s'est produite
            - 'handle': Handle du callback (si applicable)

    Example:
        ```python
        # Cette exception sera automatiquement loggée
        async def failing_task():
            raise ValueError("Erreur async")

        asyncio.create_task(failing_task())  # Fire-and-forget
        # → Log: "⚠️ Exception asyncio: Task exception was never retrieved..."
        ```

    Note:
        - Ce handler NE STOP PAS la boucle événementielle
        - Les autres tâches continuent normalement
        - Permet de tracer les erreurs dans les tâches fire-and-forget
    """
    logger = setup_logging()

    # Extraire le message d'erreur
    message = context.get('message', 'Exception asyncio')

    # Extraire l'exception si disponible
    exception = context.get('exception')

    # Logger selon la présence d'une exception
    if exception:
        logger.error(
            f"⚠️ Exception asyncio: {message}",
            exc_info=(type(exception), exception, exception.__traceback__)
        )
    else:
        # Pas d'exception, juste un message (rare)
        logger.warning(f"⚠️ Événement asyncio: {message} | Context: {context}")

    # Optionnel : Afficher sur stderr pour debugging
    if hasattr(sys, 'stderr') and sys.stderr and exception:
        print(
            f"\n⚠️ ASYNCIO EXCEPTION: {type(exception).__name__}: {exception}",
            file=sys.stderr
        )


def install_global_exception_handlers(logger: Optional[object] = None):
    """
    Installe les handlers globaux pour les exceptions non capturées.

    Cette fonction doit être appelée une seule fois au démarrage du bot,
    avant de créer des threads ou des tâches asyncio.

    Elle installe :
    1. Handler pour les threads (threading.excepthook)
    2. Handler pour asyncio (loop.set_exception_handler)

    Args:
        logger: Logger optionnel pour confirmer l'installation
                Si None, utilise le logger par défaut

    Example:
        ```python
        # Au démarrage du bot (dans bot.py ou main)
        from thread_exception_handler import install_global_exception_handlers

        logger = setup_logging()
        install_global_exception_handlers(logger)

        # Maintenant tous les threads et tâches sont protégés !
        ```

    Note:
        - Safe à appeler plusieurs fois (écrase les anciens handlers)
        - Compatible Python 3.8+ (threading.excepthook ajouté en 3.8)
        - Le handler asyncio est installé pour la boucle actuelle
    """
    if logger is None:
        logger = setup_logging()

    # Installer le handler pour les threads
    # Disponible depuis Python 3.8
    if hasattr(threading, 'excepthook'):
        threading.excepthook = global_thread_exception_handler
        logger.info("✅ Handler global pour exceptions threads installé")
    else:
        logger.warning(
            "⚠️ threading.excepthook non disponible (Python < 3.8), "
            "exceptions threads non capturées globalement"
        )

    # Installer le handler pour asyncio (si une boucle existe)
    try:
        loop = asyncio.get_event_loop()
        loop.set_exception_handler(global_asyncio_exception_handler)
        logger.info("✅ Handler global pour exceptions asyncio installé")
    except RuntimeError:
        # Pas de boucle événementielle active, on installe plus tard
        logger.debug(
            "Pas de boucle asyncio active, handler sera installé au démarrage"
        )


def install_asyncio_handler_if_needed():
    """
    Installe le handler asyncio si pas déjà fait.

    Utile à appeler au début d'une coroutine pour s'assurer que
    le handler est installé dans la boucle événementielle actuelle.

    Example:
        ```python
        async def main():
            install_asyncio_handler_if_needed()
            # ... reste du code
        ```

    Note:
        - Safe à appeler plusieurs fois
        - Silencieux si déjà installé
    """
    try:
        loop = asyncio.get_running_loop()
        # Vérifier si un handler custom est déjà installé
        current_handler = loop.get_exception_handler()
        if current_handler is None or current_handler != global_asyncio_exception_handler:
            loop.set_exception_handler(global_asyncio_exception_handler)
    except RuntimeError:
        # Pas de boucle en cours
        pass

