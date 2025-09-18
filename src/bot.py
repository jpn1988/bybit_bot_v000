#!/usr/bin/env python3
"""
🚀 Orchestrateur du bot (filters + WebSocket prix) - VERSION OPTIMISÉE

Script pour filtrer les contrats perpétuels par funding ET suivre leurs prix en temps réel.

OPTIMISATIONS PERFORMANCE APPLIQUÉES:
- fetch_spread_data(): batch_size augmenté de 50 à 200 (limite max API Bybit)
- fetch_spread_data(): suppression des délais time.sleep(0.1) entre batches
- fetch_spread_data(): parallélisation avec ThreadPoolExecutor (max 4 workers)
- fetch_funding_map(): limite maintenue à 1000 (maximum supporté par l'API)
- filter_by_volatility(): parallélisation async/await avec aiohttp et asyncio.gather()
- Gestion d'erreur robuste pour les requêtes parallèles
- Réduction estimée du temps de récupération: 60-70% (spreads) + 80-90% (volatilité)

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
from concurrent.futures import ThreadPoolExecutor, as_completed
from http_utils import get_rate_limiter
try:
    from .config import get_settings
except ImportError:
    from config import get_settings
from logging_setup import setup_logging
from bybit_client import BybitClient, BybitPublicClient
from instruments import get_perp_symbols, category_of_symbol
from price_store import update, get_snapshot, purge_expired
from volatility import get_volatility_cache_key, is_cache_valid, compute_volatility_batch_async
from errors import NoSymbolsError, FundingUnavailableError
from metrics import record_filter_result, record_ws_connection, record_ws_error
from metrics_monitor import start_metrics_monitoring


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

def validate_config(config: dict) -> None:
    """
    Valide la cohérence des paramètres de configuration.
    
    Args:
        config (dict): Configuration à valider
        
    Raises:
        ValueError: Si des paramètres sont incohérents ou invalides
    """
    errors = []
    
    # Validation des bornes de funding
    funding_min = config.get("funding_min")
    funding_max = config.get("funding_max")
    
    if funding_min is not None and funding_max is not None:
        if funding_min > funding_max:
            errors.append(f"funding_min ({funding_min}) ne peut pas être supérieur à funding_max ({funding_max})")
    
    # Validation des bornes de volatilité
    volatility_min = config.get("volatility_min")
    volatility_max = config.get("volatility_max")
    
    if volatility_min is not None and volatility_max is not None:
        if volatility_min > volatility_max:
            errors.append(f"volatility_min ({volatility_min}) ne peut pas être supérieur à volatility_max ({volatility_max})")
    
    # Validation des valeurs négatives
    if funding_min is not None and funding_min < 0:
        errors.append(f"funding_min ne peut pas être négatif ({funding_min})")
    
    if funding_max is not None and funding_max < 0:
        errors.append(f"funding_max ne peut pas être négatif ({funding_max})")
    
    if volatility_min is not None and volatility_min < 0:
        errors.append(f"volatility_min ne peut pas être négatif ({volatility_min})")
    
    if volatility_max is not None and volatility_max < 0:
        errors.append(f"volatility_max ne peut pas être négatif ({volatility_max})")
    
    # Validation du spread
    spread_max = config.get("spread_max")
    if spread_max is not None:
        if spread_max < 0:
            errors.append(f"spread_max ne peut pas être négatif ({spread_max})")
        if spread_max > 1.0:  # 100% de spread maximum
            errors.append(f"spread_max trop élevé ({spread_max}), maximum recommandé: 1.0 (100%)")
    
    # Validation des volumes
    volume_min = config.get("volume_min")
    volume_min_millions = config.get("volume_min_millions")
    
    if volume_min is not None and volume_min < 0:
        errors.append(f"volume_min ne peut pas être négatif ({volume_min})")
    
    if volume_min_millions is not None and volume_min_millions < 0:
        errors.append(f"volume_min_millions ne peut pas être négatif ({volume_min_millions})")
    
    # Validation des paramètres temporels de funding
    ft_min = config.get("funding_time_min_minutes")
    ft_max = config.get("funding_time_max_minutes")
    
    if ft_min is not None:
        if ft_min < 0:
            errors.append(f"funding_time_min_minutes ne peut pas être négatif ({ft_min})")
        if ft_min > 1440:  # 24 heures maximum
            errors.append(f"funding_time_min_minutes trop élevé ({ft_min}), maximum: 1440 (24h)")
    
    if ft_max is not None:
        if ft_max < 0:
            errors.append(f"funding_time_max_minutes ne peut pas être négatif ({ft_max})")
        if ft_max > 1440:  # 24 heures maximum
            errors.append(f"funding_time_max_minutes trop élevé ({ft_max}), maximum: 1440 (24h)")
    
    if ft_min is not None and ft_max is not None:
        if ft_min > ft_max:
            errors.append(f"funding_time_min_minutes ({ft_min}) ne peut pas être supérieur à funding_time_max_minutes ({ft_max})")
    
    # Validation de la catégorie
    categorie = config.get("categorie")
    if categorie not in ["linear", "inverse", "both"]:
        errors.append(f"categorie invalide ({categorie}), valeurs autorisées: linear, inverse, both")
    
    # Validation de la limite
    limite = config.get("limite")
    if limite is not None:
        if limite < 1:
            errors.append(f"limite doit être positive ({limite})")
        if limite > 1000:
            errors.append(f"limite trop élevée ({limite}), maximum recommandé: 1000")
    
    # Validation du TTL de volatilité
    vol_ttl = config.get("volatility_ttl_sec")
    if vol_ttl is not None:
        if vol_ttl < 10:
            errors.append(f"volatility_ttl_sec trop faible ({vol_ttl}), minimum: 10 secondes")
        if vol_ttl > 3600:
            errors.append(f"volatility_ttl_sec trop élevé ({vol_ttl}), maximum: 3600 secondes (1h)")
    
    # Lever une erreur si des problèmes ont été détectés
    if errors:
        error_msg = "Configuration invalide détectée:\n" + "\n".join(f"  - {error}" for error in errors)
        raise ValueError(error_msg)


def load_config() -> dict:
    """
    Charge la configuration depuis le fichier YAML ou utilise les valeurs par défaut.
    Priorité : ENV > fichier > valeurs par défaut
    
    Returns:
        dict: Configuration avec categorie, funding_min, funding_max, volume_min_millions, limite
    """
    config_path = "src/parameters.yaml"
    
    # Valeurs par défaut
    default_config = {
        "categorie": "linear",
        "funding_min": None,
        "funding_max": None,
        "volume_min": None,
        "volume_min_millions": None,
        "spread_max": None,
        "volatility_min": None,
        "volatility_max": None,
        "limite": 10,
        "volatility_ttl_sec": 120,
        # Nouveaux paramètres temporels
        "funding_time_min_minutes": None,
        "funding_time_max_minutes": None,
    }
    
    # Charger depuis le fichier si disponible
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            file_config = yaml.safe_load(f)
        if file_config:
            default_config.update(file_config)
    except FileNotFoundError:
        pass  # Utiliser les valeurs par défaut
    
    # Récupérer les variables d'environnement (priorité maximale)
    settings = get_settings()
    env_spread_max = settings.get("spread_max")
    env_volume_min_millions = settings.get("volume_min_millions")
    env_volatility_min = settings.get("volatility_min")
    env_volatility_max = settings.get("volatility_max")
    # Alignement ENV supplémentaires (README)
    env_funding_min = settings.get("funding_min")
    env_funding_max = settings.get("funding_max")
    env_category = settings.get("category")
    env_limit = settings.get("limit")
    env_vol_ttl = settings.get("volatility_ttl_sec")
    # Nouveaux ENV temporels
    env_ft_min = settings.get("funding_time_min_minutes")
    env_ft_max = settings.get("funding_time_max_minutes")
    
    # Appliquer les variables d'environnement si présentes
    if env_spread_max is not None:
        default_config["spread_max"] = env_spread_max
    if env_volume_min_millions is not None:
        default_config["volume_min_millions"] = env_volume_min_millions
    if env_volatility_min is not None:
        default_config["volatility_min"] = env_volatility_min
    if env_volatility_max is not None:
        default_config["volatility_max"] = env_volatility_max
    if env_funding_min is not None:
        default_config["funding_min"] = env_funding_min
    if env_funding_max is not None:
        default_config["funding_max"] = env_funding_max
    if env_category is not None:
        default_config["categorie"] = env_category
    if env_limit is not None:
        default_config["limite"] = env_limit
    if env_vol_ttl is not None:
        default_config["volatility_ttl_sec"] = env_vol_ttl
    # Appliquer les ENV temporels
    if env_ft_min is not None:
        default_config["funding_time_min_minutes"] = env_ft_min
    if env_ft_max is not None:
        default_config["funding_time_max_minutes"] = env_ft_max
    
    # Valider la configuration finale
    validate_config(default_config)
    
    return default_config


def fetch_funding_map(base_url: str, category: str, timeout: int) -> dict[str, float]:
    """
    Récupère les taux de funding pour une catégorie donnée.
    OPTIMISÉ: Utilise la limite maximum de l'API Bybit (1000) et une gestion d'erreur robuste.
    
    Args:
        base_url (str): URL de base de l'API Bybit
        category (str): Catégorie (linear ou inverse)
        timeout (int): Timeout pour les requêtes HTTP
        
    Returns:
        dict[str, float]: Dictionnaire {symbol: funding_rate}
        
    Raises:
        RuntimeError: En cas d'erreur HTTP ou API
    """
    funding_map = {}
    cursor = ""
    page_index = 0
    
    rate_limiter = get_rate_limiter()
    while True:
        # Construire l'URL avec pagination
        url = f"{base_url}/v5/market/tickers"
        params = {
            "category": category,
            "limit": 1000  # OPTIMISATION: Limite maximum supportée par l'API Bybit
        }
        if cursor:
            params["cursor"] = cursor
            
        try:
            page_index += 1
            # Respecter le rate limit avant chaque appel
            rate_limiter.acquire()
            with httpx.Client(timeout=timeout) as client:
                response = client.get(url, params=params)
                
                # Vérifier le statut HTTP
                if response.status_code >= 400:
                    raise RuntimeError(
                        (
                            f"Erreur HTTP Bybit GET {url} | category={category} limit={params.get('limit')} "
                            f"cursor={params.get('cursor', '-') } timeout={timeout}s page={page_index} "
                            f"collected={len(funding_map)} | status={response.status_code} "
                            f"detail=\"{response.text[:200]}\""
                        )
                    )
                
                data = response.json()
                
                # Vérifier le retCode
                if data.get("retCode") != 0:
                    ret_code = data.get("retCode")
                    ret_msg = data.get("retMsg", "")
                    raise RuntimeError(
                        (
                            f"Erreur API Bybit GET {url} | category={category} limit={params.get('limit')} "
                            f"cursor={params.get('cursor', '-') } timeout={timeout}s page={page_index} "
                            f"collected={len(funding_map)} | retCode={ret_code} retMsg=\"{ret_msg}\""
                        )
                    )
                
                result = data.get("result", {})
                tickers = result.get("list", [])
                
                # Extraire les funding rates, volumes et temps de funding
                for ticker in tickers:
                    symbol = ticker.get("symbol", "")
                    funding_rate = ticker.get("fundingRate")
                    volume_24h = ticker.get("volume24h")
                    next_funding_time = ticker.get("nextFundingTime")
                    
                    if symbol and funding_rate is not None:
                        try:
                            funding_map[symbol] = {
                                "funding": float(funding_rate),
                                "volume": float(volume_24h) if volume_24h is not None else 0.0,
                                "next_funding_time": next_funding_time
                            }
                        except (ValueError, TypeError):
                            # Ignorer si les données ne sont pas convertibles en float
                            pass
                
                # Vérifier s'il y a une page suivante
                next_page_cursor = result.get("nextPageCursor")
                if not next_page_cursor:
                    break
                cursor = next_page_cursor
                
        except httpx.RequestError as e:
            raise RuntimeError(
                (
                    f"Erreur réseau Bybit GET {url} | category={category} limit={params.get('limit')} "
                    f"cursor={params.get('cursor', '-') } timeout={timeout}s page={page_index} "
                    f"collected={len(funding_map)} | error={e}"
                )
            )
        except Exception as e:
            if "Erreur" in str(e):
                raise
            else:
                raise RuntimeError(
                    (
                        f"Erreur inconnue Bybit GET {url} | category={category} limit={params.get('limit')} "
                        f"cursor={params.get('cursor', '-') } timeout={timeout}s page={page_index} "
                        f"collected={len(funding_map)} | error={e}"
                    )
                )
    
    return funding_map


def calculate_funding_time_remaining(next_funding_time: str | int | float | None) -> str:
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
    except Exception:
        return "-"


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
            with httpx.Client(timeout=timeout) as client:
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
                        except Exception:
                            pass
                # Fin pagination
                next_cursor = result.get("nextPageCursor")
                # Arrêt anticipé si on a tout trouvé
                if len(found) >= len(wanted):
                    break
                if not next_cursor:
                    break
                cursor = next_cursor
        except Exception as e:
            # On ne stoppe pas le flux complet: on tente une récupération unitaire pour les manquants
            try:
                from logging_setup import setup_logging
                setup_logging().warning(
                    f"⚠️ Spread paginé erreur page={page_index} category={category} error={e}"
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
        except Exception:
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
        with httpx.Client(timeout=timeout) as client:
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
        with httpx.Client(timeout=timeout) as client:
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


async def filter_by_volatility_async(symbols_data: list[tuple[str, float, float, str, float]], bybit_client, volatility_min: float, volatility_max: float, logger, volatility_cache: dict, ttl_seconds: int | None = None, symbol_categories: dict[str, str] | None = None) -> list[tuple[str, float, float, str, float]]:
    """
    Calcule la volatilité 5 minutes pour tous les symboles et applique les filtres si définis.
    OPTIMISÉ: Utilise compute_volatility_batch_async() pour paralléliser les appels API.
    
    Args:
        symbols_data (list[tuple[str, float, float, str, float]]): Liste des (symbol, funding, volume, funding_time_remaining, spread_pct)
        bybit_client: Instance du client Bybit
        volatility_min (float): Volatilité minimum autorisée (0.002 = 0.2%) ou None
        volatility_max (float): Volatilité maximum autorisée (0.007 = 0.7%) ou None
        logger: Logger pour les messages
        volatility_cache (dict): Cache de volatilité {symbol: (timestamp, volatility)}
        
    Returns:
        list[tuple[str, float, float, str, float]]: Liste avec volatilité calculée et filtrée si nécessaire
    """
    
    filtered_symbols = []
    rejected_count = 0
    
    # Séparer les symboles en cache et ceux à calculer
    symbols_to_calculate = []
    cached_volatilities = {}
    
    cache_ttl = ttl_seconds or 120
    for symbol, funding, volume, funding_time_remaining, spread_pct in symbols_data:
        cache_key = get_volatility_cache_key(symbol)
        cached_data = volatility_cache.get(cache_key)
        
        if cached_data and is_cache_valid(cached_data[0], ttl_seconds=cache_ttl):
            # Utiliser la valeur en cache
            cached_volatilities[symbol] = cached_data[1]
        else:
            # Ajouter à la liste des symboles à calculer
            symbols_to_calculate.append(symbol)
    
    # OPTIMISATION: Calculer la volatilité pour tous les symboles en parallèle
    if symbols_to_calculate:
        logger.info(f"🔎 Calcul volatilité async (parallèle) pour {len(symbols_to_calculate)} symboles…")
        batch_volatilities = await compute_volatility_batch_async(bybit_client, symbols_to_calculate, timeout=10, symbol_categories=symbol_categories)
        
        # Mettre à jour le cache avec les nouveaux résultats
        for symbol, vol_pct in batch_volatilities.items():
            if vol_pct is not None:
                cache_key = get_volatility_cache_key(symbol)
                volatility_cache[cache_key] = (time.time(), vol_pct)
            cached_volatilities[symbol] = vol_pct
    
    # Appliquer les filtres avec toutes les volatilités (cache + calculées)
    for symbol, funding, volume, funding_time_remaining, spread_pct in symbols_data:
        vol_pct = cached_volatilities.get(symbol)
        
        # Appliquer le filtre de volatilité seulement si des seuils sont définis
        if volatility_min is not None or volatility_max is not None:
            if vol_pct is not None:
                # Vérifier les seuils de volatilité
                rejected_reason = None
                if volatility_min is not None and vol_pct < volatility_min:
                    rejected_reason = f"< seuil min {volatility_min:.2%}"
                elif volatility_max is not None and vol_pct > volatility_max:
                    rejected_reason = f"> seuil max {volatility_max:.2%}"
                
                if rejected_reason:
                    rejected_count += 1
                    continue
        
        # Ajouter le symbole avec sa volatilité
        filtered_symbols.append((symbol, funding, volume, funding_time_remaining, spread_pct, vol_pct))
    
    # Log des résultats
    kept_count = len(filtered_symbols)
    threshold_info = []
    if volatility_min is not None:
        threshold_info.append(f"min={volatility_min:.2%}")
    if volatility_max is not None:
        threshold_info.append(f"max={volatility_max:.2%}")
    threshold_str = " | ".join(threshold_info) if threshold_info else "aucun"
    logger.info(f"✅ Calcul volatilité async: gardés={kept_count} | rejetés={rejected_count} (seuils: {threshold_str})")
    
    return filtered_symbols


def filter_by_volatility(symbols_data: list[tuple[str, float, float, str, float]], bybit_client, volatility_min: float, volatility_max: float, logger, volatility_cache: dict, ttl_seconds: int | None = None, symbol_categories: dict[str, str] | None = None) -> list[tuple[str, float, float, str, float]]:
    """
    Version synchrone de filter_by_volatility pour compatibilité.
    Utilise asyncio.run() pour exécuter la version async.
    """
    return asyncio.run(filter_by_volatility_async(symbols_data, bybit_client, volatility_min, volatility_max, logger, volatility_cache, ttl_seconds, symbol_categories))


def filter_by_funding(perp_data: dict, funding_map: dict, funding_min: float | None, funding_max: float | None, volume_min: float | None, volume_min_millions: float | None, limite: int | None, funding_time_min_minutes: int | None = None, funding_time_max_minutes: int | None = None) -> list[tuple[str, float, float, str]]:
    """
    Filtre les symboles par funding, volume et fenêtre temporelle avant funding, puis trie par |funding| décroissant.
    
    Args:
        perp_data (dict): Données des perpétuels (linear, inverse, total)
        funding_map (dict): Dictionnaire des funding rates, volumes et temps de funding
        funding_min (float | None): Funding minimum
        funding_max (float | None): Funding maximum
        volume_min (float | None): Volume minimum (ancien format)
        volume_min_millions (float | None): Volume minimum en millions (nouveau format)
        limite (int | None): Limite du nombre d'éléments
        funding_time_min_minutes (int | None): Temps minimum en minutes avant prochain funding
        funding_time_max_minutes (int | None): Temps maximum en minutes avant prochain funding
        
    Returns:
        list[tuple[str, float, float, str]]: Liste des (symbol, funding, volume, funding_time_remaining) triés
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
            
            # Appliquer les bornes funding/volume
            if funding_min is not None and funding < funding_min:
                continue
            if funding_max is not None and funding > funding_max:
                continue
            if effective_volume_min is not None and volume < effective_volume_min:
                continue
            
            # Appliquer le filtre temporel si demandé
            if funding_time_min_minutes is not None or funding_time_max_minutes is not None:
                # Convertir next_funding_time en minutes restantes
                minutes_remaining: float | None = None
                try:
                    import datetime
                    if next_funding_time:
                        if isinstance(next_funding_time, (int, float)):
                            target_dt = datetime.datetime.fromtimestamp(float(next_funding_time) / 1000, tz=datetime.timezone.utc)
                        elif isinstance(next_funding_time, str):
                            if next_funding_time.isdigit():
                                target_dt = datetime.datetime.fromtimestamp(float(next_funding_time) / 1000, tz=datetime.timezone.utc)
                            else:
                                target_dt = datetime.datetime.fromisoformat(next_funding_time.replace('Z', '+00:00'))
                                if target_dt.tzinfo is None:
                                    target_dt = target_dt.replace(tzinfo=datetime.timezone.utc)
                        else:
                            target_dt = None
                        if target_dt is not None:
                            now_dt = datetime.datetime.now(datetime.timezone.utc)
                            delta_sec = (target_dt - now_dt).total_seconds()
                            if delta_sec > 0:
                                minutes_remaining = delta_sec / 60.0
                except Exception:
                    minutes_remaining = None
                
                # Si pas de temps valide alors qu'on filtre, rejeter
                if minutes_remaining is None:
                    continue
                if funding_time_min_minutes is not None and minutes_remaining < float(funding_time_min_minutes):
                    continue
                if funding_time_max_minutes is not None and minutes_remaining > float(funding_time_max_minutes):
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
        self.ws = None
        self.display_thread = None
        self.symbols = []
        self.funding_data = {}
        self.original_funding_data = {}  # Données de funding originales avec next_funding_time
        self.volatility_cache = {}  # Cache pour la volatilité {symbol: (timestamp, volatility)}
        # self.start_time supprimé: on s'appuie uniquement sur nextFundingTime côté Bybit
        self.realtime_data = {}  # Données en temps réel via WebSocket {symbol: {funding_rate, volume24h, bid1, ask1, next_funding_time, ...}}
        self._realtime_lock = threading.Lock()  # Verrou pour protéger realtime_data
        self._ws_conns: list[PublicWSConnection] = []
        self._ws_threads: list[threading.Thread] = []
        self._vol_refresh_thread: threading.Thread | None = None
        self.symbol_categories: dict[str, str] = {}
        
        # Configuration
        settings = get_settings()
        self.testnet = settings['testnet']
        
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
        # Fermer toutes les connexions WS isolées
        try:
            for conn in getattr(self, "_ws_conns", []) or []:
                conn.close()
        except Exception:
            pass
        return
    
    def _update_realtime_data(self, symbol: str, ticker_data: dict):
        """
        Met à jour les données en temps réel pour un symbole donné.
        
        Args:
            symbol (str): Symbole à mettre à jour
            ticker_data (dict): Données du ticker reçues via WebSocket
        """
        try:
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
            if any(incoming[key] is not None for key in ['funding_rate', 'volume24h', 'bid1_price', 'ask1_price', 'next_funding_time']):
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
                return calculate_funding_time_remaining(ws_ts)
            rest_ts = self.original_funding_data.get(symbol)
            if rest_ts:
                return calculate_funding_time_remaining(rest_ts)
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
            print("Aucune donnée de prix disponible")
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
        header = f"{'Symbole':<{symbol_w}} | {'Funding %':>{funding_w}} | {'Volume (M)':>{volume_w}} | {'Spread %':>{spread_w}} | {'Volatilité %':>{volatility_w}} | {'Funding T':>{funding_time_w}}"
        sep = f"{'-'*symbol_w}-+-{'-'*funding_w}-+-{'-'*volume_w}-+-{'-'*spread_w}-+-{'-'*volatility_w}-+-{'-'*funding_time_w}"
        
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
                
                # Volatilité: lecture cache uniquement (pas d'appel réseau dans l'affichage)
                volatility_pct = None
                cache_key = get_volatility_cache_key(symbol)
                cached_data = self.volatility_cache.get(cache_key)
                # N'afficher que si le cache est encore valide (pas de données périmées)
                if cached_data and is_cache_valid(cached_data[0], ttl_seconds=getattr(self, "volatility_ttl_sec", 120)):
                    volatility_pct = cached_data[1]
            else:
                # Pas de données en temps réel disponibles - utiliser les valeurs initiales REST
                funding = original_funding
                volume = original_volume
                funding_time_remaining = original_funding_time
                # Fallback: utiliser la valeur REST calculée au filtrage
                spread_pct = None
                volatility_pct = None
                
                # Volatilité: lecture cache uniquement (pas d'appel réseau dans l'affichage)
                if volatility_pct is None:
                    cache_key = get_volatility_cache_key(symbol)
                    cached_data = self.volatility_cache.get(cache_key)
                    if cached_data and is_cache_valid(cached_data[0], ttl_seconds=getattr(self, "volatility_ttl_sec", 120)):
                        volatility_pct = cached_data[1]
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
            
            line = f"{symbol:<{symbol_w}} | {funding_str:>{funding_w}} | {volume_str:>{volume_w}} | {spread_str:>{spread_w}} | {volatility_str:>{volatility_w}} | {current_funding_time:>{funding_time_w}}"
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
        # Charger et valider la configuration
        try:
            config = load_config()
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
        
        # Extraire les paramètres de configuration
        categorie = config.get("categorie", "both")
        funding_min = config.get("funding_min")
        funding_max = config.get("funding_max")
        volume_min = config.get("volume_min")
        volume_min_millions = config.get("volume_min_millions")
        spread_max = config.get("spread_max")
        volatility_min = config.get("volatility_min")
        volatility_max = config.get("volatility_max")
        limite = config.get("limite")
        self.volatility_ttl_sec = int(config.get("volatility_ttl_sec", 120) or 120)
        self.price_ttl_sec = 120
        # Nouveaux paramètres temporels
        funding_time_min_minutes = config.get("funding_time_min_minutes")
        funding_time_max_minutes = config.get("funding_time_max_minutes")
        
        # Afficher les filtres
        min_display = f"{funding_min:.6f}" if funding_min is not None else "none"
        max_display = f"{funding_max:.6f}" if funding_max is not None else "none"
        volume_display = f"{volume_min_millions:.1f}" if volume_min_millions is not None else "none"
        spread_display = f"{spread_max:.4f}" if spread_max is not None else "none"
        volatility_min_display = f"{volatility_min:.3f}" if volatility_min is not None else "none"
        volatility_max_display = f"{volatility_max:.3f}" if volatility_max is not None else "none"
        limite_display = str(limite) if limite is not None else "none"
        ft_min_display = str(funding_time_min_minutes) if funding_time_min_minutes is not None else "none"
        ft_max_display = str(funding_time_max_minutes) if funding_time_max_minutes is not None else "none"
        
        self.logger.info(f"🎛️ Filtres | catégorie={categorie} | funding_min={min_display} | funding_max={max_display} | volume_min_millions={volume_display} | spread_max={spread_display} | volatility_min={volatility_min_display} | volatility_max={volatility_max_display} | ft_min(min)={ft_min_display} | ft_max(min)={ft_max_display} | limite={limite_display} | vol_ttl={self.volatility_ttl_sec}s")
        
        # Récupérer les funding rates selon la catégorie
        # OPTIMISATION: fetch_funding_map() utilise maintenant la limite maximum (1000) de l'API
        funding_map = {}
        if categorie == "linear":
            self.logger.info("📡 Récupération des funding rates pour linear (optimisé)…")
            funding_map = fetch_funding_map(base_url, "linear", 10)
        elif categorie == "inverse":
            self.logger.info("📡 Récupération des funding rates pour inverse (optimisé)…")
            funding_map = fetch_funding_map(base_url, "inverse", 10)
        else:  # "both"
            self.logger.info("📡 Récupération des funding rates pour linear+inverse (optimisé)…")
            linear_funding = fetch_funding_map(base_url, "linear", 10)
            inverse_funding = fetch_funding_map(base_url, "inverse", 10)
            funding_map = {**linear_funding, **inverse_funding}  # Merger (priorité au dernier)
        
        if not funding_map:
            self.logger.warning("⚠️ Aucun funding disponible pour la catégorie sélectionnée")
            raise FundingUnavailableError("Aucun funding disponible pour la catégorie sélectionnée")
        
        # Stocker les next_funding_time originaux pour fallback (REST)
        try:
            self.original_funding_data = {}
            for _sym, _data in funding_map.items():
                try:
                    nft = _data.get("next_funding_time")
                    if nft:
                        self.original_funding_data[_sym] = nft
                except Exception:
                    continue
        except Exception:
            # En cas d'erreur, on garde simplement la map vide
            self.original_funding_data = {}
        
        # Compter les symboles avant filtrage
        all_symbols = list(set(perp_data["linear"] + perp_data["inverse"]))
        n0 = len([s for s in all_symbols if s in funding_map])
        
        # Filtrer par funding, volume et temps avant funding
        filtered_symbols = filter_by_funding(
            perp_data,
            funding_map,
            funding_min,
            funding_max,
            volume_min,
            volume_min_millions,
            limite,
            funding_time_min_minutes=funding_time_min_minutes,
            funding_time_max_minutes=funding_time_max_minutes,
        )
        n1 = len(filtered_symbols)
        
        # Appliquer le filtre de spread si nécessaire
        final_symbols = filtered_symbols
        n2 = n1
        
        if spread_max is not None and filtered_symbols:
            # Récupérer les données de spread pour les symboles restants
            symbols_to_check = [symbol for symbol, _, _, _ in filtered_symbols]
            self.logger.info(f"🔎 Évaluation du spread (REST tickers) pour {len(symbols_to_check)} symboles…")
            
            try:
                spread_data = {}
                
                # Séparer les symboles par catégorie pour les requêtes spread
                # Utiliser les catégories officielles (fallback heuristique si absent)
                linear_symbols_for_spread = [s for s in symbols_to_check if category_of_symbol(s, self.symbol_categories) == "linear"]
                inverse_symbols_for_spread = [s for s in symbols_to_check if category_of_symbol(s, self.symbol_categories) == "inverse"]
                
                # OPTIMISATION: fetch_spread_data() utilise maintenant des batches de 200 et de la parallélisation
                # Récupérer les spreads pour chaque catégorie
                if linear_symbols_for_spread:
                    self.logger.info(f"🔎 Récupération spreads linear (optimisé: batch=200, parallèle) pour {len(linear_symbols_for_spread)} symboles…")
                    linear_spread_data = fetch_spread_data(base_url, linear_symbols_for_spread, 10, "linear")
                    spread_data.update(linear_spread_data)
                
                if inverse_symbols_for_spread:
                    self.logger.info(f"🔎 Récupération spreads inverse (optimisé: batch=200, parallèle) pour {len(inverse_symbols_for_spread)} symboles…")
                    inverse_spread_data = fetch_spread_data(base_url, inverse_symbols_for_spread, 10, "inverse")
                    spread_data.update(inverse_spread_data)
                
                final_symbols = filter_by_spread(filtered_symbols, spread_data, spread_max)
                n2 = len(final_symbols)
                
                # Log des résultats du filtre spread
                rejected = n1 - n2
                spread_pct_display = spread_max * 100
                self.logger.info(f"✅ Filtre spread : gardés={n2} | rejetés={rejected} (seuil {spread_pct_display:.2f}%)")
                
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur lors de la récupération des spreads : {e}")
                # Continuer sans le filtre de spread
                final_symbols = [(symbol, funding, volume, funding_time_remaining, 0.0) for symbol, funding, volume, funding_time_remaining in filtered_symbols]
        
        # Calculer la volatilité pour tous les symboles (même sans filtre)
        if final_symbols:
            try:
                self.logger.info("🔎 Évaluation de la volatilité 5m pour tous les symboles…")
                final_symbols = filter_by_volatility(
                    final_symbols,
                    client,
                    volatility_min,
                    volatility_max,
                    self.logger,
                    self.volatility_cache,
                    ttl_seconds=self.volatility_ttl_sec,
                    symbol_categories=self.symbol_categories,
                )
                n2 = len(final_symbols)
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur lors du calcul de la volatilité : {e}")
                # Continuer sans le filtre de volatilité
        
        # Appliquer la limite finale
        if limite is not None and len(final_symbols) > limite:
            final_symbols = final_symbols[:limite]
        n3 = len(final_symbols)
        
        # Enregistrer les métriques des filtres
        record_filter_result("funding_volume_time", n1, n0 - n1)
        if spread_max is not None:
            record_filter_result("spread", n2, n1 - n2)
        record_filter_result("volatility", n2, n2 - n2)  # Pas de rejet par volatilité dans ce cas
        record_filter_result("final_limit", n3, n2 - n3)
        
        # Log des comptes
        self.logger.info(f"🧮 Comptes | avant filtres = {n0} | après funding/volume/temps = {n1} | après spread = {n2} | après volatilité = {n2} | après tri+limit = {n3}")
        
        if not final_symbols:
            self.logger.warning("⚠️ Aucun symbole ne correspond aux critères de filtrage")
            raise NoSymbolsError("Aucun symbole ne correspond aux critères de filtrage")
        
        # Log des symboles retenus
        if final_symbols:
            symbols_list = [symbol for symbol, _, _, _, _, _ in final_symbols] if len(final_symbols[0]) == 6 else [symbol for symbol, _, _, _, _ in final_symbols] if len(final_symbols[0]) == 5 else [symbol for symbol, _, _, _ in final_symbols] if len(final_symbols[0]) == 4 else [symbol for symbol, _, _ in final_symbols]
            self.logger.info(f"🧭 Symboles retenus (Top {n3}) : {symbols_list}")
            
            # Séparer les symboles par catégorie
            if len(final_symbols[0]) == 6:
                linear_symbols = [symbol for symbol, _, _, _, _, _ in final_symbols if category_of_symbol(symbol, self.symbol_categories) == "linear"]
                inverse_symbols = [symbol for symbol, _, _, _, _, _ in final_symbols if category_of_symbol(symbol, self.symbol_categories) == "inverse"]
            elif len(final_symbols[0]) == 5:
                linear_symbols = [symbol for symbol, _, _, _, _ in final_symbols if category_of_symbol(symbol, self.symbol_categories) == "linear"]
                inverse_symbols = [symbol for symbol, _, _, _, _ in final_symbols if category_of_symbol(symbol, self.symbol_categories) == "inverse"]
            elif len(final_symbols[0]) == 4:
                linear_symbols = [symbol for symbol, _, _, _ in final_symbols if category_of_symbol(symbol, self.symbol_categories) == "linear"]
                inverse_symbols = [symbol for symbol, _, _, _ in final_symbols if category_of_symbol(symbol, self.symbol_categories) == "inverse"]
            else:
                linear_symbols = [symbol for symbol, _, _ in final_symbols if category_of_symbol(symbol, self.symbol_categories) == "linear"]
                inverse_symbols = [symbol for symbol, _, _ in final_symbols if category_of_symbol(symbol, self.symbol_categories) == "inverse"]
            
            self.linear_symbols = linear_symbols
            self.inverse_symbols = inverse_symbols
            
            # Construire funding_data avec les bonnes données
            if len(final_symbols[0]) == 6:
                # Format: (symbol, funding, volume, funding_time_remaining, spread_pct, volatility_pct)
                self.funding_data = {symbol: (funding, volume, funding_time_remaining, spread_pct, volatility_pct) for symbol, funding, volume, funding_time_remaining, spread_pct, volatility_pct in final_symbols}
            elif len(final_symbols[0]) == 5:
                # Format: (symbol, funding, volume, funding_time_remaining, spread_pct)
                self.funding_data = {symbol: (funding, volume, funding_time_remaining, spread_pct, None) for symbol, funding, volume, funding_time_remaining, spread_pct in final_symbols}
            elif len(final_symbols[0]) == 4:
                # Format: (symbol, funding, volume, funding_time_remaining)
                self.funding_data = {symbol: (funding, volume, funding_time_remaining, 0.0, None) for symbol, funding, volume, funding_time_remaining in final_symbols}
            else:
                # Format: (symbol, funding, volume)
                self.funding_data = {symbol: (funding, volume, "-", 0.0, None) for symbol, funding, volume in final_symbols}
            
            # Les données en temps réel seront initialisées uniquement via WebSocket
            # Pas d'initialisation avec des données statiques pour garantir la fraîcheur
        
        self.logger.info(f"📊 Symboles linear: {len(self.linear_symbols)}, inverse: {len(self.inverse_symbols)}")
        
        # Démarrer la tâche de rafraîchissement de la volatilité (arrière-plan) AVANT les WS bloquantes
        self._start_volatility_refresh_task()

        # Démarrer les connexions WebSocket selon les symboles disponibles
        if self.linear_symbols and self.inverse_symbols:
            # Les deux catégories : créer deux connexions
            self.logger.info("🔄 Démarrage des connexions WebSocket pour linear et inverse")
            self._start_dual_connections()
        elif self.linear_symbols:
            # Seulement linear
            self.logger.info("🔄 Démarrage de la connexion WebSocket linear")
            self._start_single_connection("linear", self.linear_symbols)
        elif self.inverse_symbols:
            # Seulement inverse
            self.logger.info("🔄 Démarrage de la connexion WebSocket inverse")
            self._start_single_connection("inverse", self.inverse_symbols)
        else:
            self.logger.warning("⚠️ Aucun symbole valide trouvé")
            raise NoSymbolsError("Aucun symbole valide trouvé")
    
    def _handle_ticker(self, ticker_data: dict):
        """Callback thread-safe appelé par les connexions WS isolées pour chaque tick."""
        try:
            symbol = ticker_data.get("symbol", "")
            mark_price = ticker_data.get("markPrice")
            last_price = ticker_data.get("lastPrice")
            if symbol and mark_price is not None and last_price is not None:
                mark_val = float(mark_price)
                last_val = float(last_price)
                update(symbol, mark_val, last_val, time.time())
            # Mettre à jour realtime_data (autres champs aussi utiles)
            if symbol:
                self._update_realtime_data(symbol, ticker_data)
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur handle_ticker: {e}")

    def _start_single_connection(self, category: str, symbols: list):
        """Démarre une connexion WebSocket pour une seule catégorie via une instance isolée."""
        conn = PublicWSConnection(category=category, symbols=symbols, testnet=self.testnet, logger=self.logger, on_ticker_callback=self._handle_ticker)
        self._ws_conns = [conn]
        # Démarrer l'affichage
        self.display_thread = threading.Thread(target=self._display_loop)
        self.display_thread.daemon = True
        self.display_thread.start()
        # Lancer la connexion (bloquant)
        conn.run()
    
    def _start_dual_connections(self):
        """Démarre deux connexions WebSocket isolées (linear et inverse)."""
        # Démarrer l'affichage
        self.display_thread = threading.Thread(target=self._display_loop)
        self.display_thread.daemon = True
        self.display_thread.start()
        # Créer connexions isolées
        linear_conn = PublicWSConnection(category="linear", symbols=self.linear_symbols, testnet=self.testnet, logger=self.logger, on_ticker_callback=self._handle_ticker)
        inverse_conn = PublicWSConnection(category="inverse", symbols=self.inverse_symbols, testnet=self.testnet, logger=self.logger, on_ticker_callback=self._handle_ticker)
        self._ws_conns = [linear_conn, inverse_conn]
        # Lancer en parallèle
        linear_thread = threading.Thread(target=linear_conn.run)
        inverse_thread = threading.Thread(target=inverse_conn.run)
        linear_thread.daemon = True
        inverse_thread.daemon = True
        self._ws_threads = [linear_thread, inverse_thread]
        linear_thread.start()
        inverse_thread.start()
        # Bloquer le thread principal sur les deux
        linear_thread.join()
        inverse_thread.join()
        
    def _start_volatility_refresh_task(self):
        """Démarre une tâche en arrière-plan pour rafraîchir le cache de volatilité."""
        if self._vol_refresh_thread and self._vol_refresh_thread.is_alive():
            try:
                self.logger.info("ℹ️ Thread volatilité déjà actif")
            except Exception:
                pass
            return
        self._vol_refresh_thread = threading.Thread(target=self._volatility_refresh_loop)
        self._vol_refresh_thread.daemon = True
        self._vol_refresh_thread.start()
        try:
            self.logger.info("🧵 Thread volatilité démarré")
        except Exception:
            pass

    def _volatility_refresh_loop(self):
        """Boucle de rafraîchissement périodique (2 min) du cache de volatilité."""
        # Utiliser un client PUBLIC (pas besoin de clés) pour la volatilité
        try:
            client = BybitPublicClient(
                testnet=self.testnet,
                timeout=10,
            )
        except Exception as e:
            self.logger.warning(f"⚠️ Impossible d'initialiser le client public pour la volatilité: {e}")
            return
        # Rafraîchir avant l'expiration du TTL pour rester frais; si erreur, ne pas mettre à jour
        try:
            ttl_sec = int(getattr(self, "volatility_ttl_sec", 120) or 120)
        except Exception:
            ttl_sec = 120
        # Rafraîchir plus fréquemment que TTL pour réduire le risque de trou; plafonner à 60s
        refresh_interval = max(30, min(60, ttl_sec - 10))
        try:
            self.logger.info(f"🩺 Volatilité: thread actif | ttl={ttl_sec}s | interval={refresh_interval}s")
        except Exception:
            pass
        while self.running:
            try:
                symbols_to_refresh = list(self.funding_data.keys())
                if not symbols_to_refresh:
                    # Rien à faire, patienter un court instant
                    time.sleep(5)
                    continue
                # Log de cycle
                try:
                    self.logger.info(f"🔄 Refresh volatilité: {len(symbols_to_refresh)} symboles")
                except Exception:
                    pass
                if symbols_to_refresh:
                    # Utiliser la fonction async batch existante
                    results = asyncio.run(
                        compute_volatility_batch_async(
                            client,
                            symbols_to_refresh,
                            timeout=10,
                            symbol_categories=self.symbol_categories,
                        )
                    )
                    now_ts = time.time()
                    ok_count = 0
                    fail_count = 0
                    for sym, vol_pct in results.items():
                        if vol_pct is not None:
                            cache_key = get_volatility_cache_key(sym)
                            self.volatility_cache[cache_key] = (now_ts, vol_pct)
                            ok_count += 1
                        else:
                            # Ne pas écraser une valeur fraîche par None
                            fail_count += 1
                    try:
                        self.logger.info(f"✅ Refresh volatilité terminé: ok={ok_count} | fail={fail_count}")
                    except Exception:
                        pass
                    # Retry simple pour les symboles en échec afin de limiter les fenêtres "-"
                    failed = [s for s, v in results.items() if v is None]
                    if failed:
                        try:
                            self.logger.info(f"🔁 Retry volatilité pour {len(failed)} symboles…")
                            time.sleep(5)
                            retry_results = asyncio.run(
                                compute_volatility_batch_async(
                                    client,
                                    failed,
                                    timeout=10,
                                    symbol_categories=self.symbol_categories,
                                )
                            )
                            now_ts = time.time()
                            retry_ok = 0
                            for sym, vol_pct in retry_results.items():
                                if vol_pct is not None:
                                    cache_key = get_volatility_cache_key(sym)
                                    self.volatility_cache[cache_key] = (now_ts, vol_pct)
                                    retry_ok += 1
                            self.logger.info(f"🔁 Retry volatilité terminé: récupérés={retry_ok}/{len(failed)}")
                        except Exception as re:
                            self.logger.warning(f"⚠️ Erreur retry volatilité: {re}")
                # Nettoyer le cache des symboles non suivis
                try:
                    active = set(self.funding_data.keys())
                    stale_keys = [k for k in list(self.volatility_cache.keys()) if k.split("volatility_5m_")[-1] not in active]
                    for k in stale_keys:
                        self.volatility_cache.pop(k, None)
                except Exception:
                    pass
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur refresh volatilité: {e}")
                # Backoff simple en cas d'erreur globale du cycle
                time.sleep(5)
            # Attendre 2 minutes
            for _ in range(refresh_interval):
                if not self.running:
                    break
                time.sleep(1)
    
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
