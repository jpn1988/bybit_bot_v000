#!/usr/bin/env python3
"""
Client privé Bybit (authentifié).

Ce module contient l'implémentation complète de BybitClient.
Cette version utilise les helpers spécialisés pour une meilleure modularité :
- bybit_client.auth.BybitAuthenticator pour l'authentification
- bybit_client.error_handler.BybitErrorHandler pour la gestion d'erreurs
- bybit_client.rate_limiter.BybitRateLimiter pour le rate limiting
"""

import time
import httpx
import random
from typing import Optional, Dict, Any
from config.timeouts import TimeoutConfig
from enhanced_metrics import record_api_call
from http_client_manager import get_http_client
from circuit_breaker import CircuitBreaker, CircuitBreakerOpen
from interfaces.bybit_client_interface import BybitClientInterface
from bybit_client.error_handler import sanitize_error_message
from bybit_client.auth import BybitAuthenticator
from bybit_client.error_handler import BybitErrorHandler
from bybit_client.rate_limiter import BybitRateLimiter


class BybitClient(BybitClientInterface):
    """
    Client pour interagir avec l'API privée Bybit v5.

    Ce client gère :
    - Authentification HMAC-SHA256 pour les requêtes privées
    - Retry automatique avec backoff exponentiel
    - Gestion du rate limiting (429, retCode=10016)
    - Validation des codes de retour API

    Attributes:
        testnet (bool): Utiliser le testnet (True) ou mainnet (False)
        timeout (int): Timeout des requêtes HTTP en secondes
        api_key (str): Clé API Bybit
        api_secret (str): Secret API Bybit (utilisé pour la signature)
        max_retries (int): Nombre maximum de tentatives par requête
        backoff_base (float): Délai de base pour le backoff exponentiel (secondes)
        base_url (str): URL de base de l'API (testnet ou mainnet)

    Example:
        ```python
        # Créer un client pour le testnet
        client = BybitClient(
            testnet=True,
            api_key="YOUR_KEY",
            api_secret="YOUR_SECRET"
        )

        # Récupérer le solde
        balance = client.get_wallet_balance(account_type="UNIFIED")
        print(f"Total equity: {balance['list'][0]['totalEquity']}")
        ```

    Note:
        - Les clés API peuvent être générées sur https://testnet.bybit.com/app/user/api-management
        - Pour le mainnet, utilisez https://www.bybit.com/app/user/api-management
        - Assurez-vous de configurer correctement les permissions IP et API
    """

    def __init__(
        self,
        testnet: bool = True,
        timeout: int = None,
        api_key: str | None = None,
        api_secret: str | None = None,
        max_retries: int = 4,
        backoff_base: float = 0.5,
        recv_window_ms: int = 7000,
        time_sync_enabled: bool = True,
        time_sync_interval_seconds: int = 60,
        logger=None,
    ):
        """
        Initialise le client Bybit.

        Args:
            testnet (bool): Utiliser le testnet (True) ou le marché réel
                (False)
            timeout (int): Timeout pour les requêtes HTTP en secondes
                (utilise TimeoutConfig.HTTP_REQUEST par défaut)
            api_key (str | None): Clé API Bybit
            api_secret (str | None): Secret API Bybit
            max_retries (int): Nombre maximum de tentatives pour les
                requêtes (défaut: 4)
            backoff_base (float): Délai de base pour le backoff exponentiel
                en secondes (défaut: 0.5)
            recv_window_ms (int): Fenêtre de réception Bybit en millisecondes
                (défaut: 7000)
            time_sync_enabled (bool): Active la synchronisation périodique
                avec l'heure serveur (défaut: True)
            time_sync_interval_seconds (int): Intervalle de resynchronisation
                en secondes (défaut: 60)
            logger: Logger optionnel pour les messages

        Raises:
            RuntimeError: Si les clés API sont manquantes
            ValueError: Si les clés API utilisent des valeurs placeholder
        """
        # Validation des credentials (déléguée à BybitAuthenticator)
        if not api_key or not api_secret:
            raise RuntimeError(
                "🔐 Clés API manquantes. Configurez BYBIT_API_KEY et BYBIT_API_SECRET "
                "dans votre fichier .env. Consultez .env.example pour la configuration."
            )

        # Vérifier que les clés ne sont pas des valeurs placeholder
        if api_key == "your_api_key_here" or api_secret == "your_api_secret_here":
            raise ValueError(
                "🔐 ERREUR SÉCURITÉ: Vous utilisez les valeurs placeholder par défaut.\n"
                "Veuillez configurer vos vraies clés API dans le fichier .env.\n"
                "Obtenez vos clés sur: https://testnet.bybit.com/app/user/api-management"
            )

        self.testnet = testnet
        self.timeout = timeout if timeout is not None else TimeoutConfig.HTTP_REQUEST
        self.api_key = api_key
        self.api_secret = api_secret
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.recv_window_ms = recv_window_ms if recv_window_ms and recv_window_ms > 0 else 10000
        self._time_sync_enabled = time_sync_enabled
        self._time_sync_interval_seconds = max(10, time_sync_interval_seconds or 60)
        self._last_time_sync = 0.0
        self.logger = logger  # Stocker le logger pour les logs de debug

        # Définir l'URL de base selon l'environnement
        from config.urls import URLConfig
        self.base_url = URLConfig.get_api_url(testnet)

        # Circuit Breaker pour protéger contre rate limiting et erreurs répétées
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,      # Ouvrir après 5 échecs consécutifs
            timeout_seconds=60,       # Réessayer après 1 minute
            name=f"BybitAPI-{'testnet' if testnet else 'mainnet'}"
        )

        # Initialiser les helpers spécialisés
        self._authenticator = BybitAuthenticator(api_key, api_secret, recv_window_ms=self.recv_window_ms)
        self._error_handler = BybitErrorHandler(logger)
        self._rate_limiter = BybitRateLimiter()

        # Synchroniser l'horloge avec le serveur si nécessaire
        if self._time_sync_enabled:
            self._sync_time_with_server(initial=True)

    def _get_private(self, path: str, params: dict = None) -> dict:
        """
        Effectue une requête GET privée authentifiée.

        Args:
            path (str): Chemin de l'endpoint
            params (dict): Paramètres de la requête

        Returns:
            dict: Réponse JSON de l'API

        Raises:
            RuntimeError: En cas d'erreur HTTP ou API
        """
        params = params or {}

        self._maybe_sync_time()
        # Construire les headers d'authentification
        headers, query_string = self._build_auth_headers(params)

        # Construire l'URL complète
        url = self._build_request_url(path, query_string)

        # Exécuter la requête avec retry (privée = True)
        return self._execute_request_with_retry(url, headers, is_private=True)

    def _post_private(self, path: str, data: dict = None) -> dict:
        """
        Effectue une requête POST privée authentifiée.

        Args:
            path (str): Chemin de l'endpoint
            data (dict): Données JSON à envoyer dans le body

        Returns:
            dict: Réponse JSON de l'API

        Raises:
            RuntimeError: En cas d'erreur HTTP ou API
        """
        data = data or {}

        # Pour les requêtes POST, nous devons inclure les données JSON dans la signature
        import json
        json_data = json.dumps(data, separators=(',', ':'))  # Format compact sans espaces

        # 🔍 DEBUG : Log dans _post_private() après sérialisation JSON
        if hasattr(self, 'logger') and self.logger and 'qty' in data:
            # Extraire la valeur de qty du JSON sérialisé pour voir comment elle est représentée
            import re
            qty_match = re.search(r'"qty":\s*"([^"]+)"', json_data)
            qty_in_json = qty_match.group(1) if qty_match else None
            qty_match_num = re.search(r'"qty":\s*(\d+\.?\d*)', json_data)
            qty_in_json_num = qty_match_num.group(1) if qty_match_num else None
            self.logger.debug(
                f"[DEBUG_QTY] _post_private() - Sérialisation JSON: "
                f"data['qty']={data.get('qty')} (type={type(data.get('qty')).__name__}, repr={repr(data.get('qty'))}), "
                f"json_data_complet={json_data}, "
                f"qty_dans_json_str={qty_in_json}, "
                f"qty_dans_json_num={qty_in_json_num}, "
                f"longueur_json={len(json_data)}"
            )

        self._maybe_sync_time()
        # Construire les headers d'authentification avec les données JSON
        headers, query_string = self._build_auth_headers({}, json_data)

        # Construire l'URL complète
        url = self._build_request_url(path, query_string)

        # Ajouter Content-Type pour POST
        headers["Content-Type"] = "application/json"

        # Exécuter la requête POST avec retry
        return self._execute_post_request_with_retry(url, headers, data, is_private=True)

    def _get_public(self, path: str, params: dict = None) -> dict:
        """
        Effectue une requête GET publique sans authentification.

        Args:
            path (str): Chemin de l'endpoint
            params (dict): Paramètres de la requête

        Returns:
            dict: Réponse JSON de l'API

        Raises:
            RuntimeError: En cas d'erreur HTTP ou API
        """
        params = params or {}

        # Construire la query string pour les paramètres
        query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())])

        # Construire l'URL complète avec l'URL publique
        url = f"{self.public_base_url()}{path}"
        if query_string:
            url += f"?{query_string}"

        # Headers simples pour les requêtes publiques
        headers = {"Content-Type": "application/json"}

        # Appliquer rate limiting pour requêtes publiques
        self._apply_rate_limiting(is_private=False)

        # Exécuter la requête avec retry (mais sans circuit breaker pour les publiques)
        start_time = time.time()

        try:
            client = get_http_client(timeout=self.timeout)
            response = client.get(url, headers=headers)

            # Gérer la réponse HTTP
            self._handle_http_response(response, 1, 1, self.backoff_base)

            # Décoder et valider la réponse API
            data = response.json()
            self._handle_api_response(data, response, 1, 1, self.backoff_base)

            # Succès - enregistrer les métriques
            latency = time.time() - start_time
            record_api_call(latency * 1000, success=True)

            return data.get("result", {})

        except Exception as e:
            latency = time.time() - start_time
            record_api_call(latency * 1000, success=False)
            raise RuntimeError(f"Erreur requête publique Bybit: {e}") from e

    def _build_auth_headers(self, params: dict, json_data: str = None) -> tuple[dict, str]:
        """
        Construit les headers d'authentification HMAC-SHA256 pour une requête privée Bybit v5.

        Cette méthode délègue à BybitAuthenticator pour construire les headers.

        Args:
            params (dict): Paramètres de la requête à envoyer à l'API
            json_data (str): Données JSON pour les requêtes POST (optionnel)

        Returns:
            tuple[dict, str]: Tuple contenant headers et query_string
        """
        return self._authenticator.build_auth_headers(params, json_data)

    def _build_request_url(self, path: str, query_string: str) -> str:
        """
        Construit l'URL complète de la requête.

        Args:
            path: Chemin de l'endpoint
            query_string: Query string des paramètres

        Returns:
            URL complète
        """
        url = f"{self.base_url}{path}"
        if query_string:
            url += f"?{query_string}"
        return url

    def _maybe_sync_time(self) -> None:
        """Synchronise l'horloge locale avec Bybit si l'intervalle est écoulé."""
        if not self._time_sync_enabled:
            return

        now = time.time()
        if now - self._last_time_sync >= self._time_sync_interval_seconds:
            self._sync_time_with_server()

    def _sync_time_with_server(self, initial: bool = False) -> None:
        """Récupère l'heure du serveur Bybit pour ajuster le timestamp local."""
        try:
            client = get_http_client(timeout=self.timeout)
            response = client.get(f"{self.base_url}/v5/market/time")
            response.raise_for_status()
            data = response.json() if response.content else {}
            result = data.get("result") or {}

            server_ms = None

            if isinstance(result, dict):
                time_nano = result.get("timeNano")
                if time_nano:
                    server_ms = int(str(time_nano)[:13])
                else:
                    time_second = result.get("timeSecond")
                    if time_second is not None:
                        server_ms = int(float(time_second) * 1000)

            if server_ms is None:
                time_value = data.get("time") or data.get("ts")
                if time_value is not None:
                    server_ms = int(float(time_value))

            if server_ms is None:
                return

            local_ms = int(time.time() * 1000)
            offset = server_ms - local_ms
            self._authenticator.set_time_offset(offset)
            self._last_time_sync = time.time()

            if self.logger:
                msg = f"[TIME_SYNC] Offset horloge Bybit: {offset} ms"
                if initial:
                    self.logger.info(msg)
                else:
                    self.logger.debug(msg)
        except Exception as exc:
            if self.logger:
                self.logger.debug(f"[TIME_SYNC] Impossible de synchroniser l'horloge: {exc}")

    def _execute_request_with_retry(self, url: str, headers: dict, is_private: bool = True) -> dict:
        """
        Exécute une requête HTTP avec mécanisme de retry et Circuit Breaker.

        Args:
            url: URL de la requête
            headers: Headers HTTP

        Returns:
            Réponse JSON décodée

        Raises:
            RuntimeError: En cas d'erreur
            CircuitBreakerOpen: Si le circuit breaker est ouvert
        """
        # Appliquer rate limiting avant requête
        self._apply_rate_limiting(is_private)

        # Wrapper avec Circuit Breaker pour protection contre erreurs répétées
        try:
            return self.circuit_breaker.call(
                self._execute_request_internal,
                url,
                headers
            )
        except CircuitBreakerOpen as e:
            # Circuit ouvert : API temporairement indisponible
            raise RuntimeError(
                f"⚠️ API Bybit temporairement indisponible - "
                f"Circuit Breaker ouvert (trop d'erreurs récentes). "
                f"Réessayez dans quelques instants."
            ) from e

    def _apply_rate_limiting(self, is_private: bool):
        """
        Applique le rate limiting avant d'exécuter une requête.

        Cette méthode délègue à BybitRateLimiter.

        Args:
            is_private: True pour API privée, False pour API publique
        """
        self._rate_limiter.apply_rate_limiting(is_private)

    def _execute_request_internal(self, url: str, headers: dict) -> dict:
        """
        Méthode interne pour l'exécution de requête (utilisée par Circuit Breaker).

        Args:
            url: URL de la requête
            headers: Headers HTTP

        Returns:
            Réponse JSON décodée

        Raises:
            RuntimeError: En cas d'erreur
        """
        # Utiliser les paramètres configurables de l'instance
        max_attempts = self.max_retries
        backoff_base = self.backoff_base
        start_time = time.time()

        # Exécuter la boucle de retry
        result = self._handle_retry_loop(
            url, headers, max_attempts, backoff_base, start_time
        )

        if result is not None:
            return result

        # Échec après tous les retries
        self._handle_final_failure(start_time)

    def _execute_post_request_with_retry(self, url: str, headers: dict, data: dict, is_private: bool = True) -> dict:
        """
        Exécute une requête POST HTTP avec mécanisme de retry et Circuit Breaker.

        Args:
            url: URL de la requête
            headers: Headers HTTP
            data: Données JSON à envoyer
            is_private: Si c'est une requête privée (pour rate limiting)

        Returns:
            Réponse JSON décodée

        Raises:
            RuntimeError: En cas d'erreur
            CircuitBreakerOpen: Si le circuit breaker est ouvert
        """
        # Appliquer rate limiting avant requête
        self._apply_rate_limiting(is_private)

        # Wrapper avec Circuit Breaker pour protection contre erreurs répétées
        try:
            return self.circuit_breaker.call(
                self._execute_post_request_internal,
                url,
                headers,
                data
            )
        except CircuitBreakerOpen as e:
            # Circuit ouvert : API temporairement indisponible
            raise RuntimeError(
                f"⚠️ API Bybit temporairement indisponible - "
                f"Circuit Breaker ouvert (trop d'erreurs récentes). "
                f"Réessayez dans quelques instants."
            ) from e

    def _execute_post_request_internal(self, url: str, headers: dict, data: dict) -> dict:
        """
        Méthode interne pour l'exécution de requête POST (utilisée par Circuit Breaker).

        Args:
            url: URL de la requête
            headers: Headers HTTP
            data: Données JSON à envoyer

        Returns:
            Réponse JSON décodée

        Raises:
            RuntimeError: En cas d'erreur
        """
        # Utiliser les paramètres configurables de l'instance
        max_attempts = self.max_retries
        backoff_base = self.backoff_base
        start_time = time.time()

        # Exécuter la boucle de retry pour POST
        result = self._handle_post_retry_loop(
            url, headers, data, max_attempts, backoff_base, start_time
        )

        if result is not None:
            return result

        # Échec après tous les retries
        self._handle_final_failure(start_time)

    def _handle_post_retry_loop(
        self,
        url: str,
        headers: dict,
        data: dict,
        max_attempts: int,
        backoff_base: float,
        start_time: float,
    ) -> dict | None:
        """Gère la boucle de retry pour les requêtes POST HTTP."""
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                # Effectuer la requête POST et traiter la réponse
                return self._process_successful_post_request(
                    url,
                    headers,
                    data,
                    attempt,
                    max_attempts,
                    backoff_base,
                    start_time,
                )

            except Exception as e:
                last_error = self._execute_post_with_error_handling(
                    e, attempt, max_attempts, backoff_base
                )
                if last_error is None:
                    # Erreur gérée, continuer le retry
                    continue
                else:
                    # Erreur fatale, sortir de la boucle
                    break

        # Échec - préparer l'erreur finale
        self._prepare_final_error(last_error)
        return None

    def _execute_post_with_error_handling(
        self,
        error: Exception,
        attempt: int,
        max_attempts: int,
        backoff_base: float,
    ) -> Exception | None:
        """
        Gère les erreurs POST avec retry logic approprié.

        Args:
            error: Exception capturée
            attempt: Numéro de tentative actuelle
            max_attempts: Nombre maximum de tentatives
            backoff_base: Délai de base pour le backoff

        Returns:
            Exception | None: None si l'erreur peut être retry, Exception sinon
        """
        # Erreurs de timeout - retry
        if isinstance(error, (
            httpx.TimeoutException,
            httpx.ReadTimeout,
            httpx.ConnectTimeout,
        )):
            if self._should_retry(attempt, max_attempts):
                self._wait_before_retry(attempt, backoff_base)
                return None
            return error

        # Erreurs de requête HTTP - retry
        if isinstance(error, (httpx.RequestError, httpx.HTTPStatusError)):
            if self._should_retry(attempt, max_attempts):
                self._wait_before_retry(attempt, backoff_base)
                return None
            return error

        # Erreurs de données - pas de retry
        if isinstance(error, (ValueError, TypeError, KeyError)):
            return error

        # Erreurs formatées connues - propager
        if "Erreur" in str(error):
            raise error

        # Autres erreurs - pas de retry
        return error

    def _process_successful_post_request(
        self,
        url: str,
        headers: dict,
        data: dict,
        attempt: int,
        max_attempts: int,
        backoff_base: float,
        start_time: float,
    ) -> dict:
        """Traite une requête POST HTTP réussie."""
        # Effectuer la requête POST
        client = get_http_client(timeout=self.timeout)
        response = client.post(url, headers=headers, json=data)

        # Gérer la réponse HTTP
        self._handle_http_response(
            response, attempt, max_attempts, backoff_base
        )

        # Décoder et valider la réponse API
        data = response.json()
        self._handle_api_response(
            data, response, attempt, max_attempts, backoff_base
        )

        # Succès - enregistrer les métriques
        latency = time.time() - start_time
        record_api_call(latency * 1000, success=True)

        return data.get("result", {})

    def _handle_retry_loop(
        self,
        url: str,
        headers: dict,
        max_attempts: int,
        backoff_base: float,
        start_time: float,
    ) -> dict | None:
        """Gère la boucle de retry pour les requêtes HTTP."""
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                # Effectuer la requête et traiter la réponse
                return self._process_successful_request(
                    url,
                    headers,
                    attempt,
                    max_attempts,
                    backoff_base,
                    start_time,
                )

            except Exception as e:
                last_error = self._execute_with_error_handling(
                    e, attempt, max_attempts, backoff_base
                )
                if last_error is None:
                    # Erreur gérée, continuer le retry
                    continue
                else:
                    # Erreur fatale, sortir de la boucle
                    break

        # Échec - préparer l'erreur finale
        self._prepare_final_error(last_error)
        return None

    def _execute_with_error_handling(
        self,
        error: Exception,
        attempt: int,
        max_attempts: int,
        backoff_base: float,
    ) -> Exception | None:
        """
        Gère les erreurs avec retry logic approprié.

        Args:
            error: Exception capturée
            attempt: Numéro de tentative actuelle
            max_attempts: Nombre maximum de tentatives
            backoff_base: Délai de base pour le backoff

        Returns:
            Exception | None: None si l'erreur peut être retry, Exception sinon
        """
        # Erreurs de timeout - retry
        if isinstance(error, (
            httpx.TimeoutException,
            httpx.ReadTimeout,
            httpx.ConnectTimeout,
        )):
            if self._should_retry(attempt, max_attempts):
                self._wait_before_retry(attempt, backoff_base)
                return None
            return error

        # Erreurs de requête HTTP - retry
        if isinstance(error, (httpx.RequestError, httpx.HTTPStatusError)):
            if self._should_retry(attempt, max_attempts):
                self._wait_before_retry(attempt, backoff_base)
                return None
            return error

        # Erreurs de données - pas de retry
        if isinstance(error, (ValueError, TypeError, KeyError)):
            return error

        # Erreurs formatées connues - propager
        if "Erreur" in str(error):
            raise error

        # Autres erreurs - pas de retry
        return error

    def _process_successful_request(
        self,
        url: str,
        headers: dict,
        attempt: int,
        max_attempts: int,
        backoff_base: float,
        start_time: float,
    ) -> dict:
        """Traite une requête HTTP réussie."""
        # Effectuer la requête
        client = get_http_client(timeout=self.timeout)
        response = client.get(url, headers=headers)

        # Gérer la réponse HTTP
        self._handle_http_response(
            response, attempt, max_attempts, backoff_base
        )

        # Décoder et valider la réponse API
        data = response.json()
        self._handle_api_response(
            data, response, attempt, max_attempts, backoff_base
        )

        # Succès - enregistrer les métriques
        latency = time.time() - start_time
        record_api_call(latency * 1000, success=True)

        return data.get("result", {})

    def _should_retry(self, attempt: int, max_attempts: int) -> bool:
        """Détermine si un retry doit être effectué."""
        return attempt < max_attempts

    def _wait_before_retry(self, attempt: int, backoff_base: float):
        """
        Attend avant de retry avec délai de backoff.

        CORRECTIF PERF-002: Détection du contexte async pour éviter de bloquer l'event loop.
        """
        delay = self._error_handler.calculate_retry_delay(attempt, backoff_base)

        # CORRECTIF PERF-002: Vérifier si on est dans un event loop async
        try:
            import asyncio
            loop = asyncio.get_running_loop()
            # Si on arrive ici, on EST dans un event loop async
            import logging
            logging.getLogger(__name__).warning(
                "PERF-002: Tentative de retry dans un contexte async. "
                "Le délai sera ignoré pour éviter de bloquer l'event loop."
            )
            # Ne pas faire de time.sleep() dans un contexte async
            return
        except RuntimeError:
            # Pas d'event loop actif = contexte synchrone, c'est OK pour time.sleep()
            time.sleep(delay)  # Délai calculé dynamiquement, pas de constante

    def _prepare_final_error(self, last_error: Exception | None):
        """Prépare l'erreur finale pour l'échec."""
        # Stocker l'erreur pour le traitement final
        self._last_error = last_error

    def _handle_final_failure(self, start_time: float):
        """Gère l'échec final après tous les retries."""
        latency = time.time() - start_time
        record_api_call(latency * 1000, success=False)

        raise RuntimeError(
            f"Erreur réseau/HTTP Bybit : "
            f"{getattr(self, '_last_error', 'Erreur inconnue')}"
        )

    def _handle_http_response(
        self,
        response: httpx.Response,
        attempt: int,
        max_attempts: int,
        backoff_base: float,
    ):
        """
        Gère les erreurs HTTP et rate limiting.

        Cette méthode délègue à BybitErrorHandler.

        Args:
            response: Réponse HTTP
            attempt: Numéro de la tentative actuelle
            max_attempts: Nombre maximum de tentatives
            backoff_base: Délai de base pour le backoff

        Raises:
            httpx.HTTPStatusError: Pour les erreurs serveur (retry)
            RuntimeError: Pour les erreurs client (pas de retry)
        """
        self._error_handler.handle_http_response(
            response, attempt, max_attempts, backoff_base
        )

    def _handle_api_response(
        self,
        data: dict,
        response: httpx.Response,
        attempt: int,
        max_attempts: int,
        backoff_base: float,
    ):
        """
        Gère les codes de retour de l'API Bybit.

        Cette méthode délègue à BybitErrorHandler.

        Args:
            data: Réponse JSON décodée
            response: Réponse HTTP brute
            attempt: Numéro de la tentative actuelle
            max_attempts: Nombre maximum de tentatives
            backoff_base: Délai de base pour le backoff

        Raises:
            RuntimeError: Pour les erreurs API
        """
        self._error_handler.handle_api_response(
            data, response, attempt, max_attempts, backoff_base
        )

    def public_base_url(self) -> str:
        """
        Retourne l'URL de base publique pour les endpoints sans
        authentification.

        Returns:
            str: URL de base publique (testnet ou mainnet)
        """
        if self.testnet:
            return "https://api-testnet.bybit.com"
        else:
            return "https://api.bybit.com"

    def get_wallet_balance(self, account_type: str = "UNIFIED") -> dict:
        """
        Récupère le solde du portefeuille.

        Args:
            account_type (str): Type de compte (défaut: UNIFIED)

        Returns:
            dict: Données brutes du solde
        """
        return self._get_private(
            "/v5/account/wallet-balance", {"accountType": account_type}
        )

    def get_tickers(self, category: str = "linear", symbol: Optional[str] = None) -> Dict[str, Any]:
        """Récupère les données de tickers."""
        params = {"category": category}
        if symbol:
            params["symbol"] = symbol
        return self._get_public("/v5/market/tickers", params)

    def get_funding_rate_history(
        self,
        category: str = "linear",
        symbol: Optional[str] = None,
        limit: int = 200
    ) -> Dict[str, Any]:
        """Récupère l'historique des taux de funding."""
        params = {"category": category, "limit": limit}
        if symbol:
            params["symbol"] = symbol
        return self._get_public("/v5/market/funding/history", params)

    def get_funding_rate(self, symbol: str, category: str = "linear") -> Dict[str, Any]:
        """
        Récupère le taux de funding actuel pour un symbole.

        Args:
            symbol: Symbole à vérifier
            category: Catégorie des symboles ("linear", "inverse", "spot")

        Returns:
            Dict contenant le taux de funding actuel
        """
        params = {"category": category, "symbol": symbol, "limit": 1}
        return self._get_public("/v5/market/funding/history", params)

    def get_instruments_info(
        self,
        category: str = "linear",
        symbol: Optional[str] = None
    ) -> Dict[str, Any]:
        """Récupère les informations sur les instruments."""
        params = {"category": category}
        if symbol:
            params["symbol"] = symbol
        return self._get_public("/v5/market/instruments-info", params)

    def get_orderbook(
        self,
        category: str = "linear",
        symbol: str = "BTCUSDT",
        limit: int = 25
    ) -> Dict[str, Any]:
        """Récupère le carnet d'ordres."""
        params = {"category": category, "symbol": symbol, "limit": limit}
        return self._get_public("/v5/market/orderbook", params)

    def get_kline(
        self,
        category: str = "linear",
        symbol: str = "BTCUSDT",
        interval: str = "1",
        limit: int = 200
    ) -> Dict[str, Any]:
        """Récupère les données de chandeliers (kline)."""
        params = {
            "category": category,
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        return self._get_public("/v5/market/kline", params)

    def get_positions(self, category: str = "linear", settleCoin: str = None) -> Dict[str, Any]:
        """Récupère les positions ouvertes."""
        params = {"category": category}
        if settleCoin:
            params["settleCoin"] = settleCoin
        return self._get_private("/v5/position/list", params)

    def get_open_orders(self, category: str = "linear", settleCoin: str = None) -> Dict[str, Any]:
        """Récupère les ordres ouverts."""
        params = {"category": category}
        if settleCoin:
            params["settleCoin"] = settleCoin
        return self._get_private("/v5/order/realtime", params)

    def is_testnet(self) -> bool:
        """Indique si le client utilise le testnet."""
        return self.testnet

    def get_timeout(self) -> int:
        """Retourne le timeout configuré."""
        return self.timeout

    def set_timeout(self, timeout: int) -> None:
        """Définit le timeout."""
        self.timeout = timeout

    def is_authenticated(self) -> bool:
        """Indique si le client est authentifié."""
        return bool(self.api_key and self.api_secret)

    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Retourne le statut du rate limiting."""
        return {
            "circuit_breaker_state": self.circuit_breaker.state,
            "failure_count": self.circuit_breaker.failure_count,
            "last_failure_time": self.circuit_breaker.last_failure_time,
            "next_attempt_time": self.circuit_breaker.next_attempt_time
        }

    def reset_rate_limit(self) -> None:
        """Remet à zéro le compteur de rate limiting."""
        self.circuit_breaker.reset()

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str = "Limit",
        qty: str = None,
        price: str = None,
        category: str = "linear",
        time_in_force: str = "PostOnly"
    ) -> Dict[str, Any]:
        """
        Place un ordre sur Bybit.

        Args:
            symbol: Symbole de la paire (ex: "BTCUSDT")
            side: "Buy" ou "Sell"
            order_type: Type d'ordre ("Limit", "Market", etc.)
            qty: Quantité à trader
            price: Prix limite (requis pour les ordres Limit)
            category: Catégorie ("linear", "inverse", "spot")
            time_in_force: Type d'exécution ("PostOnly", "GTC", "IOC", "FOK")

        Returns:
            Dict contenant la réponse de l'API avec l'ID de l'ordre

        Raises:
            RuntimeError: En cas d'erreur API
        """
        order_data = {
            "category": category,
            "symbol": symbol,
            "side": side,
            "orderType": order_type,
            "qty": qty
        }

        if order_type == "Limit" and price:
            order_data["price"] = price

        # Ajouter timeInForce pour forcer les ordres maker
        if order_type == "Limit":
            order_data["timeInForce"] = time_in_force

        # 🔍 DEBUG : Log dans BybitClient.place_order() avant sérialisation
        import json
        if hasattr(self, 'logger') and self.logger:
            self.logger.debug(
                f"[DEBUG_QTY] {symbol} ({category}) - BybitClient.place_order: "
                f"qty_reçue={qty} (type={type(qty).__name__}, repr={repr(qty)}), "
                f"order_data={order_data}, "
                f"order_data['qty']={order_data.get('qty')} (type={type(order_data.get('qty')).__name__}, repr={repr(order_data.get('qty'))}), "
                f"order_data_json_test={json.dumps(order_data, separators=(',', ':'))}"
            )

        return self._post_private("/v5/order/create", order_data)

    def cancel_order(
        self,
        symbol: str,
        order_id: str = None,
        order_link_id: str = None,
        category: str = "linear"
    ) -> Dict[str, Any]:
        """
        Annule un ordre sur Bybit.

        Args:
            symbol: Symbole de la paire (ex: "BTCUSDT")
            order_id: ID de l'ordre à annuler
            order_link_id: ID de lien de l'ordre (alternative à order_id)
            category: Catégorie ("linear", "inverse", "spot")

        Returns:
            Dict contenant la réponse de l'API

        Raises:
            RuntimeError: En cas d'erreur API
        """
        if not order_id and not order_link_id:
            raise ValueError("order_id ou order_link_id doit être fourni")

        cancel_data = {
            "category": category,
            "symbol": symbol
        }

        if order_id:
            cancel_data["orderId"] = order_id
        if order_link_id:
            cancel_data["orderLinkId"] = order_link_id

        return self._post_private("/v5/order/cancel", cancel_data)


__all__ = ['BybitClient']
