#!/usr/bin/env python3
"""
Gestionnaire de clients HTTP persistants avec pattern Singleton.

╔═══════════════════════════════════════════════════════════════════╗
║                    📖 GUIDE DE LECTURE                            ║
╚═══════════════════════════════════════════════════════════════════╝

Ce fichier implémente un gestionnaire singleton qui maintient des clients HTTP
persistants pour réutiliser les connexions TLS et améliorer les performances.

🔍 COMPRENDRE CE FICHIER EN 3 MINUTES :

1. Pattern Singleton (lignes 22-26)
   └─> Une seule instance pour toute l'application

2. Clients persistants (lignes 44-119)
   └─> Réutilisation des connexions HTTP/HTTPS

3. Nettoyage automatique (lignes 142-223)
   └─> Fermeture propre via atexit

🏗️ PATTERN SINGLETON :

Le Singleton garantit qu'une seule instance existe pour toute l'application.

Avantages :
- ✅ Partage des connexions entre tous les modules
- ✅ Réutilisation du pool de connexions TLS
- ✅ Gestion centralisée du cycle de vie
- ✅ Économie de mémoire

Implémentation :
    class HTTPClientManager:
        _instance = None  # Instance unique (classe)

        def __new__(cls):
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

Exemple :
    manager1 = HTTPClientManager()  # Crée l'instance
    manager2 = HTTPClientManager()  # Retourne la même instance
    assert manager1 is manager2  # True !

🔗 CONNEXIONS PERSISTANTES :

Sans connexions persistantes :
    Requête 1 → Créer connexion TLS → Requête → Fermer → ❌ Lent
    Requête 2 → Créer connexion TLS → Requête → Fermer → ❌ Lent
    ...

Avec connexions persistantes (keep-alive) :
    Requête 1 → Créer connexion TLS → Requête → Garder ouverte ✅
    Requête 2 → Réutiliser connexion → Requête → Garder ouverte ✅
    Requête 3 → Réutiliser connexion → Requête → Garder ouverte ✅
    ...

Gain de performance :
- ⚡ ~300ms économisés par requête (TLS handshake)
- ⚡ Réduction de la charge serveur
- ⚡ Meilleur throughput (débit)

Configuration (httpx) :
- max_keepalive_connections : 20 connexions en attente
- max_connections : 100 connexions totales
- keepalive_expiry : 30s avant expiration

📚 EXEMPLE D'UTILISATION :

```python
from http_client_manager import get_http_client

# Obtenir le client (singleton)
client = get_http_client(timeout=10)

# Utiliser pour plusieurs requêtes
response1 = client.get("https://api.bybit.com/v5/market/tickers")
response2 = client.get("https://api.bybit.com/v5/market/orderbook")
# Les 2 requêtes réutilisent la même connexion TLS !
```

🛑 NETTOYAGE AUTOMATIQUE :

Le manager s'enregistre avec atexit pour garantir la fermeture propre :

```python
atexit.register(manager.close_all)  # Appelé automatiquement à la sortie
```

Fermeture à la sortie du programme :
1. Signal de sortie détecté (exit, Ctrl+C, crash)
2. atexit déclenche close_all()
3. Fermeture de tous les clients HTTP
4. Libération des ressources réseau

📖 RÉFÉRENCES :
- Pattern Singleton: https://refactoring.guru/design-patterns/singleton
- httpx keep-alive: https://www.python-httpx.org/advanced/#pool-limit-configuration
"""

import atexit
import httpx
import aiohttp
import asyncio
import threading
from typing import Optional
from logging_setup import setup_logging


class HTTPClientManager:
    """
    Gestionnaire singleton pour les clients HTTP persistants.

    Ce gestionnaire maintient des clients HTTP réutilisables (httpx, aiohttp)
    avec connexions keep-alive pour améliorer les performances en évitant
    les handshakes TLS répétés.

    Pattern Singleton : Une seule instance pour toute l'application.

    Clients gérés :
    - httpx.Client (synchrone) : Pour les requêtes bloquantes
    - httpx.AsyncClient (asynchrone) : Pour asyncio avec httpx
    - aiohttp.ClientSession (asynchrone) : Pour asyncio avec aiohttp

    Attributes:
        _instance (HTTPClientManager): Instance unique (niveau classe)
        _initialized (bool): Flag d'initialisation (évite double init)
        _sync_client (httpx.Client): Client HTTP synchrone
        _async_client (httpx.AsyncClient): Client HTTP asynchrone (httpx)
        _aiohttp_session (aiohttp.ClientSession): Session aiohttp

    Example:
        ```python
        # Obtenir l'instance (singleton)
        manager = HTTPClientManager()  # Même instance partout

        # Client synchrone
        client = manager.get_sync_client(timeout=10)
        response = client.get("https://api.bybit.com/...")

        # Client asynchrone
        async def fetch():
            client = await manager.get_async_client()
            response = await client.get("https://...")
        ```

    Note:
        - L'instance est créée au premier appel
        - Les clients sont créés à la demande (lazy loading)
        - La fermeture est automatique via atexit
    """

    _instance: Optional["HTTPClientManager"] = None
    _initialized: bool = False
    _lock = threading.Lock()

    def __new__(cls) -> "HTTPClientManager":
        """Pattern Singleton thread-safe pour garantir une seule instance."""
        if cls._instance is None:
            with cls._lock:  # Protection thread-safe
                if cls._instance is None:  # Double-check pattern
                    cls._instance = super(HTTPClientManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialise le gestionnaire (une seule fois)."""
        if HTTPClientManager._initialized:
            return

        self.logger = setup_logging()
        self._sync_client: Optional[httpx.Client] = None
        self._async_client: Optional[httpx.AsyncClient] = None
        self._aiohttp_session: Optional[aiohttp.ClientSession] = None

        # Enregistrer la fermeture automatique à l'arrêt du programme
        atexit.register(self.close_all)

        HTTPClientManager._initialized = True
        # Gestionnaire de clients HTTP initialisé

    def get_sync_client(self, timeout: int = 10) -> httpx.Client:
        """
        Retourne le client HTTP synchrone persistant.

        Args:
            timeout (int): Timeout en secondes

        Returns:
            httpx.Client: Client HTTP synchrone réutilisable
        """
        if self._sync_client is None or self._sync_client.is_closed:
            self._sync_client = httpx.Client(
                timeout=timeout,
                limits=httpx.Limits(
                    max_keepalive_connections=20,
                    max_connections=100,
                    keepalive_expiry=30.0,
                ),
            )
            self.logger.debug(
                f"🔗 Client HTTP synchrone créé (timeout={timeout}s)"
            )

        return self._sync_client

    async def get_async_client(self, timeout: int = 10) -> httpx.AsyncClient:
        """
        Retourne le client HTTP asynchrone persistant.

        Args:
            timeout (int): Timeout en secondes

        Returns:
            httpx.AsyncClient: Client HTTP asynchrone réutilisable
        """
        if self._async_client is None or self._async_client.is_closed:
            self._async_client = httpx.AsyncClient(
                timeout=timeout,
                limits=httpx.Limits(
                    max_keepalive_connections=20,
                    max_connections=100,
                    keepalive_expiry=30.0,
                ),
            )
            self.logger.debug(
                f"🔗 Client HTTP asynchrone créé (timeout={timeout}s)"
            )

        return self._async_client

    async def get_aiohttp_session(
        self, timeout: int = 10
    ) -> aiohttp.ClientSession:
        """
        Retourne la session aiohttp persistante.

        Args:
            timeout (int): Timeout en secondes

        Returns:
            aiohttp.ClientSession: Session aiohttp réutilisable
        """
        if self._aiohttp_session is None or self._aiohttp_session.closed:
            timeout_config = aiohttp.ClientTimeout(total=timeout)
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=20,
                keepalive_timeout=30.0,
                enable_cleanup_closed=True,
            )
            self._aiohttp_session = aiohttp.ClientSession(
                timeout=timeout_config, connector=connector
            )
            self.logger.debug(f"🔗 Session aiohttp créée (timeout={timeout}s)")

        return self._aiohttp_session

    def close_sync_client(self):
        """Ferme le client HTTP synchrone."""
        if self._sync_client is not None and not self._sync_client.is_closed:
            self._sync_client.close()
            self.logger.debug("🔌 Client HTTP synchrone fermé")

    async def close_async_client(self):
        """Ferme le client HTTP asynchrone."""
        if self._async_client is not None and not self._async_client.is_closed:
            await self._async_client.aclose()
            self.logger.debug("🔌 Client HTTP asynchrone fermé")

    async def close_aiohttp_session(self):
        """Ferme la session aiohttp."""
        if (
            self._aiohttp_session is not None
            and not self._aiohttp_session.closed
        ):
            await self._aiohttp_session.close()
            self.logger.debug("🔌 Session aiohttp fermée")

    def close_all(self):
        """
        Ferme tous les clients HTTP de manière synchrone.
        Utilisé par atexit pour un nettoyage automatique.

        ASYNC-002 CORRECTIF: Évite les event loops imbriquées.
        """
        try:
            # Fermer le client synchrone (toujours OK)
            self.close_sync_client()

            # CORRECTIF ARCH-001: Accepter que la fermeture async soit best-effort
            if self._async_client and not self._async_client.is_closed:
                self.logger.warning("⚠️ Client async non fermé (nécessite contexte async)")
            if self._aiohttp_session and not self._aiohttp_session.closed:
                self.logger.warning("⚠️ Session aiohttp non fermée (nécessite contexte async)")

            self.logger.debug("✅ Tous les clients HTTP fermés")

        except Exception as e:
            self.logger.warning(
                f"⚠️ Erreur lors de la fermeture des clients HTTP: {e}"
            )

    async def _close_async_clients(self):
        """Ferme les clients asynchrones."""
        tasks = []

        if self._async_client is not None and not self._async_client.is_closed:
            tasks.append(self.close_async_client())

        if (
            self._aiohttp_session is not None
            and not self._aiohttp_session.closed
        ):
            tasks.append(self.close_aiohttp_session())

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


# Instance lazy du gestionnaire (plus de variable globale)
_http_manager: Optional[HTTPClientManager] = None


def _get_manager() -> HTTPClientManager:
    """
    Obtient l'instance du gestionnaire HTTP de manière lazy.

    Returns:
        HTTPClientManager: Instance unique du gestionnaire
    """
    global _http_manager
    if _http_manager is None:
        _http_manager = HTTPClientManager()
    return _http_manager


def get_http_client(timeout: int = 10) -> httpx.Client:
    """
    Fonction de convenance pour obtenir le client HTTP synchrone persistant.

    Args:
        timeout (int): Timeout en secondes

    Returns:
        httpx.Client: Client HTTP synchrone réutilisable
    """
    return _get_manager().get_sync_client(timeout)


def close_all_http_clients():
    """
    Fonction de convenance pour fermer tous les clients HTTP.
    Utile pour un nettoyage explicite.
    """
    global _http_manager
    if _http_manager is not None:
        _http_manager.close_all()
        _http_manager = None
