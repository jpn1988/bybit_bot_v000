#!/usr/bin/env python3
"""
Gestionnaire de données unifié pour le bot Bybit.

Cette classe consolide toutes les fonctionnalités de récupération et gestion de données :
- Récupération des données de marché (funding, spreads)
- Chargement et validation des données
- Stockage thread-safe des données
- Gestion des erreurs et métriques
- Interface pour la construction de watchlist (via WatchlistBuilder)

Cette version unifiée remplace :
- MarketDataFetcher (market_data_fetcher.py)
- BotDataLoader (bot_data_loader.py)
- DataManager (data_manager.py)
- Fonctionnalités de récupération de WatchlistManager

Note : La construction de la watchlist est déléguée à WatchlistManager
qui utilise ce gestionnaire pour récupérer les données nécessaires.
"""

import time
import httpx
import threading
from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor
from logging_setup import setup_logging
from volatility_tracker import VolatilityTracker
from http_utils import get_rate_limiter
from http_client_manager import get_http_client
from config_manager import MAX_WORKERS_THREADPOOL


class UnifiedDataManager:
    """
    Gestionnaire de données unifié pour le bot Bybit.
    
    Responsabilités principales :
    - Récupération des données de marché (funding, spreads)
    - Stockage thread-safe des données
    - Gestion des erreurs et métriques
    - Interface pour la construction de watchlist (via WatchlistManager)
    
    Cette classe fournit les données brutes nécessaires à WatchlistManager
    pour construire la watchlist selon les critères de filtrage.
    """

    def __init__(self, testnet: bool = True, logger=None):
        """
        Initialise le gestionnaire de données unifié.

        Args:
            testnet: Utiliser le testnet (True) ou le marché réel (False)
            logger: Logger pour les messages (optionnel)
        """
        self.testnet = testnet
        self.logger = logger or setup_logging()
        
        # Données de funding (format: {symbol: (funding, volume, funding_time, spread, volatility)})
        self.funding_data: Dict[str, Tuple[float, float, str, float, Optional[float]]] = {}
        
        # Données de funding originales avec next_funding_time
        self.original_funding_data: Dict[str, str] = {}
        
        # Données en temps réel via WebSocket
        # Format: {symbol: {funding_rate, volume24h, bid1, ask1, next_funding_time, ...}}
        self.realtime_data: Dict[str, Dict[str, Any]] = {}
        
        # Verrous pour la synchronisation thread-safe
        self._funding_lock = threading.Lock()
        self._realtime_lock = threading.Lock()
        
        # Catégories des symboles
        self.symbol_categories: Dict[str, str] = {}
        
        # Listes de symboles par catégorie
        self.linear_symbols: List[str] = []
        self.inverse_symbols: List[str] = []

    def fetch_funding_map(self, base_url: str, category: str, timeout: int = 10) -> Dict[str, Dict]:
        """
        Récupère les taux de funding pour une catégorie donnée.
        
        Args:
            base_url: URL de base de l'API Bybit
            category: Catégorie (linear ou inverse)
            timeout: Timeout pour les requêtes HTTP
            
        Returns:
            Dict[str, Dict]: Dictionnaire {symbol: {funding, volume, next_funding_time}}
            
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
                "limit": 1000  # Limite maximum supportée par l'API Bybit
            }
            if cursor:
                params["cursor"] = cursor
                
            try:
                page_index += 1
                # Respecter le rate limit avant chaque appel
                rate_limiter.acquire()
                client = get_http_client(timeout=timeout)
                response = client.get(url, params=params)
                
                # Vérifier le statut HTTP
                if response.status_code >= 400:
                    raise RuntimeError(
                        f"Erreur HTTP Bybit GET {url} | category={category} limit={params.get('limit')} "
                        f"cursor={params.get('cursor', '-')} timeout={timeout}s page={page_index} "
                        f"collected={len(funding_map)} | status={response.status_code} "
                        f"detail=\"{response.text[:200]}\""
                    )
                
                data = response.json()
                
                # Vérifier le retCode
                if data.get("retCode") != 0:
                    ret_code = data.get("retCode")
                    ret_msg = data.get("retMsg", "")
                    raise RuntimeError(
                        f"Erreur API Bybit GET {url} | category={category} limit={params.get('limit')} "
                        f"cursor={params.get('cursor', '-')} timeout={timeout}s page={page_index} "
                        f"collected={len(funding_map)} | retCode={ret_code} retMsg=\"{ret_msg}\""
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
                    f"Erreur réseau Bybit GET {url} | category={category} limit={params.get('limit')} "
                    f"cursor={params.get('cursor', '-')} timeout={timeout}s page={page_index} "
                    f"collected={len(funding_map)} | error={e}"
                )
            except Exception as e:
                if "Erreur" in str(e):
                    raise
                else:
                    raise RuntimeError(
                        f"Erreur inconnue Bybit GET {url} | category={category} limit={params.get('limit')} "
                        f"cursor={params.get('cursor', '-')} timeout={timeout}s page={page_index} "
                        f"collected={len(funding_map)} | error={e}"
                    )
        
        return funding_map

    def fetch_spread_data(self, base_url: str, symbols: List[str], timeout: int = 10, category: str = "linear") -> Dict[str, float]:
        """
        Récupère les spreads via /v5/market/tickers paginé, puis filtre localement.
        
        Args:
            base_url: URL de base de l'API Bybit
            symbols: Liste cible des symboles à retourner
            timeout: Timeout HTTP
            category: "linear" ou "inverse"
            
        Returns:
            Dict[str, float]: map {symbol: spread_pct}
        """
        # Récupération paginée des spreads
        found = self._fetch_spreads_paginated(base_url, symbols, timeout, category)
        
        # Fallback unitaire pour les symboles manquants
        self._fetch_missing_spreads(base_url, symbols, found, timeout, category)
        
        return found

    def _fetch_spreads_paginated(self, base_url: str, symbols: List[str], timeout: int, category: str) -> Dict[str, float]:
        """
        Récupère les spreads via pagination de l'API.
        
        Args:
            base_url: URL de base de l'API Bybit
            symbols: Liste des symboles cibles
            timeout: Timeout HTTP
            category: Catégorie des instruments
            
        Returns:
            Dictionnaire {symbol: spread_pct}
        """
        wanted = set(symbols)
        found: Dict[str, float] = {}
        url = f"{base_url}/v5/market/tickers"
        params = {"category": category, "limit": 1000}
        cursor = ""
        page_index = 0
        rate_limiter = get_rate_limiter()
        
        while True:
            page_index += 1
            
            # Préparer les paramètres de la requête
            self._prepare_pagination_params(params, cursor)
            
            try:
                # Effectuer la requête paginée
                result = self._make_paginated_request(url, params, timeout, page_index, category, rate_limiter)
                tickers = result.get("list", [])
                
                # Traiter les tickers de cette page
                self._process_tickers_for_spreads(tickers, wanted, found)
                
                # Vérifier si on doit continuer la pagination
                if not self._should_continue_pagination(found, wanted, tickers):
                    break
                    
                # Préparer la page suivante
                cursor = result.get("nextPageCursor")
                if not cursor:
                    break
                    
            except Exception as e:
                self._handle_pagination_error(e, page_index, category)
                break
        
        return found

    def _prepare_pagination_params(self, params: dict, cursor: str):
        """Prépare les paramètres de pagination."""
        if cursor:
            params["cursor"] = cursor
        else:
            params.pop("cursor", None)

    def _make_paginated_request(self, url: str, params: dict, timeout: int, page_index: int, category: str, rate_limiter) -> dict:
        """Effectue une requête paginée et retourne le résultat complet."""
        rate_limiter.acquire()
        client = get_http_client(timeout=timeout)
        resp = client.get(url, params=params)
        
        # Vérifier le statut HTTP
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Erreur HTTP Bybit GET {url} | category={category} page={page_index} "
                f"limit={params.get('limit')} cursor={params.get('cursor','-')} status={resp.status_code} "
                f"detail=\"{resp.text[:200]}\""
            )
        
        data = resp.json()
        if data.get("retCode") != 0:
            raise RuntimeError(
                f"Erreur API Bybit GET {url} | category={category} page={page_index} "
                f"retCode={data.get('retCode')} retMsg=\"{data.get('retMsg','')}\""
            )
        
        return data.get("result", {})

    def _process_tickers_for_spreads(self, tickers: list, wanted: set, found: Dict[str, float]):
        """Traite les tickers pour extraire les spreads."""
        for t in tickers:
            sym = t.get("symbol")
            if sym in wanted:
                spread_pct = self._calculate_spread_from_ticker(t)
                if spread_pct is not None:
                    found[sym] = spread_pct

    def _calculate_spread_from_ticker(self, ticker: dict) -> Optional[float]:
        """Calcule le spread en pourcentage à partir d'un ticker."""
        bid1 = ticker.get("bid1Price")
        ask1 = ticker.get("ask1Price")
        
        try:
            if bid1 is not None and ask1 is not None:
                b = float(bid1)
                a = float(ask1)
                if b > 0 and a > 0:
                    mid = (a + b) / 2
                    if mid > 0:
                        return (a - b) / mid
        except (ValueError, TypeError):
            # Erreur de conversion numérique - ignorer silencieusement
            pass
        
        return None

    def _should_continue_pagination(self, found: Dict[str, float], wanted: set, tickers: list) -> bool:
        """Détermine si la pagination doit continuer."""
        # Arrêt anticipé si on a tout trouvé
        if len(found) >= len(wanted):
            return False
        
        # Continuer si on a des tickers
        return len(tickers) > 0

    def _handle_pagination_error(self, error: Exception, page_index: int, category: str):
        """Gère les erreurs de pagination."""
        if isinstance(error, (httpx.RequestError, httpx.TimeoutException, httpx.HTTPStatusError)):
            self.logger.error(
                f"Erreur réseau spread paginé page={page_index} category={category}: {type(error).__name__}: {error}"
            )
        elif isinstance(error, (ValueError, TypeError, KeyError)):
            self.logger.warning(
                f"Erreur données spread paginé page={page_index} category={category}: {type(error).__name__}: {error}"
            )
        else:
            self.logger.error(
                f"Erreur inattendue spread paginé page={page_index} category={category}: {type(error).__name__}: {error}"
            )

    def _fetch_missing_spreads(self, base_url: str, symbols: List[str], found: Dict[str, float], timeout: int, category: str):
        """Récupère les spreads manquants via des requêtes unitaires."""
        missing = [s for s in symbols if s not in found]
        for s in missing:
            try:
                val = self._fetch_single_spread(base_url, s, timeout, category)
                if val is not None:
                    found[s] = val
            except (httpx.RequestError, ValueError, TypeError):
                # Erreurs réseau ou conversion - ignorer silencieusement pour le fallback
                pass

    def _fetch_single_spread(self, base_url: str, symbol: str, timeout: int, category: str) -> Optional[float]:
        """Récupère le spread pour un seul symbole."""
        try:
            url = f"{base_url}/v5/market/tickers"
            params = {"category": category, "symbol": symbol}
            
            rate_limiter = get_rate_limiter()
            rate_limiter.acquire()
            client = get_http_client(timeout=timeout)
            response = client.get(url, params=params)
            
            if response.status_code >= 400:
                raise RuntimeError(
                    f"Erreur HTTP Bybit GET {url} | category={category} symbol={symbol} "
                    f"timeout={timeout}s status={response.status_code} detail=\"{response.text[:200]}\""
                )
            
            data = response.json()
            
            if data.get("retCode") != 0:
                ret_code = data.get("retCode")
                ret_msg = data.get("retMsg", "")
                raise RuntimeError(
                    f"Erreur API Bybit GET {url} | category={category} symbol={symbol} "
                    f"timeout={timeout}s retCode={ret_code} retMsg=\"{ret_msg}\""
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

    def fetch_funding_data_parallel(self, base_url: str, categories: List[str], timeout: int = 10) -> Dict[str, Dict]:
        """
        Récupère les données de funding pour plusieurs catégories en parallèle.
        
        Args:
            base_url: URL de base de l'API Bybit
            categories: Liste des catégories à récupérer
            timeout: Timeout pour les requêtes HTTP
            
        Returns:
            Dict[str, Dict]: Dictionnaire combiné de toutes les catégories
        """
        if len(categories) == 1:
            return self.fetch_funding_map(base_url, categories[0], timeout)
        
        funding_map = {}
        
        # Paralléliser les requêtes
        with ThreadPoolExecutor(max_workers=MAX_WORKERS_THREADPOOL) as executor:
            # Lancer les requêtes en parallèle
            futures = {
                executor.submit(self.fetch_funding_map, base_url, category, timeout): category 
                for category in categories
            }
            
            # Récupérer les résultats
            for future in futures:
                category = futures[future]
                try:
                    category_data = future.result()
                    funding_map.update(category_data)
                except Exception as e:
                    self.logger.error(f"Erreur récupération funding pour {category}: {e}")
                    raise
        
        return funding_map

    def load_watchlist_data(
        self, 
        base_url: str, 
        perp_data: Dict, 
        watchlist_manager,
        volatility_tracker: VolatilityTracker
    ) -> bool:
        """
        Interface pour charger les données de la watchlist via WatchlistManager.
        
        Cette méthode délègue la construction de la watchlist à WatchlistManager
        et stocke les résultats dans ce gestionnaire pour utilisation ultérieure.
        
        Args:
            base_url: URL de base de l'API
            perp_data: Données des perpétuels
            watchlist_manager: Gestionnaire de watchlist (WatchlistManager)
            volatility_tracker: Tracker de volatilité
            
        Returns:
            bool: True si le chargement a réussi
        """
        try:
            self.logger.info("📊 Chargement des données de la watchlist...")
            
            # Construire la watchlist via le gestionnaire
            linear_symbols, inverse_symbols, funding_data = watchlist_manager.build_watchlist(
                base_url, perp_data, volatility_tracker
            )
            
            if not linear_symbols and not inverse_symbols:
                self.logger.warning("⚠️ Aucun symbole trouvé pour la watchlist")
                return False
            
            # Mettre à jour les listes de symboles
            self.set_symbol_lists(linear_symbols, inverse_symbols)
            
            # Mettre à jour les données de funding
            self._update_funding_data_in_manager(funding_data, self)
            
            # Mettre à jour les données originales
            self._update_original_funding_data(watchlist_manager, self)
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Erreur chargement watchlist: {e}")
            return False

    def _update_funding_data_in_manager(self, funding_data: Dict, data_manager):
        """Met à jour les données de funding dans le data manager."""
        for symbol, data in funding_data.items():
            if isinstance(data, (list, tuple)) and len(data) >= 4:
                funding, volume, funding_time, spread = data[:4]
                volatility = data[4] if len(data) > 4 else None
                data_manager.update_funding_data(symbol, funding, volume, funding_time, spread, volatility)
            elif isinstance(data, dict):
                # Si c'est un dictionnaire, extraire les valeurs
                funding = data.get('funding', 0.0)
                volume = data.get('volume', 0.0)
                funding_time = data.get('funding_time_remaining', '-')
                spread = data.get('spread_pct', 0.0)
                volatility = data.get('volatility_pct', None)
                data_manager.update_funding_data(symbol, funding, volume, funding_time, spread, volatility)

    def _update_original_funding_data(self, watchlist_manager, data_manager):
        """Met à jour les données originales de funding."""
        try:
            original_data = watchlist_manager.get_original_funding_data()
            for symbol, next_funding_time in original_data.items():
                data_manager.update_original_funding_data(symbol, next_funding_time)
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur mise à jour données originales: {e}")

    def validate_data_integrity(self) -> bool:
        """
        Valide l'intégrité des données chargées.
        
        Returns:
            bool: True si les données sont valides
        """
        try:
            # Vérifier que les listes de symboles ne sont pas vides
            linear_symbols = self.get_linear_symbols()
            inverse_symbols = self.get_inverse_symbols()
            
            if not linear_symbols and not inverse_symbols:
                self.logger.warning("⚠️ Aucun symbole dans les listes")
                return False
            
            # Vérifier que les données de funding sont présentes
            funding_data = self.get_all_funding_data()
            if not funding_data:
                self.logger.warning("⚠️ Aucune donnée de funding")
                return False
            
            self.logger.info(f"✅ Intégrité des données validée: {len(linear_symbols)} linear, {len(inverse_symbols)} inverse")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Erreur validation intégrité: {e}")
            return False

    def get_loading_summary(self) -> Dict[str, Any]:
        """
        Retourne un résumé du chargement des données.
        
        Returns:
            Dict[str, Any]: Résumé des données chargées
        """
        try:
            linear_symbols = self.get_linear_symbols()
            inverse_symbols = self.get_inverse_symbols()
            funding_data = self.get_all_funding_data()
            
            return {
                'linear_count': len(linear_symbols),
                'inverse_count': len(inverse_symbols),
                'total_symbols': len(linear_symbols) + len(inverse_symbols),
                'funding_data_count': len(funding_data),
                'linear_symbols': linear_symbols[:5],  # Premiers 5 pour debug
                'inverse_symbols': inverse_symbols[:5]  # Premiers 5 pour debug
            }
            
        except Exception as e:
            self.logger.error(f"❌ Erreur résumé chargement: {e}")
            return {
                'linear_count': 0,
                'inverse_count': 0,
                'total_symbols': 0,
                'funding_data_count': 0,
                'error': str(e)
            }
    
    # ===== MÉTHODES DE STOCKAGE DE DONNÉES (intégrées de DataManager) =====
    
    def set_symbol_categories(self, symbol_categories: Dict[str, str]):
        """
        Définit le mapping des catégories de symboles.
        
        Args:
            symbol_categories: Dictionnaire {symbol: category}
        """
        self.symbol_categories = symbol_categories
    
    def update_funding_data(self, symbol: str, funding: float, volume: float, 
                           funding_time: str, spread: float, volatility: Optional[float] = None):
        """
        Met à jour les données de funding pour un symbole.
        
        Args:
            symbol: Symbole à mettre à jour
            funding: Taux de funding
            volume: Volume 24h
            funding_time: Temps restant avant funding
            spread: Spread en pourcentage
            volatility: Volatilité (optionnel)
        """
        with self._funding_lock:
            self.funding_data[symbol] = (funding, volume, funding_time, spread, volatility)
    
    def get_funding_data(self, symbol: str) -> Optional[Tuple[float, float, str, float, Optional[float]]]:
        """
        Récupère les données de funding pour un symbole.
        
        Args:
            symbol: Symbole à récupérer
            
        Returns:
            Tuple des données de funding ou None si absent
        """
        with self._funding_lock:
            return self.funding_data.get(symbol)
    
    def get_all_funding_data(self) -> Dict[str, Tuple[float, float, str, float, Optional[float]]]:
        """
        Récupère toutes les données de funding.
        
        Returns:
            Dictionnaire des données de funding
        """
        with self._funding_lock:
            return self.funding_data.copy()
    
    def update_realtime_data(self, symbol: str, ticker_data: Dict[str, Any]):
        """
        Met à jour les données en temps réel pour un symbole.
        
        Args:
            symbol: Symbole à mettre à jour
            ticker_data: Données du ticker reçues via WebSocket
        """
        if not symbol:
            return
        
        try:
            # Construire un diff et fusionner avec l'état précédent
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
            important_keys = [
                'funding_rate', 'volume24h', 'bid1_price', 
                'ask1_price', 'next_funding_time'
            ]
            
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
    
    def get_realtime_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les données en temps réel pour un symbole.
        
        Args:
            symbol: Symbole à récupérer
            
        Returns:
            Dictionnaire des données temps réel ou None si absent
        """
        with self._realtime_lock:
            return self.realtime_data.get(symbol)
    
    def get_all_realtime_data(self) -> Dict[str, Dict[str, Any]]:
        """
        Récupère toutes les données en temps réel.
        
        Returns:
            Dictionnaire des données temps réel
        """
        with self._realtime_lock:
            return self.realtime_data.copy()
    
    def update_original_funding_data(self, symbol: str, next_funding_time: str):
        """
        Met à jour les données de funding originales.
        
        Args:
            symbol: Symbole à mettre à jour
            next_funding_time: Timestamp du prochain funding
        """
        with self._funding_lock:
            self.original_funding_data[symbol] = next_funding_time
    
    def get_original_funding_data(self, symbol: str) -> Optional[str]:
        """
        Récupère les données de funding originales pour un symbole.
        
        Args:
            symbol: Symbole à récupérer
            
        Returns:
            Timestamp du prochain funding ou None si absent
        """
        with self._funding_lock:
            return self.original_funding_data.get(symbol)
    
    def get_all_original_funding_data(self) -> Dict[str, str]:
        """
        Récupère toutes les données de funding originales.
        
        Returns:
            Dictionnaire des données de funding originales
        """
        with self._funding_lock:
            return self.original_funding_data.copy()
    
    def set_symbol_lists(self, linear_symbols: List[str], inverse_symbols: List[str]):
        """
        Définit les listes de symboles par catégorie.
        
        Args:
            linear_symbols: Liste des symboles linear
            inverse_symbols: Liste des symboles inverse
        """
        self.linear_symbols = linear_symbols.copy()
        self.inverse_symbols = inverse_symbols.copy()
    
    def get_linear_symbols(self) -> List[str]:
        """
        Récupère la liste des symboles linear.
        
        Returns:
            Liste des symboles linear
        """
        return self.linear_symbols.copy()
    
    def get_inverse_symbols(self) -> List[str]:
        """
        Récupère la liste des symboles inverse.
        
        Returns:
            Liste des symboles inverse
        """
        return self.inverse_symbols.copy()
    
    def get_all_symbols(self) -> List[str]:
        """
        Récupère tous les symboles (linear + inverse).
        
        Returns:
            Liste de tous les symboles
        """
        return self.linear_symbols + self.inverse_symbols
    
    def add_symbol_to_category(self, symbol: str, category: str):
        """
        Ajoute un symbole à une catégorie.
        
        Args:
            symbol: Symbole à ajouter
            category: Catégorie ("linear" ou "inverse")
        """
        if category == "linear" and symbol not in self.linear_symbols:
            self.linear_symbols.append(symbol)
        elif category == "inverse" and symbol not in self.inverse_symbols:
            self.inverse_symbols.append(symbol)
    
    def remove_symbol_from_category(self, symbol: str, category: str):
        """
        Retire un symbole d'une catégorie.
        
        Args:
            symbol: Symbole à retirer
            category: Catégorie ("linear" ou "inverse")
        """
        if category == "linear" and symbol in self.linear_symbols:
            self.linear_symbols.remove(symbol)
        elif category == "inverse" and symbol in self.inverse_symbols:
            self.inverse_symbols.remove(symbol)
    
    def clear_all_data(self):
        """
        Vide toutes les données stockées.
        """
        with self._funding_lock:
            self.funding_data.clear()
            self.original_funding_data.clear()
        
        with self._realtime_lock:
            self.realtime_data.clear()
        
        self.linear_symbols.clear()
        self.inverse_symbols.clear()
    
    def get_data_stats(self) -> Dict[str, int]:
        """
        Retourne les statistiques des données stockées.
        
        Returns:
            Dictionnaire avec les statistiques
        """
        with self._funding_lock:
            funding_count = len(self.funding_data)
            original_count = len(self.original_funding_data)
        
        with self._realtime_lock:
            realtime_count = len(self.realtime_data)
        
        return {
            "funding_data": funding_count,
            "original_funding_data": original_count,
            "realtime_data": realtime_count,
            "linear_symbols": len(self.linear_symbols),
            "inverse_symbols": len(self.inverse_symbols)
        }
