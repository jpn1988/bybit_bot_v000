#!/usr/bin/env python3
"""
🚀 Orchestrateur du bot (filters + WebSocket prix)

Script pour filtrer les contrats perpétuels par funding ET suivre leurs prix en temps réel.

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
try:
    from .config import get_settings
except ImportError:
    from config import get_settings
from logging_setup import setup_logging
from bybit_client import BybitClient
from instruments import get_perp_symbols
from price_store import update, get_snapshot, get_age_seconds
from volatility import compute_5m_range_pct, get_volatility_cache_key, is_cache_valid


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
        "limite": 10
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
    
    # Appliquer les variables d'environnement si présentes
    if env_spread_max is not None:
        default_config["spread_max"] = env_spread_max
    if env_volume_min_millions is not None:
        default_config["volume_min_millions"] = env_volume_min_millions
    if env_volatility_min is not None:
        default_config["volatility_min"] = env_volatility_min
    if env_volatility_max is not None:
        default_config["volatility_max"] = env_volatility_max
    
    return default_config


def fetch_funding_map(base_url: str, category: str, timeout: int) -> dict[str, float]:
    """
    Récupère les taux de funding pour une catégorie donnée.
    
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
    
    while True:
        # Construire l'URL avec pagination
        url = f"{base_url}/v5/market/tickers"
        params = {
            "category": category,
            "limit": 1000
        }
        if cursor:
            params["cursor"] = cursor
            
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.get(url, params=params)
                
                # Vérifier le statut HTTP
                if response.status_code >= 400:
                    raise RuntimeError(f"Erreur HTTP Bybit: status={response.status_code} detail=\"{response.text[:100]}\"")
                
                data = response.json()
                
                # Vérifier le retCode
                if data.get("retCode") != 0:
                    ret_code = data.get("retCode")
                    ret_msg = data.get("retMsg", "")
                    raise RuntimeError(f"Erreur API Bybit: retCode={ret_code} retMsg=\"{ret_msg}\"")
                
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
            raise RuntimeError(f"Erreur réseau/HTTP Bybit: {e}")
        except Exception as e:
            if "Erreur" in str(e):
                raise
            else:
                raise RuntimeError(f"Erreur réseau/HTTP Bybit: {e}")
    
    return funding_map


def calculate_funding_time_remaining(next_funding_time: str | None) -> str:
    """
    Calcule le temps restant avant le prochain funding.
    
    Args:
        next_funding_time (str | None): Timestamp du prochain funding (format ISO ou timestamp)
        
    Returns:
        str: Temps restant formaté (ex: "2h 15m" ou "45m" ou "-")
    """
    if not next_funding_time:
        return "-"
    
    try:
        import datetime
        
        # Convertir le timestamp en datetime
        if isinstance(next_funding_time, str):
            # Si c'est un timestamp en millisecondes
            if next_funding_time.isdigit():
                funding_time = datetime.datetime.fromtimestamp(int(next_funding_time) / 1000)
            else:
                # Si c'est un format ISO
                funding_time = datetime.datetime.fromisoformat(next_funding_time.replace('Z', '+00:00'))
        else:
            # Si c'est déjà un timestamp numérique
            funding_time = datetime.datetime.fromtimestamp(next_funding_time / 1000)
        
        # Calculer la différence avec maintenant
        now = datetime.datetime.now(datetime.timezone.utc)
        if funding_time.tzinfo is None:
            funding_time = funding_time.replace(tzinfo=datetime.timezone.utc)
        
        time_diff = funding_time - now
        
        # Si le funding est déjà passé, retourner "-"
        if time_diff.total_seconds() <= 0:
            return "-"
        
        # Convertir en heures et minutes
        total_seconds = int(time_diff.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        
        # Formater le résultat
        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
            
    except (ValueError, TypeError, OSError):
        return "-"


def fetch_spread_data(base_url: str, symbols: list[str], timeout: int, category: str = "linear") -> dict[str, float]:
    """
    Récupère les données de spread (bid1/ask1) pour une liste de symboles.
    Gère les symboles invalides en les récupérant un par un.
    
    Args:
        base_url (str): URL de base de l'API Bybit
        symbols (list[str]): Liste des symboles à analyser
        timeout (int): Timeout pour les requêtes HTTP
        category (str): Catégorie des symboles ("linear" ou "inverse")
        
    Returns:
        dict[str, float]: Dictionnaire {symbol: spread_pct}
        
    Raises:
        RuntimeError: En cas d'erreur HTTP ou API
    """
    spread_data = {}
    
    # Essayer d'abord par batch
    try:
        # Grouper les symboles par paquets pour éviter les requêtes trop longues
        batch_size = 50  # Limite raisonnable pour l'URL
        symbol_batches = [symbols[i:i + batch_size] for i in range(0, len(symbols), batch_size)]
        
        for batch_idx, symbol_batch in enumerate(symbol_batches):
            try:
                # Construire l'URL avec les symboles du batch
                url = f"{base_url}/v5/market/tickers"
                params = {
                    "category": category,
                    "symbol": ",".join(symbol_batch)
                }
                
                with httpx.Client(timeout=timeout) as client:
                    response = client.get(url, params=params)
                    
                    # Vérifier le statut HTTP
                    if response.status_code >= 400:
                        raise RuntimeError(f"Erreur HTTP Bybit: status={response.status_code} detail=\"{response.text[:100]}\"")
                    
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
                                        spread_data[symbol] = single_spread
                                except Exception:
                                    # Ignorer les symboles qui échouent
                                    pass
                            continue
                        else:
                            raise RuntimeError(f"Erreur API Bybit: retCode={ret_code} retMsg=\"{ret_msg}\"")
                    
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
                                    spread_data[symbol] = spread_pct
                            except (ValueError, TypeError, ZeroDivisionError):
                                # Ignorer si les données ne sont pas convertibles ou si division par zéro
                                pass
                
                # Petit délai entre les batches pour éviter le rate limit
                if batch_idx < len(symbol_batches) - 1:
                    time.sleep(0.1)  # 100ms
                    
            except httpx.RequestError as e:
                raise RuntimeError(f"Erreur réseau/HTTP Bybit: {e}")
            except Exception as e:
                if "Erreur" in str(e):
                    raise
                else:
                    raise RuntimeError(f"Erreur réseau/HTTP Bybit: {e}")
    
    except Exception as e:
        # Si le batch échoue complètement, essayer un par un
        for symbol in symbols:
            try:
                single_spread = _fetch_single_spread(base_url, symbol, timeout, category)
                if single_spread:
                    spread_data[symbol] = single_spread
            except Exception:
                # Ignorer les symboles qui échouent
                pass
    
    return spread_data


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
        
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url, params=params)
            
            if response.status_code >= 400:
                return None
            
            data = response.json()
            
            if data.get("retCode") != 0:
                return None
            
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


def filter_by_volatility(symbols_data: list[tuple[str, float, float, str, float]], bybit_client, volatility_min: float, volatility_max: float, logger, volatility_cache: dict) -> list[tuple[str, float, float, str, float]]:
    """
    Filtre les symboles par volatilité 5 minutes (pour tous les symboles).
    
    Args:
        symbols_data (list[tuple[str, float, float, str, float]]): Liste des (symbol, funding, volume, funding_time_remaining, spread_pct)
        bybit_client: Instance du client Bybit
        volatility_min (float): Volatilité minimum autorisée (0.002 = 0.2%)
        volatility_max (float): Volatilité maximum autorisée (0.007 = 0.7%)
        logger: Logger pour les messages
        volatility_cache (dict): Cache de volatilité {symbol: (timestamp, volatility)}
        
    Returns:
        list[tuple[str, float, float, str, float]]: Liste filtrée par volatilité
    """
    if volatility_min is None and volatility_max is None:
        return symbols_data
    
    filtered_symbols = []
    rejected_count = 0
    
    for symbol, funding, volume, funding_time_remaining, spread_pct in symbols_data:
        # Calculer la volatilité pour tous les symboles
        cache_key = get_volatility_cache_key(symbol)
        cached_data = volatility_cache.get(cache_key)
        
        if cached_data and is_cache_valid(cached_data[0], ttl_seconds=60):
            # Utiliser la valeur en cache
            vol_pct = cached_data[1]
        else:
            # Calculer la volatilité
            vol_pct = compute_5m_range_pct(bybit_client, symbol)
            
            if vol_pct is not None:
                # Mettre en cache
                volatility_cache[cache_key] = (time.time(), vol_pct)
            else:
                # Volatilité indisponible
                vol_pct = None
        
        # Appliquer le filtre de volatilité pour tous les symboles
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
    logger.info(f"✅ Filtre volatilité: gardés={kept_count} | rejetés={rejected_count} (seuils: {threshold_str})")
    
    return filtered_symbols


def filter_by_funding(perp_data: dict, funding_map: dict, funding_min: float | None, funding_max: float | None, volume_min: float | None, volume_min_millions: float | None, limite: int | None) -> list[tuple[str, float, float, str]]:
    """
    Filtre les symboles par funding et volume, puis trie par |funding| décroissant.
    
    Args:
        perp_data (dict): Données des perpétuels (linear, inverse, total)
        funding_map (dict): Dictionnaire des funding rates, volumes et temps de funding
        funding_min (float | None): Funding minimum
        funding_max (float | None): Funding maximum
        volume_min (float | None): Volume minimum (ancien format)
        volume_min_millions (float | None): Volume minimum en millions (nouveau format)
        limite (int | None): Limite du nombre d'éléments
        
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
    
    # Filtrer par funding et volume
    filtered_symbols = []
    for symbol in all_symbols:
        if symbol in funding_map:
            data = funding_map[symbol]
            funding = data["funding"]
            volume = data["volume"]
            next_funding_time = data.get("next_funding_time")
            
            # Appliquer les bornes
            if funding_min is not None and funding < funding_min:
                continue
            if funding_max is not None and funding > funding_max:
                continue
            if effective_volume_min is not None and volume < effective_volume_min:
                continue
            
            # Calculer le temps restant avant le prochain funding
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
        self.volatility_cache = {}  # Cache pour la volatilité {symbol: (timestamp, volatility)}
        
        # Configuration
        settings = get_settings()
        self.testnet = settings['testnet']
        
        # Configuration du signal handler pour Ctrl+C
        signal.signal(signal.SIGINT, self._signal_handler)
        
        self.logger.info("🚀 Orchestrateur du bot (filters + WebSocket prix)")
        self.logger.info("📂 Configuration chargée")
    
    def _signal_handler(self, signum, frame):
        """Gestionnaire de signal pour Ctrl+C."""
        self.logger.info("🧹 Arrêt demandé, fermeture de la WebSocket…")
        self.running = False
        if self.ws:
            self.ws.close()
        sys.exit(0)
    
    def _print_price_table(self):
        """Affiche le tableau des prix aligné avec funding, volume en millions, spread et volatilité."""
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
        funding_time_w = 12  # Largeur pour le temps de funding
        
        # En-tête
        header = f"{'Symbole':<{symbol_w}} | {'Funding %':>{funding_w}} | {'Volume (M)':>{volume_w}} | {'Spread %':>{spread_w}} | {'Volatilité %':>{volatility_w}} | {'Funding T':>{funding_time_w}}"
        sep = f"{'-'*symbol_w}-+-{'-'*funding_w}-+-{'-'*volume_w}-+-{'-'*spread_w}-+-{'-'*volatility_w}-+-{'-'*funding_time_w}"
        
        print("\n" + header)
        print(sep)
        
        # Données
        for symbol, data in self.funding_data.items():
            # data peut être (funding, volume) ou (funding, volume, spread_pct) ou (funding, volume, funding_time_remaining, spread_pct) ou (funding, volume, funding_time_remaining, spread_pct, volatility_pct)
            if len(data) == 5:
                funding, volume, funding_time_remaining, spread_pct, volatility_pct = data
            elif len(data) == 4:
                funding, volume, funding_time_remaining, spread_pct = data
                volatility_pct = None  # Pas de volatilité calculée
            elif len(data) == 3:
                funding, volume, spread_pct = data
                funding_time_remaining = "-"
                volatility_pct = None  # Pas de volatilité calculée
            else:
                funding, volume = data
                spread_pct = 0.0  # Valeur par défaut si pas de spread
                funding_time_remaining = "-"
                volatility_pct = None  # Pas de volatilité calculée
            
            # Essayer de récupérer la volatilité depuis le cache si elle n'est pas déjà présente
            if volatility_pct is None:
                cache_key = get_volatility_cache_key(symbol)
                cached_data = self.volatility_cache.get(cache_key)
                if cached_data and is_cache_valid(cached_data[0], ttl_seconds=60):
                    volatility_pct = cached_data[1]
            
            funding_pct = funding * 100.0
            volume_millions = volume / 1_000_000 if volume > 0 else 0.0
            volume_str = f"{volume_millions:,.1f}" if volume > 0 else "-"
            spread_pct_display = spread_pct * 100.0
            spread_str = f"{spread_pct_display:+.3f}%" if spread_pct > 0 else "-"
            
            # Formatage de la volatilité
            if volatility_pct is not None:
                volatility_pct_display = volatility_pct * 100.0
                volatility_str = f"{volatility_pct_display:+.3f}%"
            else:
                volatility_str = "-"
            
            line = f"{symbol:<{symbol_w}} | {funding_pct:+{funding_w-1}.4f}% | {volume_str:>{volume_w}} | {spread_str:>{spread_w}} | {volatility_str:>{volatility_w}} | {funding_time_remaining:>{funding_time_w}}"
            print(line)
        
        print()  # Ligne vide après le tableau
    
    def _display_loop(self):
        """Boucle d'affichage toutes les 5 secondes."""
        while self.running:
            self._print_price_table()
            
            # Attendre 5 secondes
            for _ in range(50):  # 50 * 0.1s = 5s
                if not self.running:
                    break
                time.sleep(0.1)
    
    def ws_on_open(self, ws, symbols):
        """Callback ouverture WebSocket."""
        category = "linear" if any("USDT" in s for s in symbols) else "inverse"
        self.logger.info(f"🌐 WS ouverte ({category})")
        
        # S'abonner aux tickers
        subscribe_message = {
            "op": "subscribe",
            "args": [f"tickers.{symbol}" for symbol in symbols]
        }
        
        ws.send(json.dumps(subscribe_message))
        self.logger.info(f"🧭 Souscription tickers → {len(symbols)} symboles")
        self.logger.info("🟢 Orchestrateur prêt (WS connectée, flux en cours)")
    
    def ws_on_message(self, ws, message):
        """Callback message WebSocket."""
        try:
            data = json.loads(message)
            
            # Gestion des messages WebSocket
            if data.get("op") == "subscribe":
                success = data.get("success", False)
                if success:
                    self.logger.info(f"✅ Souscription confirmée: {data.get('ret_msg', '')}")
                else:
                    self.logger.warning(f"⚠️ Échec souscription: {data.get('ret_msg', '')}")
            elif data.get("topic", "").startswith("tickers."):
                ticker_data = data.get("data", {})
                if ticker_data:
                    symbol = ticker_data.get("symbol", "")
                    mark_price = ticker_data.get("markPrice")
                    last_price = ticker_data.get("lastPrice")
                    
                    if symbol and mark_price is not None and last_price is not None:
                        try:
                            mark_price = float(mark_price)
                            last_price = float(last_price)
                            timestamp = time.time()
                            
                            update(symbol, mark_price, last_price, timestamp)
                        except (ValueError, TypeError) as e:
                            self.logger.warning(f"⚠️ Erreur parsing prix pour {symbol}: {e}")
            
        except json.JSONDecodeError as e:
            self.logger.warning(f"⚠️ Erreur JSON: {e}")
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur parsing: {e}")
    
    def ws_on_error(self, ws, error):
        """Callback erreur WebSocket."""
        if self.running:
            self.logger.warning(f"⚠️ WS erreur : {error}")
    
    def ws_on_close(self, ws, close_status_code, close_msg):
        """Callback fermeture WebSocket."""
        if self.running:
            self.logger.info(f"🔌 WS fermée (code={close_status_code}, reason={close_msg})")
    
    def start(self):
        """Démarre le suivi des prix avec filtrage par funding."""
        # Charger la configuration
        config = load_config()
        
        # Vérifier si le fichier de config existe
        config_path = "src/parameters.yaml"
        if not os.path.exists(config_path):
            self.logger.info("ℹ️ Aucun fichier de paramètres trouvé (src/watchlist_config.fr.yaml) → utilisation des valeurs par défaut.")
        
        # Créer un client Bybit pour récupérer l'URL publique
        client = BybitClient(
            testnet=self.testnet,
            timeout=10,
            api_key="dummy_key",
            api_secret="dummy_secret"
        )
        
        base_url = client.public_base_url()
        
        # Récupérer l'univers perp
        perp_data = get_perp_symbols(base_url, timeout=10)
        self.logger.info(f"🗺️ Univers perp récupéré : linear={len(perp_data['linear'])} | inverse={len(perp_data['inverse'])} | total={perp_data['total']}")
        
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
        
        # Afficher les filtres
        min_display = f"{funding_min:.6f}" if funding_min is not None else "none"
        max_display = f"{funding_max:.6f}" if funding_max is not None else "none"
        volume_display = f"{volume_min_millions:.1f}" if volume_min_millions is not None else "none"
        spread_display = f"{spread_max:.4f}" if spread_max is not None else "none"
        volatility_min_display = f"{volatility_min:.3f}" if volatility_min is not None else "none"
        volatility_max_display = f"{volatility_max:.3f}" if volatility_max is not None else "none"
        limite_display = str(limite) if limite is not None else "none"
        
        self.logger.info(f"🎛️ Filtres | catégorie={categorie} | funding_min={min_display} | funding_max={max_display} | volume_min_millions={volume_display} | spread_max={spread_display} | volatility_min={volatility_min_display} | volatility_max={volatility_max_display} | limite={limite_display}")
        
        # Récupérer les funding rates selon la catégorie
        funding_map = {}
        if categorie == "linear":
            self.logger.info("📡 Récupération des funding rates pour linear…")
            funding_map = fetch_funding_map(base_url, "linear", 10)
        elif categorie == "inverse":
            self.logger.info("📡 Récupération des funding rates pour inverse…")
            funding_map = fetch_funding_map(base_url, "inverse", 10)
        else:  # "both"
            self.logger.info("📡 Récupération des funding rates pour linear+inverse…")
            linear_funding = fetch_funding_map(base_url, "linear", 10)
            inverse_funding = fetch_funding_map(base_url, "inverse", 10)
            funding_map = {**linear_funding, **inverse_funding}  # Merger (priorité au dernier)
        
        if not funding_map:
            self.logger.warning("⚠️ Aucun funding disponible pour la catégorie sélectionnée")
            sys.exit(1)
        
        # Compter les symboles avant filtrage
        all_symbols = list(set(perp_data["linear"] + perp_data["inverse"]))
        n0 = len([s for s in all_symbols if s in funding_map])
        
        # Filtrer par funding et volume
        filtered_symbols = filter_by_funding(perp_data, funding_map, funding_min, funding_max, volume_min, volume_min_millions, limite)
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
                linear_symbols_for_spread = [s for s in symbols_to_check if "USDT" in s]
                inverse_symbols_for_spread = [s for s in symbols_to_check if "USD" in s and "USDT" not in s]
                
                # Récupérer les spreads pour chaque catégorie
                if linear_symbols_for_spread:
                    linear_spread_data = fetch_spread_data(base_url, linear_symbols_for_spread, 10, "linear")
                    spread_data.update(linear_spread_data)
                
                if inverse_symbols_for_spread:
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
        
        # Appliquer le filtre de volatilité si nécessaire
        if (volatility_min is not None or volatility_max is not None) and final_symbols:
            try:
                self.logger.info("🔎 Évaluation de la volatilité 5m pour tous les symboles…")
                final_symbols = filter_by_volatility(final_symbols, client, volatility_min, volatility_max, self.logger, self.volatility_cache)
                n2 = len(final_symbols)
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur lors du calcul de la volatilité : {e}")
                # Continuer sans le filtre de volatilité
        
        # Appliquer la limite finale
        if limite is not None and len(final_symbols) > limite:
            final_symbols = final_symbols[:limite]
        n3 = len(final_symbols)
        
        # Log des comptes
        if volatility_min is not None or volatility_max is not None:
            self.logger.info(f"🧮 Comptes | avant filtres = {n0} | après funding/volume = {n1} | après spread = {n2} | après volatilité = {n2} | après tri+limit = {n3}")
        else:
            self.logger.info(f"🧮 Comptes | avant filtres = {n0} | après funding/volume = {n1} | après spread = {n2} | après tri+limit = {n3}")
        
        if not final_symbols:
            self.logger.warning("⚠️ Aucun symbole ne correspond aux critères de filtrage")
            sys.exit(1)
        
        # Log des symboles retenus
        if final_symbols:
            symbols_list = [symbol for symbol, _, _, _, _, _ in final_symbols] if len(final_symbols[0]) == 6 else [symbol for symbol, _, _, _, _ in final_symbols] if len(final_symbols[0]) == 5 else [symbol for symbol, _, _, _ in final_symbols] if len(final_symbols[0]) == 4 else [symbol for symbol, _, _ in final_symbols]
            self.logger.info(f"🧭 Symboles retenus (Top {n3}) : {symbols_list}")
            
            # Séparer les symboles par catégorie
            if len(final_symbols[0]) == 6:
                linear_symbols = [symbol for symbol, _, _, _, _, _ in final_symbols if "USDT" in symbol]
                inverse_symbols = [symbol for symbol, _, _, _, _, _ in final_symbols if "USD" in symbol and "USDT" not in symbol]
            elif len(final_symbols[0]) == 5:
                linear_symbols = [symbol for symbol, _, _, _, _ in final_symbols if "USDT" in symbol]
                inverse_symbols = [symbol for symbol, _, _, _, _ in final_symbols if "USD" in symbol and "USDT" not in symbol]
            elif len(final_symbols[0]) == 4:
                linear_symbols = [symbol for symbol, _, _, _ in final_symbols if "USDT" in symbol]
                inverse_symbols = [symbol for symbol, _, _, _ in final_symbols if "USD" in symbol and "USDT" not in symbol]
            else:
                linear_symbols = [symbol for symbol, _, _ in final_symbols if "USDT" in symbol]
                inverse_symbols = [symbol for symbol, _, _ in final_symbols if "USD" in symbol and "USDT" not in symbol]
            
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
        
        self.logger.info(f"📊 Symboles linear: {len(self.linear_symbols)}, inverse: {len(self.inverse_symbols)}")
        
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
            sys.exit(1)
    
    def _start_single_connection(self, category: str, symbols: list):
        """Démarre une connexion WebSocket pour une seule catégorie."""
        # URL WebSocket selon la catégorie et l'environnement
        if category == "linear":
            url = "wss://stream-testnet.bybit.com/v5/public/linear" if self.testnet else "wss://stream.bybit.com/v5/public/linear"
        else:
            url = "wss://stream-testnet.bybit.com/v5/public/inverse" if self.testnet else "wss://stream.bybit.com/v5/public/inverse"
        
        # Créer la WebSocket
        self.ws = websocket.WebSocketApp(
            url,
            on_open=lambda ws: self.ws_on_open(ws, symbols),
            on_message=self.ws_on_message,
            on_error=self.ws_on_error,
            on_close=self.ws_on_close
        )
        
        # Démarrer le thread d'affichage
        self.display_thread = threading.Thread(target=self._display_loop)
        self.display_thread.daemon = True
        self.display_thread.start()
        
        # Démarrer la WebSocket (bloquant)
        self.ws.run_forever(ping_interval=20, ping_timeout=10)
    
    def _start_dual_connections(self):
        """Démarre deux connexions WebSocket (linear et inverse)."""
        # Démarrer le thread d'affichage
        self.display_thread = threading.Thread(target=self._display_loop)
        self.display_thread.daemon = True
        self.display_thread.start()
        
        # Démarrer les deux connexions en parallèle
        linear_thread = threading.Thread(target=self._run_linear_ws)
        inverse_thread = threading.Thread(target=self._run_inverse_ws)
        
        linear_thread.daemon = True
        inverse_thread.daemon = True
        
        linear_thread.start()
        inverse_thread.start()
        
        # Attendre que les threads se terminent
        linear_thread.join()
        inverse_thread.join()
    
    def _run_linear_ws(self):
        """Exécute la WebSocket linear."""
        url = "wss://stream-testnet.bybit.com/v5/public/linear" if self.testnet else "wss://stream.bybit.com/v5/public/linear"
        
        ws = websocket.WebSocketApp(
            url,
            on_open=lambda ws: self.ws_on_open(ws, self.linear_symbols),
            on_message=self.ws_on_message,
            on_error=self.ws_on_error,
            on_close=self.ws_on_close
        )
        
        ws.run_forever(ping_interval=20, ping_timeout=10)
    
    def _run_inverse_ws(self):
        """Exécute la WebSocket inverse."""
        url = "wss://stream-testnet.bybit.com/v5/public/inverse" if self.testnet else "wss://stream.bybit.com/v5/public/inverse"
        
        ws = websocket.WebSocketApp(
            url,
            on_open=lambda ws: self.ws_on_open(ws, self.inverse_symbols),
            on_message=self.ws_on_message,
            on_error=self.ws_on_error,
            on_close=self.ws_on_close
        )
        
        ws.run_forever(ping_interval=20, ping_timeout=10)


def main():
    """Fonction principale."""
    tracker = PriceTracker()
    try:
        tracker.start()
    except Exception as e:
        tracker.logger.error(f"❌ Erreur : {e}")
        tracker.running = False
        sys.exit(1)


if __name__ == "__main__":
    main()
