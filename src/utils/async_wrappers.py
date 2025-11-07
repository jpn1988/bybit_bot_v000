#!/usr/bin/env python3
"""Utilitaires pour exécuter du code bloquant dans un thread dédié."""

import asyncio
from typing import Any, Callable


async def run_in_thread(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Exécute ``func`` dans un thread via ``asyncio.to_thread``.

    Args:
        func: Fonction bloquante à exécuter dans un thread séparé.
        *args: Arguments positionnels pour ``func``.
        **kwargs: Arguments nommés pour ``func``.

    Returns:
        Résultat retourné par ``func``.
    """

    return await asyncio.to_thread(func, *args, **kwargs)

