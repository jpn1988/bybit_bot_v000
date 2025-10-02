#!/usr/bin/env python3
"""
Module de calcul de volatilité 5 minutes pour le bot Bybit.

Calcule la volatilité basée sur la plage de prix (high-low) des 5 dernières bougies 1 minute.
"""

import time
import asyncio
import aiohttp
from typing import Optional, Dict, List
from collections import deque
from instruments import category_of_symbol
from http_utils import get_rate_limiter


"""La version synchrone compute_5m_range_pct a été retirée pour éviter les écarts de logique.
Utiliser compute_volatility_batch_async avec category_of_symbol et un cache partagé."""


def get_async_rate_limiter():
    """Construit un rate limiter asynchrone à partir des variables d'environnement."""
    try:
        import os
        max_calls = int(os.getenv("PUBLIC_HTTP_MAX_CALLS_PER_SEC", "5"))
        window = float(os.getenv("PUBLIC_HTTP_WINDOW_SECONDS", "1"))
    except (ValueError, TypeError) as e:
        # Log de l'erreur de conversion pour debugging
        import logging
        logging.getLogger(__name__).warning(f"Erreur conversion variables d'environnement rate limiter: {e}")
        max_calls = 5
        window = 1.0
    
    # Rate limiter asynchrone simple inline
    class AsyncRateLimiter:
        def __init__(self, max_calls: int = 5, window_seconds: float = 1.0):
            self.max_calls = max_calls
            self.window_seconds = window_seconds
            self._timestamps = deque()
            self._lock = asyncio.Lock()
        
        async def acquire(self):
            """Attend de manière asynchrone si nécessaire pour respecter la limite."""
            while True:
                now = time.time()
                async with self._lock:
                    # Retirer les timestamps hors fenêtre
                    while self._timestamps and now - self._timestamps[0] > self.window_seconds:
                        self._timestamps.popleft()
                    if len(self._timestamps) < self.max_calls:
                        self._timestamps.append(now)
                        return
                    # Temps à attendre jusqu'à expiration du plus ancien
                    wait_time = self.window_seconds - (now - self._timestamps[0])
                if wait_time > 0:
                    await asyncio.sleep(min(wait_time, 0.05))
    
    return AsyncRateLimiter(max_calls=max_calls, window_seconds=window)


def get_volatility_cache_key(symbol: str) -> str:
    """
    Génère une clé de cache pour la volatilité d'un symbole.
    
    Args:
        symbol (str): Symbole
        
    Returns:
        str: Clé de cache
    """
    return f"volatility_5m_{symbol}"


def is_cache_valid(timestamp: float, ttl_seconds: int = 60) -> bool:
    """
    Vérifie si un cache est encore valide.
    
    Args:
        timestamp (float): Timestamp du cache
        ttl_seconds (int): Durée de vie en secondes
        
    Returns:
        bool: True si le cache est valide
    """
    return (time.time() - timestamp) < ttl_seconds


async def compute_volatility_batch_async(
    bybit_client, 
    symbols: List[str], 
    timeout: int = 10, 
    symbol_categories: Dict[str, str] | None = None
) -> Dict[str, Optional[float]]:
    """
    Calcule la volatilité 5 minutes pour une liste de symboles en parallèle.
    OPTIMISATION: Utilise aiohttp et asyncio.gather() pour paralléliser les appels API.
    
    Args:
        bybit_client: Instance du client Bybit (pour récupérer l'URL de base)
        symbols (List[str]): Liste des symboles à analyser
        timeout (int): Timeout pour les requêtes HTTP en secondes
        
    Returns:
        Dict[str, Optional[float]]: Dictionnaire {symbol: volatility_pct} ou None si erreur
    """
    if not symbols:
        return {}
    
    # Récupérer l'URL de base du client
    base_url = bybit_client.public_base_url()
    
    # Limiter la concurrence globale pour éviter le rate limit (plus conservateur)
    sem = asyncio.Semaphore(5)
    async_rate_limiter = get_async_rate_limiter()

    async def limited_task(sym: str):
        # Respecter le rate limiter asynchrone avant chaque requête
        await async_rate_limiter.acquire()
        async with sem:
            return await _compute_single_volatility_async(session, base_url, sym, symbol_categories)

    # Créer une session aiohttp
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
        # Créer les tâches async pour chaque symbole
        tasks = []
        for symbol in symbols:
            task = limited_task(symbol)
            tasks.append(task)
        
        # Exécuter toutes les tâches en parallèle
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Construire le dictionnaire de résultats
        volatility_results = {}
        for i, result in enumerate(results):
            symbol = symbols[i]
            if isinstance(result, Exception):
                # En cas d'erreur, mettre None et enrichir le contexte en log
                try:
                    # Ne pas importer le logger globalement pour éviter dépendances circulaires
                    import logging
                    logging.getLogger(__name__).warning(
                        (
                            f"Erreur async kline | endpoint=/v5/market/kline symbol={symbol} "
                            f"timeout={timeout}s error={result}"
                        )
                    )
                except (ImportError, AttributeError) as e:
                    # Erreur de logging - ne pas bloquer le flux
                    pass
                volatility_results[symbol] = None
            else:
                volatility_results[symbol] = result
        
        return volatility_results


async def _compute_single_volatility_async(
    session: aiohttp.ClientSession, 
    base_url: str, 
    symbol: str, 
    symbol_categories: Dict[str, str] | None = None
) -> Optional[float]:
    """
    Calcule la volatilité pour un seul symbole de manière asynchrone.
    Fonction helper pour la parallélisation.
    
    Args:
        session (aiohttp.ClientSession): Session HTTP asynchrone
        base_url (str): URL de base de l'API Bybit
        symbol (str): Symbole à analyser
        
    Returns:
        Optional[float]: Volatilité en pourcentage ou None si erreur
    """
    try:
        # Déterminer la catégorie via mapping officiel si disponible, sinon fallback heuristique
        category = category_of_symbol(symbol, symbol_categories)
        
        # Construire l'URL pour récupérer les bougies 1 minute
        url = f"{base_url}/v5/market/kline"
        params = {
            "category": category,
            "symbol": symbol,
            "interval": "1",  # 1 minute
            "limit": 6  # 6 bougies pour avoir 5 minutes + 1 de sécurité
        }
        
        # Faire la requête HTTP asynchrone
        async with session.get(url, params=params) as response:
            # Vérifier le statut HTTP
            if response.status >= 400:
                try:
                    import logging
                    logging.getLogger(__name__).warning(
                        (
                            f"Erreur HTTP kline GET {url} | category={category} symbol={symbol} "
                            f"interval={params['interval']} timeout={session.timeout.total} status={response.status}"
                        )
                    )
                except (ImportError, AttributeError) as e:
                    # Erreur de logging - ne pas bloquer le flux
                    pass
                return None
            
            data = await response.json()
            
            # Vérifier le retCode
            if data.get("retCode") != 0:
                try:
                    import logging
                    logging.getLogger(__name__).warning(
                        (
                            f"Erreur API kline GET {url} | category={category} symbol={symbol} "
                            f"interval={params['interval']} retCode={data.get('retCode')} retMsg=\"{data.get('retMsg','')}\""
                        )
                    )
                except (ImportError, AttributeError) as e:
                    # Erreur de logging - ne pas bloquer le flux
                    pass
                return None
            
            result = data.get("result", {})
            klines = result.get("list", [])
            
            # Vérifier qu'on a assez de données
            if len(klines) < 5:
                return None
            
            # Extraire les prix (high et low de chaque bougie)
            # Les bougies sont triées par timestamp décroissant (plus récent en premier)
            prices_high = []
            prices_low = []
            
            for kline in klines[:5]:  # Prendre les 5 plus récentes
                try:
                    high = float(kline[2])  # Index 2 = high
                    low = float(kline[3])   # Index 3 = low
                    prices_high.append(high)
                    prices_low.append(low)
                except (ValueError, TypeError, IndexError):
                    # Ignorer les bougies avec des données invalides
                    continue
            
            # Vérifier qu'on a assez de données valides
            if len(prices_high) < 3:  # Au moins 3 bougies valides
                return None
            
            # Calculer la volatilité
            pmax = max(prices_high)  # Prix maximum sur la période
            pmin = min(prices_low)   # Prix minimum sur la période
            pmid = (pmax + pmin) / 2  # Prix médian
            
            # Éviter la division par zéro
            if pmid <= 0:
                return None
            
            # Calculer la volatilité en pourcentage
            vol_pct = (pmax - pmin) / pmid
            
            return vol_pct
            
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, TypeError, KeyError, IndexError) as e:
        # Erreurs spécifiques : réseau, timeout, conversion, accès données
        import logging
        logging.getLogger(__name__).error(f"Erreur calcul volatilité pour {symbol}: {type(e).__name__}: {e}")
        return None
    except Exception as e:
        # Erreur inattendue - log pour debugging
        import logging
        logging.getLogger(__name__).error(f"Erreur inattendue calcul volatilité pour {symbol}: {type(e).__name__}: {e}")
        return None
