"""Client Bybit pour les opérations synchrones avec authentification privée."""

import time
import hashlib
import hmac
import httpx
import random
try:
    from .config_unified import get_settings
    from .metrics import record_api_call
    from .http_client_manager import get_http_client
except ImportError:
    from config_unified import get_settings
    from metrics import record_api_call
    from http_client_manager import get_http_client


class BybitClient:
    """Client pour interagir avec l'API privée Bybit v5."""
    
    def __init__(
        self, 
        testnet: bool = True, 
        timeout: int = 15,  # Timeout augmenté de 10s à 15s 
        api_key: str | None = None, 
        api_secret: str | None = None
    ):
        """
        Initialise le client Bybit.
        
        Args:
            testnet (bool): Utiliser le testnet (True) ou le marché réel (False)
            timeout (int): Timeout pour les requêtes HTTP en secondes
            api_key (str | None): Clé API Bybit
            api_secret (str | None): Secret API Bybit
            
        Raises:
            RuntimeError: Si les clés API sont manquantes
        """
        if not api_key or not api_secret:
            raise RuntimeError("Clés API manquantes")
            
        self.testnet = testnet
        self.timeout = timeout
        self.api_key = api_key
        self.api_secret = api_secret
        
        # Définir l'URL de base selon l'environnement
        if testnet:
            self.base_url = "https://api-testnet.bybit.com"
        else:
            self.base_url = "https://api.bybit.com"
    
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
        
        # Construire les headers d'authentification
        headers, query_string = self._build_auth_headers(params)
        
        # Construire l'URL complète
        url = self._build_request_url(path, query_string)
        
        # Exécuter la requête avec retry
        return self._execute_request_with_retry(url, headers)
    
    def _build_auth_headers(self, params: dict) -> tuple[dict, str]:
        """
        Construit les headers d'authentification pour une requête privée.
        
        Args:
            params: Paramètres de la requête
            
        Returns:
            Tuple (headers, query_string)
        """
        timestamp = int(time.time() * 1000)
        recv_window_ms = 10000
        
        # Créer la query string triée
        query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        
        # Générer la signature
        signature = self._generate_signature(timestamp, recv_window_ms, query_string)
        
        # Construire les headers
        headers = {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-SIGN": signature,
            "X-BAPI-SIGN-TYPE": "2",
            "X-BAPI-TIMESTAMP": str(timestamp),
            "X-BAPI-RECV-WINDOW": str(recv_window_ms),
            "Content-Type": "application/json"
        }
        
        return headers, query_string
    
    def _generate_signature(self, timestamp: int, recv_window_ms: int, query_string: str) -> str:
        """
        Génère la signature HMAC-SHA256 pour l'authentification.
        
        Args:
            timestamp: Timestamp en millisecondes
            recv_window_ms: Fenêtre de réception en millisecondes
            query_string: Query string des paramètres
            
        Returns:
            Signature hexadécimale
        """
        payload = f"{timestamp}{self.api_key}{recv_window_ms}{query_string}"
        return hmac.new(
            self.api_secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
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
    
    def _execute_request_with_retry(self, url: str, headers: dict) -> dict:
        """
        Exécute une requête HTTP avec mécanisme de retry.
        
        Args:
            url: URL de la requête
            headers: Headers HTTP
            
        Returns:
            Réponse JSON décodée
            
        Raises:
            RuntimeError: En cas d'erreur
        """
        max_attempts = 4
        backoff_base = 0.5
        start_time = time.time()
        
        # Exécuter la boucle de retry
        result = self._handle_retry_loop(url, headers, max_attempts, backoff_base, start_time)
        
        if result is not None:
            return result
        
        # Échec après tous les retries
        self._handle_final_failure(start_time)
    
    def _handle_retry_loop(self, url: str, headers: dict, max_attempts: int, 
                          backoff_base: float, start_time: float) -> dict | None:
        """Gère la boucle de retry pour les requêtes HTTP."""
        last_error: Exception | None = None
        
        for attempt in range(1, max_attempts + 1):
            try:
                # Effectuer la requête et traiter la réponse
                return self._process_successful_request(url, headers, attempt, 
                                                      max_attempts, backoff_base, start_time)
                
            except (httpx.TimeoutException, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
                last_error = e
                if not self._should_retry(attempt, max_attempts):
                    break
                self._wait_before_retry(attempt, backoff_base)
                
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                last_error = e
                if not self._should_retry(attempt, max_attempts):
                    break
                self._wait_before_retry(attempt, backoff_base)
                
            except (ValueError, TypeError, KeyError) as e:
                # Erreurs de données - pas de retry
                last_error = e
                break
                
            except Exception as e:
                # Propager les erreurs formatées connues
                if "Erreur" in str(e):
                    raise
                last_error = e
                break
        
        # Échec - préparer l'erreur finale
        self._prepare_final_error(last_error)
        return None
    
    def _process_successful_request(self, url: str, headers: dict, attempt: int,
                                  max_attempts: int, backoff_base: float, start_time: float) -> dict:
        """Traite une requête HTTP réussie."""
        # Effectuer la requête
        client = get_http_client(timeout=self.timeout)
        response = client.get(url, headers=headers)
        
        # Gérer la réponse HTTP
        self._handle_http_response(response, attempt, max_attempts, backoff_base)
        
        # Décoder et valider la réponse API
        data = response.json()
        self._handle_api_response(data, response, attempt, max_attempts, backoff_base)
        
        # Succès - enregistrer les métriques
        latency = time.time() - start_time
        record_api_call(latency, success=True)
        
        return data.get("result", {})
    
    def _should_retry(self, attempt: int, max_attempts: int) -> bool:
        """Détermine si un retry doit être effectué."""
        return attempt < max_attempts
    
    def _wait_before_retry(self, attempt: int, backoff_base: float):
        """Attend avant de retry avec délai de backoff."""
        delay = self._calculate_retry_delay(attempt, backoff_base)
        time.sleep(delay)
    
    def _prepare_final_error(self, last_error: Exception | None):
        """Prépare l'erreur finale pour l'échec."""
        # Stocker l'erreur pour le traitement final
        self._last_error = last_error
    
    def _handle_final_failure(self, start_time: float):
        """Gère l'échec final après tous les retries."""
        latency = time.time() - start_time
        record_api_call(latency, success=False)
        
        raise RuntimeError(f"Erreur réseau/HTTP Bybit : {getattr(self, '_last_error', 'Erreur inconnue')}")
    
    def _handle_http_response(self, response: httpx.Response, attempt: int, 
                              max_attempts: int, backoff_base: float):
        """
        Gère les erreurs HTTP et rate limiting.
        
        Args:
            response: Réponse HTTP
            attempt: Numéro de la tentative actuelle
            max_attempts: Nombre maximum de tentatives
            backoff_base: Délai de base pour le backoff
            
        Raises:
            httpx.HTTPStatusError: Pour les erreurs serveur (retry)
            RuntimeError: Pour les erreurs client (pas de retry)
        """
        # Erreurs serveur (5xx) - retry
        if response.status_code >= 500:
            raise httpx.HTTPStatusError(
                "Server error", request=None, response=response
            )
        
        # Rate limiting (429) - retry avec backoff
        if response.status_code == 429:
            delay = self._get_retry_after_delay(response, attempt, backoff_base)
            time.sleep(delay)
            raise httpx.HTTPStatusError(
                "Rate limited", request=None, response=response
            )
        
        # Erreurs client (4xx) - pas de retry
        if response.status_code >= 400:
            detail = response.text[:100]
            raise RuntimeError(
                f"Erreur HTTP Bybit: status={response.status_code} detail=\"{detail}\""
            )
    
    def _handle_api_response(self, data: dict, response: httpx.Response, 
                            attempt: int, max_attempts: int, backoff_base: float):
        """
        Gère les codes de retour de l'API Bybit.
        
        Args:
            data: Réponse JSON décodée
            response: Réponse HTTP brute
            attempt: Numéro de la tentative actuelle
            max_attempts: Nombre maximum de tentatives
            backoff_base: Délai de base pour le backoff
            
        Raises:
            RuntimeError: Pour les erreurs API
        """
        ret_code = data.get("retCode")
        if ret_code == 0:
            return  # Succès
        
        ret_msg = data.get("retMsg", "")
        
        # Erreurs d'authentification
        if ret_code in [10005, 10006]:
            raise RuntimeError(
                "Authentification échouée : clé/secret invalides ou signature incorrecte"
            )
        
        # Erreur d'IP non autorisée
        if ret_code == 10018:
            raise RuntimeError(
                "Accès refusé : IP non autorisée (whitelist requise dans Bybit)"
            )
        
        # Erreur de timestamp
        if ret_code == 10017:
            raise RuntimeError(
                "Horodatage invalide : horloge locale désynchronisée (corrige l'heure système)"
            )
        
        # Rate limit API - retry
        if ret_code == 10016:
            delay = self._get_retry_after_delay(response, attempt, backoff_base)
            time.sleep(delay)
            if attempt < max_attempts:
                raise httpx.HTTPStatusError(
                    "API Rate limited", request=None, response=response
                )
            raise RuntimeError(
                "Limite de requêtes atteinte : ralentis ou réessaie plus tard"
            )
        
        # Autre erreur API
        raise RuntimeError(
            f"Erreur API Bybit : retCode={ret_code} retMsg=\"{ret_msg}\""
        )
    
    def _get_retry_after_delay(self, response: httpx.Response, 
                               attempt: int, backoff_base: float) -> float:
        """
        Calcule le délai à attendre avant de retry en respectant Retry-After.
        
        Args:
            response: Réponse HTTP
            attempt: Numéro de la tentative
            backoff_base: Délai de base pour le backoff
            
        Returns:
            Délai en secondes
        """
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            delay = float(retry_after)
        else:
            delay = backoff_base * (2 ** (attempt - 1))
        
        # Ajouter un jitter aléatoire
        delay += random.uniform(0, 0.25)
        return delay
    
    def _calculate_retry_delay(self, attempt: int, backoff_base: float) -> float:
        """
        Calcule le délai de retry avec backoff exponentiel et jitter.
        
        Args:
            attempt: Numéro de la tentative
            backoff_base: Délai de base
            
        Returns:
            Délai en secondes
        """
        delay = backoff_base * (2 ** (attempt - 1))
        delay += random.uniform(0, 0.25)
        return delay
    
    def public_base_url(self) -> str:
        """
        Retourne l'URL de base publique pour les endpoints sans authentification.
        
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
        return self._get_private("/v5/account/wallet-balance", {"accountType": account_type})


class BybitPublicClient:
    """Client public Bybit v5 (aucune clé requise)."""

    def __init__(self, testnet: bool = True, timeout: int = 10):
        self.testnet = testnet
        self.timeout = timeout

    def public_base_url(self) -> str:
        """Retourne l'URL de base publique (testnet ou mainnet)."""
        if self.testnet:
            return "https://api-testnet.bybit.com"
        return "https://api.bybit.com"


