#!/usr/bin/env python3
"""
Client Bybit pour les opérations synchrones avec authentification privée.

╔═══════════════════════════════════════════════════════════════════╗
║                    📖 GUIDE DE LECTURE                            ║
╚═══════════════════════════════════════════════════════════════════╝

Ce fichier implémente un client HTTP authentifié pour l'API privée Bybit v5.
Il gère l'authentification HMAC-SHA256, les retries avec backoff exponentiel,
et le rate limiting.

🔍 COMPRENDRE CE FICHIER EN 5 MINUTES :

1. Authentification HMAC-SHA256 (lignes 120-166)
   └─> Processus de signature des requêtes privées Bybit

2. Mécanisme de retry (lignes 187-240)
   └─> Backoff exponentiel avec jitter pour gérer les erreurs temporaires

3. Gestion du rate limiting (lignes 323-331, 389-401)
   └─> Respect des limites de requêtes avec Retry-After

🔐 PROCESSUS D'AUTHENTIFICATION HMAC-SHA256 :

Bybit v5 utilise HMAC-SHA256 pour authentifier les requêtes privées.

Étapes :
1. Créer un timestamp en millisecondes
2. Trier les paramètres par ordre alphabétique
3. Construire le payload : timestamp + api_key + recv_window + query_string
4. Signer le payload avec HMAC-SHA256 et le secret API
5. Ajouter les headers : X-BAPI-API-KEY, X-BAPI-SIGN, X-BAPI-TIMESTAMP, etc.

Exemple de signature :
    Payload: "1712345678000MY_API_KEY10000symbol=BTCUSDT"
    Signature: HMAC-SHA256(payload, api_secret) -> hex string

📚 EXEMPLE D'UTILISATION :

```python
from bybit_client import BybitClient

# Créer le client
client = BybitClient(
    testnet=True,
    api_key="YOUR_API_KEY",
    api_secret="YOUR_API_SECRET",
    max_retries=4,
    backoff_base=0.5
)

# Récupérer le solde du portefeuille
try:
    balance = client.get_wallet_balance(account_type="UNIFIED")
    print(f"Solde: {balance}")
except RuntimeError as e:
    print(f"Erreur: {e}")
```

⚡ MÉCANISME DE RETRY :

Le client utilise un backoff exponentiel avec jitter pour gérer les erreurs :
- Tentative 1 : Délai = 0.5s + jitter (0-0.25s)
- Tentative 2 : Délai = 1.0s + jitter
- Tentative 3 : Délai = 2.0s + jitter
- Tentative 4 : Délai = 4.0s + jitter

Cas de retry :
- ✅ Timeouts (ReadTimeout, ConnectTimeout)
- ✅ Erreurs serveur (5xx)
- ✅ Rate limiting (429, retCode=10016)
- ❌ Erreurs d'authentification (pas de retry)
- ❌ Erreurs client 4xx (pas de retry)

📊 CODES DE RETOUR BYBIT :

- retCode=0 : Succès ✅
- retCode=10005/10006 : Authentification échouée (clé/secret invalides) 🔐
- retCode=10016 : Rate limit atteint (retry avec backoff) ⏱️
- retCode=10017 : Timestamp invalide (horloge désynchronisée) ⏰
- retCode=10018 : IP non autorisée (whitelist requise) 🚫

📖 RÉFÉRENCES :
- Documentation API Bybit v5: https://bybit-exchange.github.io/docs/v5/intro
- Authentification: https://bybit-exchange.github.io/docs/v5/guide#authentication
"""

import time
import hashlib
import hmac
import httpx
import random
import re
from typing import Optional, Dict, Any
from config.timeouts import TimeoutConfig
from metrics import record_api_call
from http_client_manager import get_http_client
from circuit_breaker import CircuitBreaker, CircuitBreakerOpen
from interfaces.bybit_client_interface import BybitClientInterface


def _sanitize_error_message(message: str) -> str:
    """
    Nettoie un message d'erreur pour éviter fuite de credentials.
    
    Filtre :
    - Clés API (format: alphanumeric 20-40 chars)
    - Signatures HMAC (format: hex 64 chars)
    - Tokens JWT (format: xxx.yyy.zzz)
    """
    if not isinstance(message, str):
        return str(message)
    
    # Masquer clés API (ex: "ABCD1234EFGH5678")
    message = re.sub(r'\b[A-Za-z0-9]{20,40}\b', '***API_KEY***', message)
    
    # Masquer signatures HMAC (ex: "a1b2c3d4...")
    message = re.sub(r'\b[a-f0-9]{64}\b', '***SIGNATURE***', message)
    
    # Masquer tokens JWT
    message = re.sub(r'\b[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\b', '***TOKEN***', message)
    
    return message


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

        Raises:
            RuntimeError: Si les clés API sont manquantes
            ValueError: Si les clés API utilisent des valeurs placeholder
        """
        # SEC-001: Validation renforcée des credentials
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

        # Définir l'URL de base selon l'environnement
        from config.urls import URLConfig
        self.base_url = URLConfig.get_api_url(testnet)
        
        # Circuit Breaker pour protéger contre rate limiting et erreurs répétées
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,      # Ouvrir après 5 échecs consécutifs
            timeout_seconds=60,       # Réessayer après 1 minute
            name=f"BybitAPI-{'testnet' if testnet else 'mainnet'}"
        )

        # CORRECTIF PERF-001: Rate limiters selon documentation Bybit
        try:
            from async_rate_limiter import AsyncRateLimiter
            # Rate limiters selon documentation Bybit API v5
            self._public_limiter = AsyncRateLimiter(
                max_calls=120,  # 120 requêtes
                window_seconds=60  # par minute pour API publique
            )
            self._private_limiter = AsyncRateLimiter(
                max_calls=50,   # 50 requêtes  
                window_seconds=60  # par minute pour API privée
            )
        except ImportError:
            # Fallback si le rate limiter n'est pas disponible
            self._public_limiter = None
            self._private_limiter = None

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

        # CORRECTIF PERF-001: Appliquer rate limiting pour requêtes publiques
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
            record_api_call(latency, success=True)
            
            return data.get("result", {})
            
        except Exception as e:
            latency = time.time() - start_time
            record_api_call(latency, success=False)
            raise RuntimeError(f"Erreur requête publique Bybit: {e}") from e

    def _build_auth_headers(self, params: dict, json_data: str = None) -> tuple[dict, str]:
        """
        Construit les headers d'authentification HMAC-SHA256 pour une requête privée Bybit v5.
        
        Ce processus suit la spécification d'authentification Bybit v5 :
        1. Générer un timestamp en millisecondes
        2. Trier les paramètres par ordre alphabétique (clés)
        3. Construire la query string triée
        4. Générer la signature HMAC-SHA256
        5. Construire les headers avec la signature
        
        Format du payload signé :
            timestamp + api_key + recv_window + query_string
            
        Exemple :
            params = {"symbol": "BTCUSDT", "category": "linear"}
            → query_string = "category=linear&symbol=BTCUSDT"  (ordre alphabétique)
            → payload = "1712345678000MY_API_KEY10000category=linear&symbol=BTCUSDT"
            → signature = HMAC-SHA256(payload, api_secret).hex()

        Args:
            params (dict): Paramètres de la requête à envoyer à l'API
                         Exemple: {"symbol": "BTCUSDT", "category": "linear"}

        Returns:
            tuple[dict, str]: Tuple contenant :
                - headers (dict) : Headers HTTP avec authentification
                    * X-BAPI-API-KEY : Clé API publique
                    * X-BAPI-SIGN : Signature HMAC-SHA256 (hex)
                    * X-BAPI-SIGN-TYPE : Type de signature (2 = HMAC-SHA256)
                    * X-BAPI-TIMESTAMP : Timestamp en millisecondes
                    * X-BAPI-RECV-WINDOW : Fenêtre de réception (10000ms)
                    * Content-Type : application/json
                - query_string (str) : Paramètres triés au format "key1=val1&key2=val2"
                
        Note:
            - Le recv_window (10000ms) définit la durée pendant laquelle
              la requête est considérée comme valide par Bybit
            - Si l'horloge locale est désynchronisée, vous obtiendrez retCode=10017
            - Les paramètres DOIVENT être triés alphabétiquement pour la signature
        """
        # Générer un timestamp en millisecondes (epoch time * 1000)
        # Bybit utilise ce timestamp pour valider la fraîcheur de la requête
        timestamp = int(time.time() * 1000)
        
        # Fenêtre de réception : durée pendant laquelle la requête est valide
        # 10000ms = 10 secondes (valeur recommandée par Bybit)
        recv_window_ms = 10000

        # Créer la query string triée par ordre alphabétique des clés
        # IMPORTANT : L'ordre alphabétique est OBLIGATOIRE pour la signature
        # Exemple : {"z": 1, "a": 2} → "a=2&z=1"
        query_string = "&".join(
            [f"{k}={v}" for k, v in sorted(params.items())]
        )
        
        # Pour les requêtes POST, inclure les données JSON dans la signature
        if json_data:
            # Pour POST, la signature doit inclure les données JSON
            payload_data = json_data
        else:
            # Pour GET, utiliser la query string
            payload_data = query_string

        # Générer la signature HMAC-SHA256 du payload
        # Le payload est construit selon le format Bybit v5
        signature = self._generate_signature(
            timestamp, recv_window_ms, payload_data
        )

        # Construire les headers d'authentification
        # Ces headers sont requis pour toutes les requêtes privées Bybit v5
        headers = {
            "X-BAPI-API-KEY": self.api_key,           # Clé API publique
            "X-BAPI-SIGN": signature,                  # Signature HMAC-SHA256
            "X-BAPI-SIGN-TYPE": "2",                   # Type : 2 = HMAC-SHA256
            "X-BAPI-TIMESTAMP": str(timestamp),        # Timestamp en ms
            "X-BAPI-RECV-WINDOW": str(recv_window_ms), # Fenêtre de validité
            "Content-Type": "application/json",        # Format JSON
        }

        return headers, query_string

    def _generate_signature(
        self, timestamp: int, recv_window_ms: int, query_string: str
    ) -> str:
        """
        Génère la signature HMAC-SHA256 pour l'authentification Bybit v5.
        
        Cette signature prouve que vous possédez le secret API sans le transmettre.
        Bybit recalcule la signature de son côté et la compare avec celle fournie.
        
        Algorithme HMAC-SHA256 :
        1. Construire le payload : timestamp + api_key + recv_window + query_string
        2. Encoder le payload et le secret en UTF-8
        3. Calculer HMAC-SHA256(payload, secret)
        4. Convertir en hexadécimal (chaîne de 64 caractères)
        
        Exemple concret :
            timestamp = 1712345678000
            api_key = "ABCDEF123456"
            recv_window_ms = 10000
            query_string = "category=linear&symbol=BTCUSDT"
            
            → payload = "1712345678000ABCDEF12345610000category=linear&symbol=BTCUSDT"
            → HMAC-SHA256(payload, secret) → "a1b2c3d4e5f6..." (64 caractères hex)

        Args:
            timestamp (int): Timestamp en millisecondes (epoch time * 1000)
                           Doit être synchronisé avec le serveur Bybit (±5 secondes)
            recv_window_ms (int): Fenêtre de réception en millisecondes (ex: 10000)
                                 Durée pendant laquelle la requête reste valide
            query_string (str): Paramètres triés au format "key1=val1&key2=val2"
                              Chaîne vide si aucun paramètre

        Returns:
            str: Signature HMAC-SHA256 en hexadécimal (64 caractères)
                Exemple: "a1b2c3d4e5f6789012345678901234567890abcdef..."
                
        Note:
            - La signature est unique pour chaque requête (timestamp différent)
            - Si le payload ou le secret change, la signature sera différente
            - Bybit rejette les requêtes avec une mauvaise signature (retCode=10005/10006)
            - Si l'horloge locale est désynchronisée, vous obtiendrez retCode=10017
            
        Security:
            - Le secret API n'est JAMAIS envoyé sur le réseau
            - Seule la signature (dérivée du secret) est transmise
            - Sans le secret, impossible de générer une signature valide
        """
        # Construire le payload selon le format Bybit v5
        # Format : timestamp + api_key + recv_window + query_string (concaténés)
        payload = f"{timestamp}{self.api_key}{recv_window_ms}{query_string}"
        
        # Calculer la signature HMAC-SHA256
        # 1. Encoder le secret et le payload en bytes UTF-8
        # 2. Calculer le hash HMAC avec SHA256
        # 3. Convertir en hexadécimal (string de 64 caractères)
        return hmac.new(
            self.api_secret.encode("utf-8"),  # Clé secrète (bytes)
            payload.encode("utf-8"),          # Message à signer (bytes)
            hashlib.sha256,                   # Algorithme de hash
        ).hexdigest()  # Résultat en hexadécimal

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
        # CORRECTIF PERF-001: Appliquer rate limiting avant requête
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
        
        CORRECTIF PERF-001: Rate limiting simplifié pour éviter les event loops imbriquées.
        Version synchrone uniquement - ce client ne doit être utilisé que dans des threads dédiés.
        
        Args:
            is_private: True pour API privée, False pour API publique
        """
        limiter = self._private_limiter if is_private else self._public_limiter
        
        if limiter is None:
            return  # Pas de rate limiting si les limiters ne sont pas disponibles
            
        try:
            # CORRECTIF PERF-002: Éviter time.sleep() si on détecte un contexte async
            # Bien que ce client soit prévu pour être synchrone, on s'assure qu'il
            # ne bloque pas un event loop par erreur
            import asyncio
            try:
                # Vérifier si on est dans un event loop
                loop = asyncio.get_running_loop()
                # Si on arrive ici, on EST dans un event loop async
                # Log warning mais ne pas bloquer avec time.sleep
                import logging
                logging.getLogger(__name__).warning(
                    "PERF-002: BybitClient synchron utilisé depuis un contexte async. "
                    "Utilisez un thread dédié pour éviter de bloquer l'event loop."
                )
                return  # Skip le rate limiting pour éviter de bloquer
            except RuntimeError:
                # Pas d'event loop actif = contexte synchrone, c'est OK
                pass
            
            # CORRECTIF ARCH-001: Version simplifiée - vérifier le compteur actuel
            current_count = limiter.get_current_count()
            max_calls = limiter.max_calls
            
            if current_count >= max_calls:
                # Si on est proche de la limite, faire une pause
                # Sans effectuer cette vérification async, on peut utiliser time.sleep
                import time
                time.sleep(0.05)  # Attendre 50ms pour respecter les limites
        except Exception as e:
            # En cas d'erreur, logger un warning mais continuer
            import logging
            logging.getLogger(__name__).warning(f"Erreur rate limiting: {e}")
    
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
        # CORRECTIF PERF-001: Appliquer rate limiting avant requête
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

            except (
                httpx.TimeoutException,
                httpx.ReadTimeout,
                httpx.ConnectTimeout,
            ) as e:
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
        record_api_call(latency, success=True)

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

            except (
                httpx.TimeoutException,
                httpx.ReadTimeout,
                httpx.ConnectTimeout,
            ) as e:
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
        record_api_call(latency, success=True)

        return data.get("result", {})

    def _should_retry(self, attempt: int, max_attempts: int) -> bool:
        """Détermine si un retry doit être effectué."""
        return attempt < max_attempts

    def _wait_before_retry(self, attempt: int, backoff_base: float):
        """
        Attend avant de retry avec délai de backoff.
        
        CORRECTIF PERF-002: Détection du contexte async pour éviter de bloquer l'event loop.
        """
        delay = self._calculate_retry_delay(attempt, backoff_base)
        
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
        record_api_call(latency, success=False)

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
            delay = self._get_retry_after_delay(
                response, attempt, backoff_base
            )
            
            # CORRECTIF PERF-002: Éviter time.sleep() dans un contexte async
            try:
                import asyncio
                loop = asyncio.get_running_loop()
                # Contexte async détecté - logger et continuer sans sleep
                import logging
                logging.getLogger(__name__).warning(
                    "PERF-002: Rate limit détecté dans un contexte async. "
                    "Délai ignoré pour éviter de bloquer l'event loop."
                )
            except RuntimeError:
                # Contexte synchrone - OK pour time.sleep
                time.sleep(delay)
            
            raise httpx.HTTPStatusError(
                "Rate limited", request=None, response=response
            )

        # Erreurs client (4xx) - pas de retry
        if response.status_code >= 400:
            detail = response.text[:100]
            detail_safe = _sanitize_error_message(detail)
            raise RuntimeError(
                f'Erreur HTTP Bybit: status={response.status_code} '
                f'detail="{detail_safe}"'
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
                "Authentification échouée : clé/secret invalides ou "
                "signature incorrecte"
            )

        # Erreur d'IP non autorisée
        if ret_code == 10018:
            raise RuntimeError(
                "Accès refusé : IP non autorisée "
                "(whitelist requise dans Bybit)"
            )

        # Erreur de timestamp
        if ret_code == 10017:
            raise RuntimeError(
                "Horodatage invalide : horloge locale désynchronisée "
                "(corrige l'heure système)"
            )

        # Rate limit API - retry
        if ret_code == 10016:
            delay = self._get_retry_after_delay(
                response, attempt, backoff_base
            )
            
            # CORRECTIF PERF-002: Éviter time.sleep() dans un contexte async
            try:
                import asyncio
                loop = asyncio.get_running_loop()
                # Contexte async détecté - logger et continuer sans sleep
                import logging
                logging.getLogger(__name__).warning(
                    "PERF-002: API Rate limit (retCode=10016) dans un contexte async. "
                    "Délai ignoré pour éviter de bloquer l'event loop."
                )
            except RuntimeError:
                # Contexte synchrone - OK pour time.sleep
                time.sleep(delay)
            
            if attempt < max_attempts:
                raise httpx.HTTPStatusError(
                    "API Rate limited", request=None, response=response
                )
            raise RuntimeError(
                "Limite de requêtes atteinte : ralentis ou réessaie plus tard"
            )

        # Autre erreur API
        ret_msg_safe = _sanitize_error_message(ret_msg)
        raise RuntimeError(
            f'Erreur API Bybit : retCode={ret_code} retMsg="{ret_msg_safe}"'
        )

    def _get_retry_after_delay(
        self, response: httpx.Response, attempt: int, backoff_base: float
    ) -> float:
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

    def _calculate_retry_delay(
        self, attempt: int, backoff_base: float
    ) -> float:
        """
        Calcule le délai de retry avec backoff exponentiel et jitter aléatoire.
        
        Le backoff exponentiel permet d'espacer progressivement les tentatives
        pour laisser le temps au serveur de se rétablir. Le jitter aléatoire
        évite que plusieurs clients ne se synchronisent sur les mêmes moments.
        
        Algorithme :
        - Délai = backoff_base * (2 ^ (attempt - 1)) + jitter
        - Jitter = nombre aléatoire entre 0 et 0.25 secondes
        
        Exemple avec backoff_base=0.5 :
        - Tentative 1 : 0.5 * 2^0 + jitter = 0.5s + 0-0.25s  = 0.50-0.75s
        - Tentative 2 : 0.5 * 2^1 + jitter = 1.0s + 0-0.25s  = 1.00-1.25s
        - Tentative 3 : 0.5 * 2^2 + jitter = 2.0s + 0-0.25s  = 2.00-2.25s
        - Tentative 4 : 0.5 * 2^3 + jitter = 4.0s + 0-0.25s  = 4.00-4.25s
        - Tentative 5 : 0.5 * 2^4 + jitter = 8.0s + 0-0.25s  = 8.00-8.25s
        
        Pourquoi le jitter ?
        - Évite la "thundering herd" (tous les clients retrying en même temps)
        - Réduit la charge sur le serveur en distribuant les requêtes
        - Améliore les chances de succès en évitant la congestion

        Args:
            attempt (int): Numéro de la tentative actuelle (1, 2, 3, ...)
            backoff_base (float): Délai de base en secondes (ex: 0.5)

        Returns:
            float: Délai à attendre en secondes avant le prochain retry
                  Exemple: 1.12 (pour tentative 2 avec backoff_base=0.5)
                  
        Example:
            ```python
            # Première tentative échouée
            delay = self._calculate_retry_delay(attempt=1, backoff_base=0.5)
            # delay ≈ 0.5-0.75 secondes
            
            time.sleep(delay)  # Attendre avant de retry
            ```
            
        Note:
            - Le délai augmente exponentiellement (doublement à chaque tentative)
            - Le jitter est toujours positif (entre 0 et 0.25s)
            - Pour des tentatives élevées, le délai peut devenir très long
        """
        # Calculer le délai de base avec exponentielle : base * 2^(attempt-1)
        # attempt=1 → 2^0=1, attempt=2 → 2^1=2, attempt=3 → 2^2=4, etc.
        delay = backoff_base * (2 ** (attempt - 1))
        
        # Ajouter un jitter aléatoire entre 0 et 0.25 secondes
        # Cela évite que tous les clients retry exactement au même moment
        delay += random.uniform(0, 0.25)
        
        return delay

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
    
    def get_open_orders(self, category: str = "linear") -> Dict[str, Any]:
        """Récupère les ordres ouverts."""
        return self._get_private("/v5/order/realtime", {"category": category})
    
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
        category: str = "linear"
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
            
        return self._post_private("/v5/order/create", order_data)


class BybitPublicClient(BybitClientInterface):
    """Client public Bybit v5 (aucune clé requise)."""

    def __init__(self, testnet: bool = True, timeout: int = None):
        self.testnet = testnet
        self.timeout = timeout if timeout is not None else TimeoutConfig.DEFAULT

    def public_base_url(self) -> str:
        """Retourne l'URL de base publique (testnet ou mainnet)."""
        from config.urls import URLConfig
        return URLConfig.get_api_url(self.testnet)

    # ===== IMPLÉMENTATION DE BybitClientInterface =====
    
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
        """Indique si le client est authentifié (toujours False pour le client public)."""
        return False

    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Retourne le statut du rate limiting (vide pour le client public)."""
        return {}

    def reset_rate_limit(self) -> None:
        """Remet à zéro le compteur de rate limiting (no-op pour le client public)."""
        pass

    # Méthodes API publiques - implémentations minimales pour l'interface
    def get_tickers(self, category: str = "linear", symbol: Optional[str] = None) -> Dict[str, Any]:
        """Non implémenté - utiliser BybitClient pour les appels API réels."""
        raise NotImplementedError("Utilisez BybitClient pour les appels API réels")

    def get_funding_rate_history(self, category: str = "linear", symbol: Optional[str] = None, limit: int = 200) -> Dict[str, Any]:
        """Non implémenté - utiliser BybitClient pour les appels API réels."""
        raise NotImplementedError("Utilisez BybitClient pour les appels API réels")

    def get_funding_rate(self, symbol: str, category: str = "linear") -> Dict[str, Any]:
        """Non implémenté - utiliser BybitClient pour les appels API réels."""
        raise NotImplementedError("Utilisez BybitClient pour les appels API réels")

    def get_instruments_info(self, category: str = "linear", symbol: Optional[str] = None) -> Dict[str, Any]:
        """Non implémenté - utiliser BybitClient pour les appels API réels."""
        raise NotImplementedError("Utilisez BybitClient pour les appels API réels")

    def get_orderbook(self, category: str = "linear", symbol: str = "BTCUSDT", limit: int = 25) -> Dict[str, Any]:
        """Non implémenté - utiliser BybitClient pour les appels API réels."""
        raise NotImplementedError("Utilisez BybitClient pour les appels API réels")

    def get_kline(self, category: str = "linear", symbol: str = "BTCUSDT", interval: str = "1", limit: int = 200) -> Dict[str, Any]:
        """Non implémenté - utiliser BybitClient pour les appels API réels."""
        raise NotImplementedError("Utilisez BybitClient pour les appels API réels")

    # API privées - non supportées pour le client public
    def get_wallet_balance(self, account_type: str = "UNIFIED") -> Dict[str, Any]:
        """Non supporté - le client public n'a pas accès aux API privées."""
        raise NotImplementedError("Client public - API privées non supportées")

    def get_positions(self, category: str = "linear", settleCoin: str = None) -> Dict[str, Any]:
        """Non supporté - le client public n'a pas accès aux API privées."""
        raise NotImplementedError("Client public - API privées non supportées")

    def get_open_orders(self, category: str = "linear") -> Dict[str, Any]:
        """Non supporté - le client public n'a pas accès aux API privées."""
        raise NotImplementedError("Client public - API privées non supportées")
    
    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str = "Limit",
        qty: str = None,
        price: str = None,
        category: str = "linear"
    ) -> Dict[str, Any]:
        """Non supporté - le client public n'a pas accès aux API privées."""
        raise NotImplementedError("Client public - API privées non supportées")
