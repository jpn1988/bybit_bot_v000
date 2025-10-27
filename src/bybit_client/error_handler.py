#!/usr/bin/env python3
"""
Gestion des erreurs pour le client Bybit.

Ce module gère :
- Sanitization des messages d'erreur (masquage credentials)
- Gestion des erreurs HTTP (4xx, 5xx)
- Gestion des erreurs d'authentification
- Gestion des erreurs de rate limiting
- Gestion des erreurs API génériques
"""

import re
import time
import httpx
from typing import Optional


def sanitize_error_message(message: str) -> str:
    """
    Nettoie un message d'erreur pour éviter fuite de credentials.
    
    Filtre :
    - Clés API (format: alphanumeric 20-40 chars)
    - Signatures HMAC (format: hex 64 chars)
    - Tokens JWT (format: xxx.yyy.zzz)
    
    Args:
        message: Message d'erreur à nettoyer
        
    Returns:
        str: Message nettoyé
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


class BybitErrorHandler:
    """
    Gestionnaire d'erreurs pour le client Bybit.
    
    Cette classe gère tous les types d'erreurs possibles :
    - Erreurs HTTP (4xx, 5xx, 429)
    - Erreurs d'authentification (10005, 10006, 10017, 10018)
    - Erreurs de rate limiting (10016)
    - Erreurs API génériques
    """
    
    def __init__(self, logger=None):
        """
        Initialise le gestionnaire d'erreurs.
        
        Args:
            logger: Logger optionnel pour les messages
        """
        self.logger = logger
    
    def handle_http_response(
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
            self.handle_rate_limit_sleep(response, attempt, backoff_base)
            raise httpx.HTTPStatusError(
                "Rate limited", request=None, response=response
            )

        # Erreurs client (4xx) - pas de retry
        if response.status_code >= 400:
            detail = response.text[:100]
            detail_safe = sanitize_error_message(detail)
            raise RuntimeError(
                f'Erreur HTTP Bybit: status={response.status_code} '
                f'detail="{detail_safe}"'
            )
    
    def handle_rate_limit_sleep(
        self,
        response: httpx.Response,
        attempt: int,
        backoff_base: float,
    ):
        """
        Gère le sleep pour rate limiting avec détection async.
        
        Args:
            response: Réponse HTTP
            attempt: Numéro de tentative actuelle
            backoff_base: Délai de base pour le backoff
        """
        delay = self.get_retry_after_delay(response, attempt, backoff_base)
        
        # Éviter time.sleep() dans un contexte async (PERF-002)
        try:
            import asyncio
            loop = asyncio.get_running_loop()
            # Contexte async détecté - logger et continuer sans sleep
            if self.logger:
                self.logger.warning(
                    "PERF-002: Rate limit détecté dans un contexte async. "
                    "Délai ignoré pour éviter de bloquer l'event loop."
                )
        except RuntimeError:
            # Contexte synchrone - OK pour time.sleep
            time.sleep(delay)
    
    def handle_api_response(
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

        # Dispatcher vers les handlers spécialisés
        if ret_code in [10005, 10006, 10018, 10017]:
            self.handle_auth_errors(ret_code)
        elif ret_code == 10016:
            self.handle_rate_limit_error(
                response, attempt, max_attempts, backoff_base
            )
        else:
            self.handle_generic_api_error(ret_code, ret_msg)
    
    def handle_auth_errors(self, ret_code: int):
        """
        Gère les erreurs d'authentification.
        
        Args:
            ret_code: Code d'erreur API
            
        Raises:
            RuntimeError: Erreur d'authentification détaillée
        """
        if ret_code in [10005, 10006]:
            raise RuntimeError(
                "Authentification échouée : clé/secret invalides ou "
                "signature incorrecte"
            )
        elif ret_code == 10018:
            raise RuntimeError(
                "Accès refusé : IP non autorisée "
                "(whitelist requise dans Bybit)"
            )
        elif ret_code == 10017:
            raise RuntimeError(
                "Horodatage invalide : horloge locale désynchronisée "
                "(corrige l'heure système)"
            )
    
    def handle_rate_limit_error(
        self,
        response: httpx.Response,
        attempt: int,
        max_attempts: int,
        backoff_base: float,
    ):
        """
        Gère les erreurs de rate limiting.
        
        Args:
            response: Réponse HTTP
            attempt: Numéro de tentative actuelle
            max_attempts: Nombre maximum de tentatives
            backoff_base: Délai de base pour le backoff
            
        Raises:
            httpx.HTTPStatusError: Pour retry
            RuntimeError: Pour échec final
        """
        delay = self.get_retry_after_delay(response, attempt, backoff_base)
        
        # Éviter time.sleep() dans un contexte async (PERF-002)
        try:
            import asyncio
            loop = asyncio.get_running_loop()
            # Contexte async détecté - logger et continuer sans sleep
            if self.logger:
                self.logger.warning(
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
    
    def handle_generic_api_error(self, ret_code: int, ret_msg: str):
        """
        Gère les erreurs API génériques.
        
        Args:
            ret_code: Code d'erreur API
            ret_msg: Message d'erreur API
            
        Raises:
            RuntimeError: Erreur API générique
        """
        ret_msg_safe = sanitize_error_message(ret_msg)
        raise RuntimeError(
            f'Erreur API Bybit : retCode={ret_code} retMsg="{ret_msg_safe}"'
        )
    
    def get_retry_after_delay(
        self,
        response: httpx.Response,
        attempt: int,
        backoff_base: float,
    ) -> int:
        """
        Calcule le délai avant retry en fonction du header Retry-After.
        
        Args:
            response: Réponse HTTP
            attempt: Numéro de tentative actuelle
            backoff_base: Délai de base pour le backoff
            
        Returns:
            int: Délai en secondes
        """
        # Essayer de lire le header Retry-After
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return int(retry_after)
            except ValueError:
                pass
        
        # Sinon, utiliser le backoff exponentiel
        return self.calculate_retry_delay(attempt, backoff_base)
    
    def calculate_retry_delay(self, attempt: int, backoff_base: float) -> int:
        """
        Calcule le délai de retry avec backoff exponentiel + jitter.
        
        Args:
            attempt: Numéro de tentative actuelle
            backoff_base: Délai de base pour le backoff
            
        Returns:
            int: Délai en secondes
        """
        import random
        
        # Backoff exponentiel : base * 2^(attempt-1)
        delay = backoff_base * (2 ** (attempt - 1))
        
        # Ajouter un jitter (±25%)
        jitter = delay * 0.25 * (2 * random.random() - 1)
        
        return int(delay + jitter)
    
    def prepare_final_error(self, last_error: Optional[Exception]) -> RuntimeError:
        """
        Prépare le message d'erreur final après échec de tous les retries.
        
        Args:
            last_error: Dernière exception capturée
            
        Returns:
            RuntimeError: Exception finale à lever
        """
        if last_error:
            error_msg = str(last_error)
            error_msg_safe = sanitize_error_message(error_msg)
            return RuntimeError(f"Échec après retries : {error_msg_safe}")
        return RuntimeError("Échec après retries : erreur inconnue")

