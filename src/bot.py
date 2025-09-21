#!/usr/bin/env python3
"""
🚀 Orchestrateur du bot (filters + WebSocket prix) - VERSION OPTIMISÉE

Script pour filtrer les contrats perpétuels par funding ET suivre leurs prix en temps réel.

OPTIMISATIONS PERFORMANCE APPLIQUÉES (alignées avec la doc):
- fetch_funding_map(): limite 1000 (maximum API Bybit) + pagination robuste
- fetch_spread_data(): pagination 1000 + fallback unitaire (pas de ThreadPoolExecutor)
- filter_by_volatility(): parallélisation async/await (aiohttp + asyncio.gather) + semaphore(5)
- Rate limiting configurable via ENV (PUBLIC_HTTP_MAX_CALLS_PER_SEC, PUBLIC_HTTP_WINDOW_SECONDS)
- Gestion d'erreur robuste et logs informatifs

Usage:
    python src/bot.py
"""

import os
import sys
import json
import time
import signal
import threading
import yaml
import httpx
import websocket
import asyncio
import atexit
from typing import List, Dict
from http_utils import get_rate_limiter
from http_client_manager import get_http_client, close_all_http_clients
try:
    from .config import get_settings
except ImportError:
    from config import get_settings
from logging_setup import setup_logging
from bybit_client import BybitClient, BybitPublicClient
from instruments import get_perp_symbols, category_of_symbol
from price_store import update, get_snapshot, purge_expired
from volatility import get_volatility_cache_key, is_cache_valid, compute_volatility_batch_async
from volatility_tracker import VolatilityTracker
from watchlist_manager import WatchlistManager
from errors import NoSymbolsError, FundingUnavailableError
from metrics import record_filter_result, record_ws_connection, record_ws_error
from metrics_monitor import start_metrics_monitoring
from ws_public import PublicWSClient
from ws_manager import WebSocketManager


class PublicWSConnection:
    """Connexion WebSocket publique isolée (évite l'état partagé entre linear/inverse)."""

    def __init__(self, category: str, symbols: list[str], testnet: bool, logger, on_ticker_callback):
        self.category = category
        self.symbols = symbols
        self.testnet = testnet
        self.logger = logger
        self.on_ticker_callback = on_ticker_callback  # callable(ticker_data: dict)
        self.ws = None
        self.running = False
        
        # Configuration de reconnexion avec backoff
        self.reconnect_delays = [1, 2, 5, 10, 30]  # secondes
        self.current_delay_index = 0

    def _build_url(self) -> str:
        if self.category == "linear":
            return "wss://stream-testnet.bybit.com/v5/public/linear" if self.testnet else "wss://stream.bybit.com/v5/public/linear"
        else:
            return "wss://stream-testnet.bybit.com/v5/public/inverse" if self.testnet else "wss://stream.bybit.com/v5/public/inverse"

    def _on_open(self, ws):
        self.logger.info(f"🌐 WS ouverte ({self.category})")
        
        # Enregistrer la connexion WebSocket
        record_ws_connection(connected=True)
        
        # Réinitialiser l'index de délai de reconnexion après une connexion réussie
        self.current_delay_index = 0
        
        # S'abonner aux tickers pour tous les symboles
        if self.symbols:
            subscribe_message = {
                "op": "subscribe",
                "args": [f"tickers.{symbol}" for symbol in self.symbols]
            }
            try:
                ws.send(json.dumps(subscribe_message))
                self.logger.info(f"🧭 Souscription tickers → {len(self.symbols)} symboles ({self.category})")
            except (json.JSONEncodeError, ConnectionError, OSError) as e:
                self.logger.error(f"Erreur souscription WebSocket {self.category}: {type(e).__name__}: {e}")
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur souscription {self.category}: {e}")
        else:
            self.logger.warning(f"⚠️ Aucun symbole à suivre pour {self.category}")

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            if data.get("topic", "").startswith("tickers."):
                ticker_data = data.get("data", {})
                if ticker_data:
                    self.on_ticker_callback(ticker_data)
        except json.JSONDecodeError as e:
            self.logger.warning(f"⚠️ Erreur JSON ({self.category}): {e}")
        except (KeyError, TypeError, AttributeError) as e:
            self.logger.warning(f"⚠️ Erreur parsing données ({self.category}): {type(e).__name__}: {e}")
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur parsing ({self.category}): {e}")

    def _on_error(self, ws, error):
        if self.running:
            self.logger.warning(f"⚠️ WS erreur ({self.category}) : {error}")
            record_ws_error()

    def _on_close(self, ws, close_status_code, close_msg):
        if self.running:
            self.logger.info(f"🔌 WS fermée ({self.category}) (code={close_status_code}, reason={close_msg})")

    def run(self):
        """Boucle principale avec reconnexion automatique et backoff progressif."""
        self.running = True
        
        while self.running:
            try:
                try:
                    self.logger.info(f"🔐 Connexion à la WebSocket publique ({self.category})…")
                except Exception:
                    pass
                
                url = self._build_url()
                self.ws = websocket.WebSocketApp(
                    url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close
                )
                
                self.ws.run_forever(ping_interval=20, ping_timeout=10)
                
            except (ConnectionError, OSError, TimeoutError) as e:
                if self.running:
                    try:
                        self.logger.error(f"Erreur connexion réseau WS publique ({self.category}): {type(e).__name__}: {e}")
                    except Exception:
                        pass
            except Exception as e:
                if self.running:
                    try:
                        self.logger.error(f"Erreur connexion WS publique ({self.category}): {e}")
                    except Exception:
                        pass
            
            # Reconnexion avec backoff progressif
            if self.running:
                delay = self.reconnect_delays[min(self.current_delay_index, len(self.reconnect_delays) - 1)]
                try:
                    self.logger.warning(f"🔁 WS publique ({self.category}) déconnectée → reconnexion dans {delay}s")
                    record_ws_connection(connected=False)  # Enregistrer la reconnexion
                except Exception:
                    pass
                
                # Attendre le délai avec vérification périodique de l'arrêt
                for _ in range(delay):
                    if not self.running:
                        break
                    time.sleep(1)
                
                # Augmenter l'index de délai pour le prochain backoff (jusqu'à la limite)
                if self.current_delay_index < len(self.reconnect_delays) - 1:
                    self.current_delay_index += 1
            else:
                break

    def close(self):
        self.running = False
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass

# validate_config moved to WatchlistManager


# load_config moved to WatchlistManager


# fetch_funding_map moved to WatchlistManager


# calculate_funding_time_remaining moved to WatchlistManager
def calculate_funding_time_remaining_DEPRECATED(next_funding_time: str | int | float | None) -> str:
    """Retourne "Xh Ym Zs" à partir d'un timestamp Bybit (ms) ou ISO. Pas de parsing manuel."""
    if not next_funding_time:
        return "-"
    try:
        import datetime
        funding_dt: datetime.datetime | None = None
        if isinstance(next_funding_time, (int, float)):
            funding_dt = datetime.datetime.fromtimestamp(float(next_funding_time) / 1000, tz=datetime.timezone.utc)
        elif isinstance(next_funding_time, str):
            if next_funding_time.isdigit():
                funding_dt = datetime.datetime.fromtimestamp(float(next_funding_time) / 1000, tz=datetime.timezone.utc)
            else:
                funding_dt = datetime.datetime.fromisoformat(next_funding_time.replace('Z', '+00:00'))
                if funding_dt.tzinfo is None:
                    funding_dt = funding_dt.replace(tzinfo=datetime.timezone.utc)
        if funding_dt is None:
            return "-"
        now = datetime.datetime.now(datetime.timezone.utc)
        delta = (funding_dt - now).total_seconds()
        if delta <= 0:
            return "-"
        total_seconds = int(delta)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        if minutes > 0:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"
    except (ValueError, TypeError, OSError) as e:
        # Erreurs de conversion ou système
        import logging
        logging.getLogger(__name__).error(f"Erreur calcul temps funding formaté: {type(e).__name__}: {e}")
        return "-"
    except Exception as e:
        # Erreur inattendue
        import logging
        logging.getLogger(__name__).error(f"Erreur inattendue calcul temps funding: {type(e).__name__}: {e}")
        return "-"


def calculate_funding_minutes_remaining(next_funding_time: str | int | float | None) -> float | None:
    """Retourne les minutes restantes avant le prochain funding (pour filtrage). Utilise la logique centralisée."""
    if not next_funding_time:
        return None
    try:
        import datetime
        funding_dt: datetime.datetime | None = None
        if isinstance(next_funding_time, (int, float)):
            funding_dt = datetime.datetime.fromtimestamp(float(next_funding_time) / 1000, tz=datetime.timezone.utc)
        elif isinstance(next_funding_time, str):
            if next_funding_time.isdigit():
                funding_dt = datetime.datetime.fromtimestamp(float(next_funding_time) / 1000, tz=datetime.timezone.utc)
            else:
                funding_dt = datetime.datetime.fromisoformat(next_funding_time.replace('Z', '+00:00'))
                if funding_dt.tzinfo is None:
                    funding_dt = funding_dt.replace(tzinfo=datetime.timezone.utc)
        if funding_dt is None:
            return None
        now = datetime.datetime.now(datetime.timezone.utc)
        delta_sec = (funding_dt - now).total_seconds()
        if delta_sec <= 0:
            return None
        return delta_sec / 60.0  # Convertir en minutes
    except (ValueError, TypeError, OSError) as e:
        # Erreurs de conversion ou système
        import logging
        logging.getLogger(__name__).error(f"Erreur calcul minutes funding: {type(e).__name__}: {e}")
        return None
    except Exception as e:
        # Erreur inattendue
        import logging
        logging.getLogger(__name__).error(f"Erreur inattendue calcul minutes funding: {type(e).__name__}: {e}")
        return None


def fetch_spread_data(base_url: str, symbols: list[str], timeout: int, category: str = "linear") -> dict[str, float]:
    """
    Récupère les spreads via /v5/market/tickers paginé (sans symbol=), puis filtre localement.
    
    Args:
        base_url (str): URL de base de l'API Bybit
        symbols (list[str]): Liste cible des symboles à retourner
        timeout (int): Timeout HTTP
        category (str): "linear" ou "inverse"
    Returns:
        dict[str, float]: map {symbol: spread_pct}
    """
    wanted = set(symbols)
    found: dict[str, float] = {}
    url = f"{base_url}/v5/market/tickers"
    params = {"category": category, "limit": 1000}
    cursor = ""
    page_index = 0
    rate_limiter = get_rate_limiter()
    while True:
        page_index += 1
        if cursor:
            params["cursor"] = cursor
        else:
            params.pop("cursor", None)
        try:
            rate_limiter.acquire()
            client = get_http_client(timeout=timeout)
            resp = client.get(url, params=params)
            if resp.status_code >= 400:
                raise RuntimeError(
                    (
                        f"Erreur HTTP Bybit GET {url} | category={category} page={page_index} "
                        f"limit={params.get('limit')} cursor={params.get('cursor','-')} status={resp.status_code} "
                        f"detail=\"{resp.text[:200]}\""
                    )
                )
            data = resp.json()
            if data.get("retCode") != 0:
                raise RuntimeError(
                    (
                        f"Erreur API Bybit GET {url} | category={category} page={page_index} "
                        f"retCode={data.get('retCode')} retMsg=\"{data.get('retMsg','')}\""
                    )
                )
            result = data.get("result", {})
            tickers = result.get("list", [])
            for t in tickers:
                sym = t.get("symbol")
                if sym in wanted:
                    bid1 = t.get("bid1Price")
                    ask1 = t.get("ask1Price")
                    try:
                        if bid1 is not None and ask1 is not None:
                            b = float(bid1)
                            a = float(ask1)
                            if b > 0 and a > 0:
                                mid = (a + b) / 2
                                if mid > 0:
                                    found[sym] = (a - b) / mid
                    except (ValueError, TypeError) as e:
                        # Erreur de conversion numérique - ignorer silencieusement
                        pass
            # Fin pagination
            next_cursor = result.get("nextPageCursor")
            # Arrêt anticipé si on a tout trouvé
            if len(found) >= len(wanted):
                break
            if not next_cursor:
                break
            cursor = next_cursor
        except (httpx.RequestError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
            # Erreurs réseau/HTTP spécifiques
            try:
                from logging_setup import setup_logging
                setup_logging().error(
                    f"Erreur réseau spread paginé page={page_index} category={category}: {type(e).__name__}: {e}"
                )
            except Exception:
                pass
            break
        except (ValueError, TypeError, KeyError) as e:
            # Erreurs de données/parsing
            try:
                from logging_setup import setup_logging
                setup_logging().warning(
                    f"Erreur données spread paginé page={page_index} category={category}: {type(e).__name__}: {e}"
                )
            except Exception:
                pass
            break
        except Exception as e:
            # Erreur inattendue
            try:
                from logging_setup import setup_logging
                setup_logging().error(
                    f"Erreur inattendue spread paginé page={page_index} category={category}: {type(e).__name__}: {e}"
                )
            except Exception:
                pass
            break
    # Fallback unitaire pour les symboles manquants
    missing = [s for s in symbols if s not in found]
    for s in missing:
        try:
            val = _fetch_single_spread(base_url, s, timeout, category)
            if val is not None:
                found[s] = val
        except (httpx.RequestError, ValueError, TypeError) as e:
            # Erreurs réseau ou conversion - ignorer silencieusement pour le fallback
            pass
    return found


def _process_batch_spread(base_url: str, symbol_batch: list[str], timeout: int, category: str, batch_idx: int) -> dict[str, float]:
    """
    Traite un batch de symboles pour récupérer les spreads.
    Fonction helper pour la parallélisation.
    
    Args:
        base_url (str): URL de base de l'API Bybit
        symbol_batch (list[str]): Batch de symboles à traiter
        timeout (int): Timeout pour les requêtes HTTP
        category (str): Catégorie des symboles
        batch_idx (int): Index du batch (pour le logging)
        
    Returns:
        dict[str, float]: Dictionnaire {symbol: spread_pct} pour ce batch
    """
    batch_spread_data = {}
    
    try:
        # Construire l'URL avec les symboles du batch
        url = f"{base_url}/v5/market/tickers"
        params = {
            "category": category,
            "symbol": ",".join(symbol_batch)
        }
        
        # Respecter le rate limiter global
        rate_limiter = get_rate_limiter()
        rate_limiter.acquire()
        client = get_http_client(timeout=timeout)
        response = client.get(url, params=params)
        
        # Vérifier le statut HTTP
        if response.status_code >= 400:
            sample = ",".join(symbol_batch[:5])
            raise RuntimeError(
                (
                    f"Erreur HTTP Bybit GET {url} | category={category} batch_idx={batch_idx} "
                    f"batch_size={len(symbol_batch)} sample=[{sample}] timeout={timeout}s "
                    f"status={response.status_code} detail=\"{response.text[:200]}\""
                )
            )
        
        data = response.json()
        
        # Vérifier le retCode
        if data.get("retCode") != 0:
            ret_code = data.get("retCode")
            ret_msg = data.get("retMsg", "")
            
            # Si erreur de symbole invalide, essayer un par un
            if ret_code == 10001 and "symbol invalid" in ret_msg.lower():
                # Récupérer les spreads un par un pour ce batch
                for symbol in symbol_batch:
                    try:
                        single_spread = _fetch_single_spread(base_url, symbol, timeout, category)
                        if single_spread:
                            batch_spread_data[symbol] = single_spread
                    except Exception:
                        # Ignorer les symboles qui échouent
                        pass
                return batch_spread_data
            else:
                sample = ",".join(symbol_batch[:5])
                raise RuntimeError(
                    (
                        f"Erreur API Bybit GET {url} | category={category} batch_idx={batch_idx} "
                        f"batch_size={len(symbol_batch)} sample=[{sample}] timeout={timeout}s "
                        f"retCode={ret_code} retMsg=\"{ret_msg}\""
                    )
                )
        
        result = data.get("result", {})
        tickers = result.get("list", [])
        
        # Extraire les données de spread
        for ticker in tickers:
            symbol = ticker.get("symbol", "")
            bid1_price = ticker.get("bid1Price")
            ask1_price = ticker.get("ask1Price")
            
            if symbol and bid1_price is not None and ask1_price is not None:
                try:
                    bid1 = float(bid1_price)
                    ask1 = float(ask1_price)
                    
                    # Calculer le spread en pourcentage
                    # spread_pct = (ask1 - bid1) / ((ask1 + bid1)/2)
                    if bid1 > 0 and ask1 > 0:
                        spread_pct = (ask1 - bid1) / ((ask1 + bid1) / 2)
                        batch_spread_data[symbol] = spread_pct
                except (ValueError, TypeError, ZeroDivisionError):
                    # Ignorer si les données ne sont pas convertibles ou si division par zéro
                    pass
                
    except httpx.RequestError as e:
        sample = ",".join(symbol_batch[:5])
        raise RuntimeError(
            (
                f"Erreur réseau Bybit GET {url} | category={category} batch_idx={batch_idx} "
                f"batch_size={len(symbol_batch)} sample=[{sample}] timeout={timeout}s error={e}"
            )
        )
    except Exception as e:
        if "Erreur" in str(e):
            raise
        else:
            sample = ",".join(symbol_batch[:5])
            raise RuntimeError(
                (
                    f"Erreur inconnue Bybit GET {url} | category={category} batch_idx={batch_idx} "
                    f"batch_size={len(symbol_batch)} sample=[{sample}] timeout={timeout}s error={e}"
                )
            )
    
    return batch_spread_data


def _fetch_single_spread(base_url: str, symbol: str, timeout: int, category: str) -> float | None:
    """
    Récupère le spread pour un seul symbole.
    
    Args:
        base_url (str): URL de base de l'API Bybit
        symbol (str): Symbole à analyser
        timeout (int): Timeout pour les requêtes HTTP
        category (str): Catégorie des symboles ("linear" ou "inverse")
        
    Returns:
        float | None: Spread en pourcentage ou None si erreur
    """
    try:
        url = f"{base_url}/v5/market/tickers"
        params = {
            "category": category,
            "symbol": symbol
        }
        
        rate_limiter = get_rate_limiter()
        rate_limiter.acquire()
        client = get_http_client(timeout=timeout)
        response = client.get(url, params=params)
        
        if response.status_code >= 400:
            raise RuntimeError(
                (
                    f"Erreur HTTP Bybit GET {url} | category={category} symbol={symbol} "
                    f"timeout={timeout}s status={response.status_code} detail=\"{response.text[:200]}\""
                )
            )
        
        data = response.json()
        
        if data.get("retCode") != 0:
            ret_code = data.get("retCode")
            ret_msg = data.get("retMsg", "")
            raise RuntimeError(
                (
                    f"Erreur API Bybit GET {url} | category={category} symbol={symbol} "
                    f"timeout={timeout}s retCode={ret_code} retMsg=\"{ret_msg}\""
                )
            )
        
        result = data.get("result", {})
        tickers = result.get("list", [])
        
        if not tickers:
            return None
        
        ticker = tickers[0]
        bid1_price = ticker.get("bid1Price")
        ask1_price = ticker.get("ask1Price")
        
        if bid1_price is not None and ask1_price is not None:
            try:
                bid1 = float(bid1_price)
                ask1 = float(ask1_price)
                
                if bid1 > 0 and ask1 > 0:
                    spread_pct = (ask1 - bid1) / ((ask1 + bid1) / 2)
                    return spread_pct
            except (ValueError, TypeError, ZeroDivisionError):
                pass
        
        return None
        
    except Exception:
        return None


def filter_by_spread(symbols_data: list[tuple[str, float, float, str]], spread_data: dict[str, float], spread_max: float | None) -> list[tuple[str, float, float, str, float]]:
    """
    Filtre les symboles par spread maximum.
    
    Args:
        symbols_data (list[tuple[str, float, float, str]]): Liste des (symbol, funding, volume, funding_time_remaining)
        spread_data (dict[str, float]): Dictionnaire des spreads {symbol: spread_pct}
        spread_max (float | None): Spread maximum autorisé
        
    Returns:
        list[tuple[str, float, float, str, float]]: Liste des (symbol, funding, volume, funding_time_remaining, spread_pct) filtrés
    """
    if spread_max is None:
        # Pas de filtre de spread, ajouter 0.0 comme spread par défaut
        return [(symbol, funding, volume, funding_time_remaining, 0.0) for symbol, funding, volume, funding_time_remaining in symbols_data]
    
    filtered_symbols = []
    for symbol, funding, volume, funding_time_remaining in symbols_data:
        if symbol in spread_data:
            spread_pct = spread_data[symbol]
            if spread_pct <= spread_max:
                filtered_symbols.append((symbol, funding, volume, funding_time_remaining, spread_pct))
    
    return filtered_symbols




def filter_by_funding(
    perp_data: dict, 
    funding_map: dict, 
    funding_min: float | None, 
    funding_max: float | None, 
    volume_min: float | None, 
    volume_min_millions: float | None, 
    limite: int | None, 
    funding_time_min_minutes: int | None = None, 
    funding_time_max_minutes: int | None = None
) -> list[tuple[str, float, float, str]]:
    """
    Filtre les symboles par funding, volume et fenêtre temporelle avant funding, puis trie par |funding| décroissant.
    
    Args:
        perp_data (dict): Données des perpétuels (linear, inverse, total)
        funding_map (dict): Dictionnaire des funding rates, volumes et temps de funding
        funding_min (float | None): Funding minimum en valeur absolue (ex: 0.01 = 1%)
        funding_max (float | None): Funding maximum en valeur absolue (ex: 0.05 = 5%)
        volume_min (float | None): Volume minimum (ancien format)
        volume_min_millions (float | None): Volume minimum en millions (nouveau format)
        limite (int | None): Limite du nombre d'éléments
        funding_time_min_minutes (int | None): Temps minimum en minutes avant prochain funding
        funding_time_max_minutes (int | None): Temps maximum en minutes avant prochain funding
        
    Returns:
        list[tuple[str, float, float, str]]: Liste des (symbol, funding, volume, funding_time_remaining) triés
        
    Note:
        Les filtres funding_min et funding_max utilisent la valeur absolue du funding.
        Ainsi, un funding de +0.02% ou -0.02% passe tous les deux si 0.01 <= |funding| <= 0.05.
    """
    # Récupérer tous les symboles perpétuels
    all_symbols = list(set(perp_data["linear"] + perp_data["inverse"]))
    
    # Déterminer le volume minimum à utiliser (priorité : volume_min_millions > volume_min)
    effective_volume_min = None
    if volume_min_millions is not None:
        effective_volume_min = volume_min_millions * 1_000_000  # Convertir en valeur brute
    elif volume_min is not None:
        effective_volume_min = volume_min
    
    # Filtrer par funding, volume et fenêtre temporelle
    filtered_symbols = []
    for symbol in all_symbols:
        if symbol in funding_map:
            data = funding_map[symbol]
            funding = data["funding"]
            volume = data["volume"]
            next_funding_time = data.get("next_funding_time")
            
            # Appliquer les bornes funding/volume (utiliser valeur absolue pour funding)
            if funding_min is not None and abs(funding) < funding_min:
                continue
            if funding_max is not None and abs(funding) > funding_max:
                continue
            if effective_volume_min is not None and volume < effective_volume_min:
                continue
            
            # Appliquer le filtre temporel si demandé
            if funding_time_min_minutes is not None or funding_time_max_minutes is not None:
                # Utiliser la fonction centralisée pour calculer les minutes restantes
                minutes_remaining = calculate_funding_minutes_remaining(next_funding_time)
                
                # Si pas de temps valide alors qu'on filtre, rejeter
                if minutes_remaining is None:
                    continue
                if (funding_time_min_minutes is not None and 
                    minutes_remaining < float(funding_time_min_minutes)):
                    continue
                if (funding_time_max_minutes is not None and 
                    minutes_remaining > float(funding_time_max_minutes)):
                    continue
            
            # Calculer le temps restant avant le prochain funding (formaté)
            funding_time_remaining = calculate_funding_time_remaining(next_funding_time)
            
            filtered_symbols.append((symbol, funding, volume, funding_time_remaining))
    
    # Trier par |funding| décroissant
    filtered_symbols.sort(key=lambda x: abs(x[1]), reverse=True)
    
    # Appliquer la limite
    if limite is not None:
        filtered_symbols = filtered_symbols[:limite]
    
    return filtered_symbols


class PriceTracker:
    """Suivi des prix en temps réel via WebSocket avec filtrage par funding."""
    
    def __init__(self):
        self.logger = setup_logging()
        self.running = True
        
        # S'assurer que les clients HTTP sont fermés à l'arrêt
        atexit.register(close_all_http_clients)
        self.display_thread = None
        self.symbols = []
        self.funding_data = {}
        self.original_funding_data = {}  # Données de funding originales avec next_funding_time
        # self.start_time supprimé: on s'appuie uniquement sur nextFundingTime côté Bybit
        self.realtime_data = {}  # Données en temps réel via WebSocket {symbol: {funding_rate, volume24h, bid1, ask1, next_funding_time, ...}}
        self._realtime_lock = threading.Lock()  # Verrou pour protéger realtime_data
        self._first_display = True  # Indicateur pour la première exécution de l'affichage
        self.symbol_categories: dict[str, str] = {}
        
        # Configuration
        settings = get_settings()
        self.testnet = settings['testnet']
        
        # Gestionnaire WebSocket dédié
        self.ws_manager = WebSocketManager(testnet=self.testnet, logger=self.logger)
        self.ws_manager.set_ticker_callback(self._update_realtime_data_from_ticker)
        
        # Gestionnaire de volatilité dédié
        self.volatility_tracker = VolatilityTracker(testnet=self.testnet, logger=self.logger)
        self.volatility_tracker.set_active_symbols_callback(self._get_active_symbols)
        
        # Gestionnaire de watchlist dédié
        self.watchlist_manager = WatchlistManager(testnet=self.testnet, logger=self.logger)
        
        # Configuration du signal handler pour Ctrl+C
        signal.signal(signal.SIGINT, self._signal_handler)
        
        self.logger.info("🚀 Orchestrateur du bot (filters + WebSocket prix)")
        self.logger.info("📂 Configuration chargée")
        
        # Démarrer le monitoring des métriques
        start_metrics_monitoring(interval_minutes=5)
    
    def _signal_handler(self, signum, frame):
        """Gestionnaire de signal pour Ctrl+C."""
        self.logger.info("🧹 Arrêt demandé, fermeture de la WebSocket…")
        self.running = False
        # Arrêter le gestionnaire WebSocket
        try:
            self.ws_manager.stop()
        except Exception:
            pass
        # Arrêter le tracker de volatilité
        try:
            self.volatility_tracker.stop_refresh_task()
        except Exception:
            pass
        return
    
    def _update_realtime_data_from_ticker(self, ticker_data: dict):
        """
        Met à jour les données en temps réel à partir des données ticker WebSocket.
        Callback appelé par WebSocketManager.
        
        Args:
            ticker_data (dict): Données du ticker reçues via WebSocket
        """
        try:
            symbol = ticker_data.get("symbol", "")
            if not symbol:
                return
                
            # Construire un diff et fusionner avec l'état précédent pour ne pas écraser des valeurs valides par None
            now_ts = time.time()
            incoming = {
                'funding_rate': ticker_data.get('fundingRate'),
                'volume24h': ticker_data.get('volume24h'),
                'bid1_price': ticker_data.get('bid1Price'),
                'ask1_price': ticker_data.get('ask1Price'),
                'next_funding_time': ticker_data.get('nextFundingTime'),
                'mark_price': ticker_data.get('markPrice'),
                'last_price': ticker_data.get('lastPrice'),
            }
            # Vérifier si des données importantes sont présentes
            important_keys = ['funding_rate', 'volume24h', 'bid1_price', 'ask1_price', 'next_funding_time']
            if any(incoming[key] is not None for key in important_keys):
                with self._realtime_lock:
                    current = self.realtime_data.get(symbol, {})
                    merged = dict(current) if current else {}
                    for k, v in incoming.items():
                        if v is not None:
                            merged[k] = v
                    merged['timestamp'] = now_ts
                    self.realtime_data[symbol] = merged
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur mise à jour données temps réel pour {symbol}: {e}")
    
    
    def _recalculate_funding_time(self, symbol: str) -> str:
        """Retourne le temps restant basé uniquement sur nextFundingTime (WS puis REST)."""
        try:
            with self._realtime_lock:
                realtime_info = self.realtime_data.get(symbol, {})
            ws_ts = realtime_info.get('next_funding_time')
            if ws_ts:
                return self.watchlist_manager.calculate_funding_time_remaining(ws_ts)
            rest_ts = self.original_funding_data.get(symbol)
            if rest_ts:
                return self.watchlist_manager.calculate_funding_time_remaining(rest_ts)
            return "-"
        except Exception:
            return "-"
    
    def _print_price_table(self):
        """Affiche le tableau des prix aligné avec funding, volume en millions, spread et volatilité."""
        # Purger les données de prix trop anciennes et récupérer un snapshot
        try:
            purge_expired(ttl_seconds=getattr(self, "price_ttl_sec", 120))
        except Exception:
            pass
        snapshot = get_snapshot()
        
        if not snapshot:
            if self._first_display:
                self.logger.info("⏳ En attente de la première donnée WS…")
                self._first_display = False  # Ne plus afficher ce message
            return
        
        # Calculer les largeurs de colonnes
        all_symbols = list(self.funding_data.keys())
        max_symbol_len = max(len("Symbole"), max(len(s) for s in all_symbols)) if all_symbols else len("Symbole")
        symbol_w = max(8, max_symbol_len)
        funding_w = 12  # Largeur pour le funding
        volume_w = 10  # Largeur pour le volume en millions
        spread_w = 10  # Largeur pour le spread
        volatility_w = 12  # Largeur pour la volatilité
        funding_time_w = 15  # Largeur pour le temps de funding (avec secondes)
        
        # En-tête
        header = (
            f"{'Symbole':<{symbol_w}} | {'Funding %':>{funding_w}} | "
            f"{'Volume (M)':>{volume_w}} | {'Spread %':>{spread_w}} | "
            f"{'Volatilité %':>{volatility_w}} | {'Funding T':>{funding_time_w}}"
        )
        sep = (
            f"{'-'*symbol_w}-+-{'-'*funding_w}-+-{'-'*volume_w}-+-"
            f"{'-'*spread_w}-+-{'-'*volatility_w}-+-{'-'*funding_time_w}"
        )
        
        print("\n" + header)
        print(sep)
        
        # Données
        for symbol, data in self.funding_data.items():
            # Récupérer les données en temps réel si disponibles
            realtime_info = self.realtime_data.get(symbol, {})
            # Récupérer les valeurs initiales (REST) comme fallbacks
            # data format: (funding, volume, funding_time_remaining, spread_pct, volatility_pct)
            try:
                original_funding = data[0]
                original_volume = data[1]
                original_funding_time = data[2]
            except Exception:
                original_funding = None
                original_volume = None
                original_funding_time = "-"
            
            # Utiliser les données en temps réel si disponibles, sinon fallback vers REST initial
            if realtime_info:
                # Données en temps réel disponibles - gérer les valeurs None
                funding_rate = realtime_info.get('funding_rate')
                funding = float(funding_rate) if funding_rate is not None else original_funding
                
                volume24h = realtime_info.get('volume24h')
                volume = float(volume24h) if volume24h is not None else original_volume
                
                # On ne remplace pas la valeur initiale si la donnée WS est absente
                funding_time_remaining = original_funding_time
                
                # Calculer le spread en temps réel si on a bid/ask
                spread_pct = None
                if realtime_info.get('bid1_price') and realtime_info.get('ask1_price'):
                    try:
                        bid_price = float(realtime_info['bid1_price'])
                        ask_price = float(realtime_info['ask1_price'])
                        if bid_price > 0 and ask_price > 0:
                            mid_price = (ask_price + bid_price) / 2
                            if mid_price > 0:
                                spread_pct = (ask_price - bid_price) / mid_price
                    except (ValueError, TypeError):
                        pass  # Garder spread_pct = None en cas d'erreur
                # Fallback: utiliser la valeur REST calculée au filtrage si le temps réel est indisponible
                if spread_pct is None:
                    try:
                        # data[3] contient spread_pct (ou 0.0 si absent lors du filtrage)
                        spread_pct = data[3]
                    except Exception:
                        pass
                
                # Volatilité: lecture via le tracker dédié
                volatility_pct = self.volatility_tracker.get_cached_volatility(symbol)
            else:
                # Pas de données en temps réel disponibles - utiliser les valeurs initiales REST
                funding = original_funding
                volume = original_volume
                funding_time_remaining = original_funding_time
                # Fallback: utiliser la valeur REST calculée au filtrage
                spread_pct = None
                volatility_pct = None
                
                # Volatilité: lecture via le tracker dédié
                if volatility_pct is None:
                    volatility_pct = self.volatility_tracker.get_cached_volatility(symbol)
                # Essayer de récupérer le spread initial calculé lors du filtrage
                if spread_pct is None:
                    try:
                        spread_pct = data[3]
                    except Exception:
                        pass
            
            # Recalculer le temps de funding (priorité WS, fallback REST)
            current_funding_time = self._recalculate_funding_time(symbol)
            if current_funding_time is None:
                current_funding_time = "-"
            
            # Gérer l'affichage des valeurs null
            if funding is not None:
                funding_pct = funding * 100.0
                funding_str = f"{funding_pct:+{funding_w-1}.4f}%"
            else:
                funding_str = "null"
            
            if volume is not None and volume > 0:
                volume_millions = volume / 1_000_000
                volume_str = f"{volume_millions:,.1f}"
            else:
                volume_str = "null"
            
            if spread_pct is not None:
                spread_pct_display = spread_pct * 100.0
                spread_str = f"{spread_pct_display:+.3f}%"
            else:
                spread_str = "null"
            
            # Formatage de la volatilité
            if volatility_pct is not None:
                volatility_pct_display = volatility_pct * 100.0
                volatility_str = f"{volatility_pct_display:+.3f}%"
            else:
                volatility_str = "-"
            
            line = (
                f"{symbol:<{symbol_w}} | {funding_str:>{funding_w}} | "
                f"{volume_str:>{volume_w}} | {spread_str:>{spread_w}} | "
                f"{volatility_str:>{volatility_w}} | {current_funding_time:>{funding_time_w}}"
            )
            print(line)
        
        print()  # Ligne vide après le tableau
    
    def _display_loop(self):
        """Boucle d'affichage toutes les 15 secondes."""
        while self.running:
            self._print_price_table()
            
            # Attendre 15 secondes
            for _ in range(150):  # 150 * 0.1s = 15s
                if not self.running:
                    break
                time.sleep(0.1)
    
    # Anciennes callbacks WS supprimées (remplacées par PublicWSConnection)
    
    def start(self):
        """Démarre le suivi des prix avec filtrage par funding."""
        # Charger et valider la configuration via le watchlist manager
        try:
            config = self.watchlist_manager.load_and_validate_config()
        except ValueError as e:
            self.logger.error(f"❌ Erreur de configuration : {e}")
            self.logger.error("💡 Corrigez les paramètres dans src/parameters.yaml ou les variables d'environnement")
            return  # Arrêt propre sans sys.exit
        
        # Vérifier si le fichier de config existe
        config_path = "src/parameters.yaml"
        if not os.path.exists(config_path):
            self.logger.info("ℹ️ Aucun fichier de paramètres trouvé (src/parameters.yaml) → utilisation des valeurs par défaut.")
        else:
            self.logger.info("ℹ️ Configuration chargée depuis src/parameters.yaml")
        
        # Créer un client PUBLIC pour récupérer l'URL publique (aucune clé requise)
        client = BybitPublicClient(
            testnet=self.testnet,
            timeout=10,
        )
        
        base_url = client.public_base_url()
        
        # Récupérer l'univers perp
        perp_data = get_perp_symbols(base_url, timeout=10)
        self.logger.info(f"🗺️ Univers perp récupéré : linear={len(perp_data['linear'])} | inverse={len(perp_data['inverse'])} | total={perp_data['total']}")
        # Stocker le mapping officiel des catégories
        try:
            self.symbol_categories = perp_data.get("categories", {}) or {}
        except Exception:
            self.symbol_categories = {}
        
        # Configurer les gestionnaires avec les catégories
        self.volatility_tracker.set_symbol_categories(self.symbol_categories)
        self.watchlist_manager.symbol_categories = self.symbol_categories
        
        # Configurer le tracker de volatilité
        volatility_ttl_sec = int(config.get("volatility_ttl_sec", 120) or 120)
        self.volatility_tracker.ttl_seconds = volatility_ttl_sec
        self.price_ttl_sec = 120
        
        # Afficher les filtres (délégué au watchlist manager)
        self._log_filter_config(config, volatility_ttl_sec)
        
        # Construire la watchlist via le gestionnaire dédié
        try:
            self.linear_symbols, self.inverse_symbols, self.funding_data = self.watchlist_manager.build_watchlist(
                base_url, perp_data, self.volatility_tracker
            )
            # Récupérer les données originales de funding
            self.original_funding_data = self.watchlist_manager.get_original_funding_data()
        except Exception as e:
            if "Aucun symbole" in str(e) or "Aucun funding" in str(e):
                # Convertir en exceptions spécifiques
                if "Aucun symbole" in str(e):
                    raise NoSymbolsError(str(e))
                else:
                    from errors import FundingUnavailableError
                    raise FundingUnavailableError(str(e))
            else:
                raise
        
        self.logger.info(f"📊 Symboles linear: {len(self.linear_symbols)}, inverse: {len(self.inverse_symbols)}")
        
        # Démarrer le tracker de volatilité (arrière-plan) AVANT les WS bloquantes
        self.volatility_tracker.start_refresh_task()
        
        # Démarrer l'affichage
        self.display_thread = threading.Thread(target=self._display_loop)
        self.display_thread.daemon = True
        self.display_thread.start()

        # Démarrer les connexions WebSocket via le gestionnaire dédié
        if self.linear_symbols or self.inverse_symbols:
            self.ws_manager.start_connections(self.linear_symbols, self.inverse_symbols)
        else:
            self.logger.warning("⚠️ Aucun symbole valide trouvé")
            raise NoSymbolsError("Aucun symbole valide trouvé")
    
    
    def _get_active_symbols(self) -> List[str]:
        """Retourne la liste des symboles actuellement actifs."""
        return list(self.funding_data.keys())
    
    def _log_filter_config(self, config: Dict, volatility_ttl_sec: int):
        """Affiche la configuration des filtres."""
        # Extraire les paramètres pour l'affichage
        categorie = config.get("categorie", "both")
        funding_min = config.get("funding_min")
        funding_max = config.get("funding_max")
        volume_min_millions = config.get("volume_min_millions")
        spread_max = config.get("spread_max")
        volatility_min = config.get("volatility_min")
        volatility_max = config.get("volatility_max")
        limite = config.get("limite")
        funding_time_min_minutes = config.get("funding_time_min_minutes")
        funding_time_max_minutes = config.get("funding_time_max_minutes")
        
        # Formater pour l'affichage
        min_display = f"{funding_min:.6f}" if funding_min is not None else "none"
        max_display = f"{funding_max:.6f}" if funding_max is not None else "none"
        volume_display = f"{volume_min_millions:.1f}" if volume_min_millions is not None else "none"
        spread_display = f"{spread_max:.4f}" if spread_max is not None else "none"
        volatility_min_display = f"{volatility_min:.3f}" if volatility_min is not None else "none"
        volatility_max_display = f"{volatility_max:.3f}" if volatility_max is not None else "none"
        limite_display = str(limite) if limite is not None else "none"
        ft_min_display = str(funding_time_min_minutes) if funding_time_min_minutes is not None else "none"
        ft_max_display = str(funding_time_max_minutes) if funding_time_max_minutes is not None else "none"
        
        self.logger.info(
            f"🎛️ Filtres | catégorie={categorie} | funding_min={min_display} | "
            f"funding_max={max_display} | volume_min_millions={volume_display} | "
            f"spread_max={spread_display} | volatility_min={volatility_min_display} | "
            f"volatility_max={volatility_max_display} | ft_min(min)={ft_min_display} | "
            f"ft_max(min)={ft_max_display} | limite={limite_display} | vol_ttl={volatility_ttl_sec}s"
        )
    
    # Runners legacy supprimés (isolation par PublicWSConnection en place)


def main():
    """Fonction principale."""
    tracker = PriceTracker()
    try:
        tracker.start()
    except Exception as e:
        tracker.logger.error(f"❌ Erreur : {e}")
        tracker.running = False
        # Laisser le code appelant décider (ne pas sys.exit ici)


if __name__ == "__main__":
    main()
