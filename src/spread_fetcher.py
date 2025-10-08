#!/usr/bin/env python3
"""
Gestionnaire de récupération des spreads pour le bot Bybit - Version refactorisée.

Cette classe gère uniquement :
- La récupération des données de spread
- Le traitement des données de spread
- La gestion des erreurs spécifiques aux spreads
"""

from typing import Dict, List, Any, Optional
try:
    from .logging_setup import setup_logging
    from .pagination_handler import PaginationHandler
    from .error_handler import ErrorHandler
    from .http_utils import get_rate_limiter
    from .http_client_manager import get_http_client
except ImportError:
    from logging_setup import setup_logging
    from pagination_handler import PaginationHandler
    from error_handler import ErrorHandler
    from http_utils import get_rate_limiter
    from http_client_manager import get_http_client


class SpreadFetcher:
    """
    Gestionnaire de récupération des spreads pour le bot Bybit.

    Responsabilités :
    - Récupération des données de spread
    - Traitement des données de spread
    - Gestion des erreurs spécifiques aux spreads
    """

    def __init__(self, logger=None):
        """
        Initialise le gestionnaire de spreads.

        Args:
            logger: Logger pour les messages (optionnel)
        """
        self.logger = logger or setup_logging()
        self._pagination_handler = PaginationHandler(logger)
        self._error_handler = ErrorHandler(logger)

    def fetch_spread_data(
        self,
        base_url: str,
        symbols: List[str],
        timeout: int = 10,
        category: str = "linear",
    ) -> Dict[str, float]:
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
        try:
            self.logger.debug(
                f"📊 Récupération spreads pour {len(symbols)} symboles ({category})..."
            )

            # Récupération paginée des spreads
            found = self._fetch_spreads_paginated(base_url, symbols, timeout, category)

            # Fallback unitaire pour les symboles manquants
            self._fetch_missing_spreads(base_url, symbols, found, timeout, category)

            self.logger.info(f"✅ Spreads récupérés: {len(found)}/{len(symbols)} symboles")
            return found

        except Exception as e:
            self._error_handler.log_error(e, f"fetch_spread_data category={category}")
            raise

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

        # Paramètres de base pour la pagination
        params = {"category": category, "limit": 1000}

        try:
            # Récupérer toutes les données via pagination
            all_tickers = self._pagination_handler.fetch_paginated_data(
                base_url, "/v5/market/tickers", params, timeout
            )

            # Traiter les tickers pour extraire les spreads
            self._process_tickers_for_spreads(all_tickers, wanted, found)

        except Exception as e:
            self._error_handler.log_error(e, f"_fetch_spreads_paginated category={category}")
            raise

        return found

    def _process_tickers_for_spreads(
        self, tickers: List[Dict[str, Any]], wanted: set, found: Dict[str, float]
    ):
        """
        Traite les tickers pour extraire les spreads.

        Args:
            tickers: Liste des tickers reçus de l'API
            wanted: Set des symboles recherchés
            found: Dictionnaire des spreads trouvés
        """
        for ticker in tickers:
            try:
                symbol = ticker.get("symbol")
                if symbol in wanted:
                    spread_pct = self._calculate_spread_from_ticker(ticker)
                    if spread_pct is not None:
                        found[symbol] = spread_pct
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur traitement ticker spread: {e}")
                continue

    def _calculate_spread_from_ticker(self, ticker: Dict[str, Any]) -> Optional[float]:
        """
        Calcule le spread en pourcentage à partir d'un ticker.

        Args:
            ticker: Données du ticker

        Returns:
            Spread en pourcentage ou None si impossible
        """
        try:
            bid1 = ticker.get("bid1Price")
            ask1 = ticker.get("ask1Price")

            if bid1 is None or ask1 is None:
                return None

            bid1_float = self._safe_float_conversion(bid1, "bid1Price")
            ask1_float = self._safe_float_conversion(ask1, "ask1Price")

            if bid1_float is None or ask1_float is None:
                return None

            if bid1_float <= 0 or ask1_float <= 0:
                return None

            # Calculer le spread
            mid_price = (ask1_float + bid1_float) / 2
            if mid_price <= 0:
                return None

            spread_pct = (ask1_float - bid1_float) / mid_price
            return spread_pct

        except Exception as e:
            self.logger.debug(f"⚠️ Erreur calcul spread: {e}")
            return None

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
            symbols: Liste des symboles
            found: Dictionnaire des spreads trouvés
            timeout: Timeout HTTP
            category: Catégorie des instruments
        """
        missing = [s for s in symbols if s not in found]

        if not missing:
            return

        self.logger.debug(f"🔍 Récupération spreads manquants: {len(missing)} symboles")

        for symbol in missing:
            try:
                spread = self._fetch_single_spread(base_url, symbol, timeout, category)
                if spread is not None:
                    found[symbol] = spread
            except Exception as e:
                self.logger.debug(f"⚠️ Erreur spread unitaire pour {symbol}: {e}")
                continue

    def _fetch_single_spread(
        self, base_url: str, symbol: str, timeout: int, category: str
    ) -> Optional[float]:
        """
        Récupère le spread pour un seul symbole.

        Args:
            base_url: URL de base de l'API Bybit
            symbol: Symbole à récupérer
            timeout: Timeout HTTP
            category: Catégorie des instruments

        Returns:
            Spread en pourcentage ou None si impossible
        """
        try:
            url = f"{base_url}/v5/market/tickers"
            params = {"category": category, "symbol": symbol}

            rate_limiter = get_rate_limiter()
            rate_limiter.acquire()
            client = get_http_client(timeout=timeout)
            response = client.get(url, params=params)

            if response.status_code >= 400:
                self._error_handler.handle_http_error(url, params, response, f"symbol={symbol}")
                return None

            data = response.json()

            if data.get("retCode") != 0:
                self._error_handler.handle_api_error(url, params, data, f"symbol={symbol}")
                return None

            result = data.get("result", {})
            tickers = result.get("list", [])

            if not tickers:
                return None

            ticker = tickers[0]
            return self._calculate_spread_from_ticker(ticker)

        except Exception as e:
            self.logger.debug(f"⚠️ Erreur récupération spread unitaire {symbol}: {e}")
            return None

    def _safe_float_conversion(self, value: Any, field_name: str) -> Optional[float]:
        """
        Convertit une valeur en float de manière sécurisée.

        Args:
            value: Valeur à convertir
            field_name: Nom du champ (pour les logs)

        Returns:
            Float converti ou None si impossible
        """
        try:
            if value is None:
                return None
            return float(value)
        except (ValueError, TypeError):
            self.logger.debug(f"⚠️ Conversion float échouée pour {field_name}: {value}")
            return None

    def validate_spread_data(self, spread_data: Dict[str, float]) -> bool:
        """
        Valide les données de spread récupérées.

        Args:
            spread_data: Données de spread à valider

        Returns:
            True si les données sont valides
        """
        try:
            if not spread_data:
                self.logger.warning("⚠️ Aucune donnée de spread à valider")
                return False

            valid_count = 0
            for symbol, spread in spread_data.items():
                if self._validate_single_spread_entry(symbol, spread):
                    valid_count += 1

            self.logger.debug(
                f"📊 Validation spread: {valid_count}/{len(spread_data)} entrées valides"
            )
            return valid_count > 0

        except Exception as e:
            self.logger.error(f"❌ Erreur validation spread: {e}")
            return False

    def _validate_single_spread_entry(self, symbol: str, spread: float) -> bool:
        """
        Valide une entrée de spread individuelle.

        Args:
            symbol: Symbole à valider
            spread: Spread en pourcentage

        Returns:
            True si l'entrée est valide
        """
        try:
            if not symbol or not isinstance(spread, (int, float)):
                return False

            # Vérifier que le spread est dans une plage raisonnable
            if spread < 0 or spread > 1:  # 0% à 100%
                return False

            return True

        except Exception:
            return False
