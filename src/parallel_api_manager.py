#!/usr/bin/env python3
"""
Gestionnaire de parallélisation optimisé pour les appels API.

Ce module fournit des outils avancés pour optimiser la parallélisation
des appels API tout en respectant les limites de rate limiting.
"""

import asyncio
import time
from typing import List, Dict, Any, Callable, Optional, TypeVar, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import Enum

from config.timeouts import ConcurrencyConfig
from async_rate_limiter import get_async_rate_limiter
from http_utils import get_rate_limiter

# Type générique pour les résultats
T = TypeVar('T')


class ExecutionMode(Enum):
    """Modes d'exécution pour les tâches parallèles."""
    ASYNC = "async"
    THREAD = "thread"
    HYBRID = "hybrid"


@dataclass
class ParallelConfig:
    """Configuration pour l'exécution parallèle."""
    max_concurrent: int = 10
    max_retries: int = 3
    retry_delay: float = 0.1
    timeout: float = 30.0
    mode: ExecutionMode = ExecutionMode.ASYNC
    rate_limit_enabled: bool = True
    batch_size: int = 50


class ParallelAPIManager:
    """
    Gestionnaire de parallélisation optimisé pour les appels API.

    Cette classe fournit des méthodes optimisées pour exécuter des tâches
    en parallèle tout en respectant les limites de rate limiting.
    """

    def __init__(self, config: Optional[ParallelConfig] = None):
        """
        Initialise le gestionnaire de parallélisation.

        Args:
            config: Configuration personnalisée (utilise les valeurs par défaut si None)
        """
        self.config = config or ParallelConfig()
        self._async_rate_limiter = get_async_rate_limiter()
        self._sync_rate_limiter = get_rate_limiter()
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent)

    async def execute_async_batch(
        self,
        tasks: List[Callable[[], Any]],
        batch_size: Optional[int] = None
    ) -> List[Any]:
        """
        Exécute une liste de tâches asynchrones en parallèle par lots.

        Args:
            tasks: Liste des tâches à exécuter
            batch_size: Taille des lots (utilise la config par défaut si None)

        Returns:
            Liste des résultats dans l'ordre des tâches
        """
        if not tasks:
            return []

        batch_size = batch_size or self.config.batch_size
        results = [None] * len(tasks)

        # Diviser en lots pour éviter la surcharge
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            batch_results = await self._execute_async_batch_internal(batch)

            # Insérer les résultats dans l'ordre
            for j, result in enumerate(batch_results):
                results[i + j] = result

        return results

    async def _execute_async_batch_internal(
        self,
        tasks: List[Callable[[], Any]]
    ) -> List[Any]:
        """Exécute un lot de tâches asynchrones avec rate limiting."""
        if not tasks:
            return []

        async def limited_task(task: Callable[[], Any]) -> Any:
            """Tâche avec rate limiting et semaphore."""
            if self.config.rate_limit_enabled:
                await self._async_rate_limiter.acquire()

            async with self._semaphore:
                return await task()

        # Exécuter toutes les tâches en parallèle
        return await asyncio.gather(
            *[limited_task(task) for task in tasks],
            return_exceptions=True
        )

    def execute_sync_batch(
        self,
        tasks: List[Callable[[], Any]],
        batch_size: Optional[int] = None
    ) -> List[Any]:
        """
        Exécute une liste de tâches synchrones en parallèle par lots.

        Args:
            tasks: Liste des tâches à exécuter
            batch_size: Taille des lots (utilise la config par défaut si None)

        Returns:
            Liste des résultats dans l'ordre des tâches
        """
        if not tasks:
            return []

        batch_size = batch_size or self.config.batch_size
        results = [None] * len(tasks)

        # Diviser en lots pour éviter la surcharge
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            batch_results = self._execute_sync_batch_internal(batch)

            # Insérer les résultats dans l'ordre
            for j, result in enumerate(batch_results):
                results[i + j] = result

        return results

    def _execute_sync_batch_internal(
        self,
        tasks: List[Callable[[], Any]]
    ) -> List[Any]:
        """Exécute un lot de tâches synchrones avec rate limiting."""
        if not tasks:
            return []

        def limited_task(task: Callable[[], Any]) -> Any:
            """Tâche avec rate limiting."""
            if self.config.rate_limit_enabled:
                self._sync_rate_limiter.acquire()
            return task()

        # Exécuter avec ThreadPoolExecutor pour la parallélisation
        with ThreadPoolExecutor(max_workers=min(len(tasks), ConcurrencyConfig.MAX_THREAD_POOL_WORKERS)) as executor:
            futures = [executor.submit(limited_task, task) for task in tasks]
            return [future.result() for future in as_completed(futures)]

    async def execute_hybrid_batch(
        self,
        async_tasks: List[Callable[[], Any]],
        sync_tasks: List[Callable[[], Any]],
        batch_size: Optional[int] = None
    ) -> tuple[List[Any], List[Any]]:
        """
        Exécute des tâches asynchrones et synchrones en parallèle.

        Args:
            async_tasks: Liste des tâches asynchrones
            sync_tasks: Liste des tâches synchrones
            batch_size: Taille des lots (utilise la config par défaut si None)

        Returns:
            Tuple (résultats_async, résultats_sync)
        """
        batch_size = batch_size or self.config.batch_size

        # Exécuter les deux types de tâches en parallèle
        async_results, sync_results = await asyncio.gather(
            self.execute_async_batch(async_tasks, batch_size),
            asyncio.get_event_loop().run_in_executor(
                None,
                self.execute_sync_batch,
                sync_tasks,
                batch_size
            )
        )

        return async_results, sync_results

    def create_async_task(
        self,
        func: Callable[..., Any],
        *args,
        **kwargs
    ) -> Callable[[], Any]:
        """
        Crée une tâche asynchrone à partir d'une fonction.

        Args:
            func: Fonction à exécuter
            *args: Arguments positionnels
            **kwargs: Arguments nommés

        Returns:
            Fonction asynchrone sans paramètres
        """
        async def task():
            return await func(*args, **kwargs)
        return task

    def create_sync_task(
        self,
        func: Callable[..., Any],
        *args,
        **kwargs
    ) -> Callable[[], Any]:
        """
        Crée une tâche synchrone à partir d'une fonction.

        Args:
            func: Fonction à exécuter
            *args: Arguments positionnels
            **kwargs: Arguments nommés

        Returns:
            Fonction synchrone sans paramètres
        """
        def task():
            return func(*args, **kwargs)
        return task

    async def execute_with_retry(
        self,
        task: Callable[[], Any],
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None
    ) -> Any:
        """
        Exécute une tâche avec retry automatique.

        Args:
            task: Tâche à exécuter
            max_retries: Nombre maximum de tentatives (utilise la config si None)
            retry_delay: Délai entre les tentatives (utilise la config si None)

        Returns:
            Résultat de la tâche

        Raises:
            Exception: Si toutes les tentatives échouent
        """
        max_retries = max_retries or self.config.max_retries
        retry_delay = retry_delay or self.config.retry_delay

        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(task):
                    return await task()
                else:
                    return task()
            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay * (2 ** attempt))  # Backoff exponentiel
                else:
                    raise last_exception

        raise last_exception


# Instance globale pour faciliter l'utilisation
_global_manager: Optional[ParallelAPIManager] = None


def get_parallel_manager() -> ParallelAPIManager:
    """
    Retourne l'instance globale du gestionnaire de parallélisation.

    Returns:
        Instance configurée de ParallelAPIManager
    """
    global _global_manager
    if _global_manager is None:
        _global_manager = ParallelAPIManager()
    return _global_manager


def create_parallel_manager(config: ParallelConfig) -> ParallelAPIManager:
    """
    Crée une nouvelle instance du gestionnaire de parallélisation.

    Args:
        config: Configuration personnalisée

    Returns:
        Nouvelle instance de ParallelAPIManager
    """
    return ParallelAPIManager(config)
