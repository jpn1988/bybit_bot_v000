"""Gestionnaire de clients HTTP persistants pour optimiser les performances."""

import atexit
import httpx
import aiohttp
import asyncio
from typing import Optional
from logging_setup import setup_logging


class HTTPClientManager:
    """
    Gestionnaire singleton pour les clients HTTP persistants.

    Maintient des clients HTTP réutilisables pour éviter de recréer
    des connexions TLS à chaque requête.
    """

    _instance: Optional["HTTPClientManager"] = None
    _initialized: bool = False

    def __new__(cls) -> "HTTPClientManager":
        """Pattern Singleton pour garantir une seule instance."""
        if cls._instance is None:
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
        """
        try:
            # Fermer le client synchrone
            self.close_sync_client()

            # Fermer les clients asynchrones si un event loop est disponible
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Si la boucle tourne, programmer la fermeture
                    if (
                        self._async_client is not None
                        and not self._async_client.is_closed
                    ):
                        loop.create_task(self.close_async_client())
                    if (
                        self._aiohttp_session is not None
                        and not self._aiohttp_session.closed
                    ):
                        loop.create_task(self.close_aiohttp_session())
                else:
                    # Si la boucle ne tourne pas, l'exécuter pour fermer
                    loop.run_until_complete(self._close_async_clients())
            except RuntimeError:
                # Pas d'event loop disponible, créer une nouvelle boucle
                try:
                    asyncio.run(self._close_async_clients())
                except Exception as e:
                    self.logger.warning(
                        f"⚠️ Erreur fermeture clients async: {e}"
                    )

            # Tous les clients HTTP fermés

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


# Instance globale du gestionnaire
_http_manager = HTTPClientManager()


def get_http_client(timeout: int = 10) -> httpx.Client:
    """
    Fonction de convenance pour obtenir le client HTTP synchrone persistant.

    Args:
        timeout (int): Timeout en secondes

    Returns:
        httpx.Client: Client HTTP synchrone réutilisable
    """
    return _http_manager.get_sync_client(timeout)


def close_all_http_clients():
    """
    Fonction de convenance pour fermer tous les clients HTTP.
    Utile pour un nettoyage explicite.
    """
    _http_manager.close_all()
