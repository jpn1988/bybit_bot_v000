#!/usr/bin/env python3
"""
Récupérateur de données de marché pour le bot Bybit.

Cette classe gère uniquement :
- La récupération des données de funding via l'API Bybit
- La récupération des données de spread via l'API Bybit
- La gestion des requêtes paginées et du rate limiting
"""

import httpx
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor
from logging_setup import setup_logging
from http_utils import get_rate_limiter
from http_client_manager import get_http_client
from config_manager import MAX_WORKERS_THREADPOOL


class MarketDataFetcher:
    """
    Récupérateur de données de marché pour le bot Bybit.

    Responsabilités :
    - Récupération des taux de funding via l'API Bybit
    - Récupération des spreads via l'API Bybit
    - Gestion de la pagination et du rate limiting
    - Gestion des requêtes parallèles
    """

    def __init__(self, testnet: bool = True, logger=None):
        """
        Initialise le récupérateur de données de marché.

        Args:
            testnet (bool): Utiliser le testnet (True) ou le marché réel
            (False)
            logger: Logger pour les messages (optionnel)
        """
        self.testnet = testnet
        self.logger = logger or setup_logging()

    def fetch_funding_map(
        self, base_url: str, category: str, timeout: int = 10
    ) -> Dict[str, Dict]:
        """
        Récupère les taux de funding pour une catégorie donnée.

        Args:
            base_url: URL de base de l'API Bybit
            category: Catégorie (linear ou inverse)
            timeout: Timeout pour les requêtes HTTP

        Returns:
            Dict[str, Dict]: Dictionnaire {symbol: {funding, volume,
            next_funding_time}}

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
                "limit": 1000,  # Limite maximum supportée par l'API Bybit
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
                        f"Erreur HTTP Bybit GET {url} | category={category} "
                        f"limit={params.get('limit')} "
                        f"cursor={params.get('cursor', '-')} "
                        f"timeout={timeout}s page={page_index} "
                        f"collected={len(funding_map)} | "
                        f"status={response.status_code} "
                        f'detail="{response.text[:200]}"'
                    )

                data = response.json()

                # Vérifier le retCode
                if data.get("retCode") != 0:
                    ret_code = data.get("retCode")
                    ret_msg = data.get("retMsg", "")
                    raise RuntimeError(
                        f"Erreur API Bybit GET {url} | category={category} "
                        f"limit={params.get('limit')} "
                        f"cursor={params.get('cursor', '-')} "
                        f"timeout={timeout}s page={page_index} "
                        f"collected={len(funding_map)} | "
                        f'retCode={ret_code} retMsg="{ret_msg}"'
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
                                "volume": float(volume_24h)
                                if volume_24h is not None
                                else 0.0,
                                "next_funding_time": next_funding_time,
                            }
                        except (ValueError, TypeError):
                            # Ignorer si les données ne sont pas convertibles
                            # en float
                            pass

                # Vérifier s'il y a une page suivante
                next_page_cursor = result.get("nextPageCursor")
                if not next_page_cursor:
                    break
                cursor = next_page_cursor

            except httpx.RequestError as e:
                raise RuntimeError(
                    f"Erreur réseau Bybit GET {url} | category={category} "
                    f"limit={params.get('limit')} "
                    f"cursor={params.get('cursor', '-')} timeout={timeout}s "
                    f"page={page_index} collected={len(funding_map)} | error={e}"
                )
            except Exception as e:
                if "Erreur" in str(e):
                    raise
                else:
                    raise RuntimeError(
                        f"Erreur inconnue Bybit GET {url} | category={category} "
                        f"limit={params.get('limit')} "
                        f"cursor={params.get('cursor', '-')} timeout={timeout}s "
                        f"page={page_index} collected={len(funding_map)} | error={e}"
                    )

        return funding_map

    def fetch_spread_data(
        self,
        base_url: str,
        symbols: List[str],
        timeout: int = 10,
        category: str = "linear",
    ) -> Dict[str, float]:
        """
        Récupère les spreads via /v5/market/tickers paginé, 
        puis filtre localement.

        Args:
            base_url: URL de base de l'API Bybit
            symbols: Liste cible des symboles à retourner
            timeout: Timeout HTTP
            category: "linear" ou "inverse"

        Returns:
            Dict[str, float]: map {symbol: spread_pct}
        """
        # Récupération paginée des spreads
        found = self._fetch_spreads_paginated(
            base_url, symbols, timeout, category
        )

        # Fallback unitaire pour les symboles manquants
        self._fetch_missing_spreads(
            base_url, symbols, found, timeout, category
        )

        return found

    def _fetch_spreads_paginated(
        self, base_url: str, symbols: List[str], timeout: int, category: str
    ) -> Dict[str, float]:
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
                result = self._make_paginated_request(
                    url, params, timeout, page_index, category, rate_limiter
                )
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
        """
        Prépare les paramètres de pagination.

        Args:
            params: Dictionnaire des paramètres à modifier
            cursor: Curseur de pagination
        """
        if cursor:
            params["cursor"] = cursor
        else:
            params.pop("cursor", None)

    def _make_paginated_request(
        self,
        url: str,
        params: dict,
        timeout: int,
        page_index: int,
        category: str,
        rate_limiter,
    ) -> dict:
        """
        Effectue une requête paginée et retourne le résultat complet.

        Args:
            url: URL de l'API
            params: Paramètres de la requête
            timeout: Timeout HTTP
            page_index: Index de la page
            category: Catégorie des instruments
            rate_limiter: Limiteur de taux

        Returns:
            Dictionnaire result de l'API

        Raises:
            RuntimeError: En cas d'erreur HTTP ou API
        """
        rate_limiter.acquire()
        client = get_http_client(timeout=timeout)
        resp = client.get(url, params=params)

        # Vérifier le statut HTTP
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Erreur HTTP Bybit GET {url} | category={category} "
                f"page={page_index} limit={params.get('limit')} "
                f"cursor={params.get('cursor','-')} "
                f"status={resp.status_code} detail=\"{resp.text[:200]}\""
            )

        data = resp.json()
        if data.get("retCode") != 0:
            raise RuntimeError(
                f"Erreur API Bybit GET {url} | category={category} "
                f"page={page_index} retCode={data.get('retCode')} "
                f"retMsg=\"{data.get('retMsg', '')}\""
            )

        return data.get("result", {})

    def _process_tickers_for_spreads(
        self, tickers: list, wanted: set, found: Dict[str, float]
    ):
        """
        Traite les tickers pour extraire les spreads.

        Args:
            tickers: Liste des tickers de l'API
            wanted: Set des symboles recherchés
            found: Dictionnaire des résultats (modifié en place)
        """
        for t in tickers:
            sym = t.get("symbol")
            if sym in wanted:
                spread_pct = self._calculate_spread_from_ticker(t)
                if spread_pct is not None:
                    found[sym] = spread_pct

    def _calculate_spread_from_ticker(self, ticker: dict) -> Optional[float]:
        """
        Calcule le spread en pourcentage à partir d'un ticker.

        Args:
            ticker: Dictionnaire du ticker

        Returns:
            Spread en pourcentage ou None si impossible à calculer
        """
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

    def _should_continue_pagination(
        self, found: Dict[str, float], wanted: set, tickers: list
    ) -> bool:
        """
        Détermine si la pagination doit continuer.

        Args:
            found: Symboles trouvés
            wanted: Symboles recherchés
            tickers: Tickers de la page actuelle

        Returns:
            True si la pagination doit continuer
        """
        # Arrêt anticipé si on a tout trouvé
        if len(found) >= len(wanted):
            return False

        # Continuer si on a des tickers
        return len(tickers) > 0

    def _handle_pagination_error(
        self, error: Exception, page_index: int, category: str
    ):
        """
        Gère les erreurs de pagination.

        Args:
            error: Exception levée
            page_index: Index de la page
            category: Catégorie des instruments
        """
        if isinstance(
            error,
            (
                httpx.RequestError,
                httpx.TimeoutException,
                httpx.HTTPStatusError,
            ),
        ):
            self.logger.error(
                f"Erreur réseau spread paginé page={page_index} "
                f"category={category}: {type(error).__name__}: {error}"
            )
        elif isinstance(error, (ValueError, TypeError, KeyError)):
            self.logger.warning(
                f"Erreur données spread paginé page={page_index} "
                f"category={category}: {type(error).__name__}: {error}"
            )
        else:
            self.logger.error(
                f"Erreur inattendue spread paginé page={page_index} "
                f"category={category}: {type(error).__name__}: {error}"
            )

    def _fetch_missing_spreads(
        self,
        base_url: str,
        symbols: List[str],
        found: Dict[str, float],
        timeout: int,
        category: str,
    ):
        """
        Récupère les spreads manquants via des requêtes unitaires.

        Args:
            base_url: URL de base de l'API Bybit
            symbols: Liste des symboles cibles
            found: Dictionnaire des résultats (modifié en place)
            timeout: Timeout HTTP
            category: Catégorie des instruments
        """
        missing = [s for s in symbols if s not in found]
        for s in missing:
            try:
                val = self._fetch_single_spread(base_url, s, timeout, category)
                if val is not None:
                    found[s] = val
            except (httpx.RequestError, ValueError, TypeError):
                # Erreurs réseau ou conversion - ignorer silencieusement pour
                # le fallback
                pass

    def _fetch_single_spread(
        self, base_url: str, symbol: str, timeout: int, category: str
    ) -> Optional[float]:
        """
        Récupère le spread pour un seul symbole.

        Args:
            base_url: URL de base de l'API Bybit
            symbol: Symbole à analyser
            timeout: Timeout pour les requêtes HTTP
            category: Catégorie des symboles ("linear" ou "inverse")

        Returns:
            Spread en pourcentage ou None si erreur
        """
        try:
            url = f"{base_url}/v5/market/tickers"
            params = {"category": category, "symbol": symbol}

            rate_limiter = get_rate_limiter()
            rate_limiter.acquire()
            client = get_http_client(timeout=timeout)
            response = client.get(url, params=params)

            if response.status_code >= 400:
                raise RuntimeError(
                    f"Erreur HTTP Bybit GET {url} | category={category} "
                    f"symbol={symbol} timeout={timeout}s "
                    f"status={response.status_code} "
                    f'detail="{response.text[:200]}"'
                )

            data = response.json()

            if data.get("retCode") != 0:
                ret_code = data.get("retCode")
                ret_msg = data.get("retMsg", "")
                raise RuntimeError(
                    f"Erreur API Bybit GET {url} | category={category} "
                    f"symbol={symbol} timeout={timeout}s "
                    f'retCode={ret_code} retMsg="{ret_msg}"'
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

    def fetch_funding_data_parallel(
        self, base_url: str, categories: List[str], timeout: int = 10
    ) -> Dict[str, Dict]:
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
        with ThreadPoolExecutor(
            max_workers=MAX_WORKERS_THREADPOOL
        ) as executor:
            # Lancer les requêtes en parallèle
            futures = {
                executor.submit(
                    self.fetch_funding_map, base_url, category, timeout
                ): category
                for category in categories
            }

            # Récupérer les résultats
            for future in futures:
                category = futures[future]
                try:
                    category_data = future.result()
                    funding_map.update(category_data)
                except Exception as e:
                    self.logger.error(
                        f"Erreur récupération funding pour {category}: {e}"
                    )
                    raise

        return funding_map
