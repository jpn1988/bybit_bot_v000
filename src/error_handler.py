#!/usr/bin/env python3
"""
Gestionnaire d'erreurs pour le bot Bybit - Version refactorisée.

Cette classe gère uniquement :
- La gestion centralisée des erreurs
- La création de messages d'erreur standardisés
- La classification des types d'erreurs
"""

import httpx
from typing import Dict, Any
try:
    from .logging_setup import setup_logging
except ImportError:
    from logging_setup import setup_logging


class ErrorHandler:
    """
    Gestionnaire d'erreurs pour le bot Bybit.

    Responsabilités :
    - Gestion centralisée des erreurs
    - Création de messages d'erreur standardisés
    - Classification des types d'erreurs
    """

    def __init__(self, logger=None):
        """
        Initialise le gestionnaire d'erreurs.

        Args:
            logger: Logger pour les messages (optionnel)
        """
        self.logger = logger or setup_logging()

    def handle_http_error(
        self,
        url: str,
        params: Dict[str, Any],
        response,
        context: str = "",
    ) -> RuntimeError:
        """
        Gère les erreurs HTTP et retourne une exception formatée.

        Args:
            url: URL de la requête
            params: Paramètres de la requête
            response: Réponse HTTP
            context: Contexte de l'erreur

        Returns:
            RuntimeError formaté
        """
        error_msg = self._create_http_error_message(url, params, response, context)
        return RuntimeError(error_msg)

    def handle_api_error(
        self,
        url: str,
        params: Dict[str, Any],
        data: Dict[str, Any],
        context: str = "",
    ) -> RuntimeError:
        """
        Gère les erreurs API et retourne une exception formatée.

        Args:
            url: URL de la requête
            params: Paramètres de la requête
            data: Données de la réponse
            context: Contexte de l'erreur

        Returns:
            RuntimeError formaté
        """
        error_msg = self._create_api_error_message(url, params, data, context)
        return RuntimeError(error_msg)

    def handle_network_error(
        self,
        url: str,
        params: Dict[str, Any],
        error: Exception,
        context: str = "",
    ) -> RuntimeError:
        """
        Gère les erreurs réseau et retourne une exception formatée.

        Args:
            url: URL de la requête
            params: Paramètres de la requête
            error: Exception réseau
            context: Contexte de l'erreur

        Returns:
            RuntimeError formaté
        """
        error_msg = self._create_network_error_message(url, params, error, context)
        return RuntimeError(error_msg)

    def handle_validation_error(
        self,
        data: Any,
        expected_type: str,
        context: str = "",
    ) -> RuntimeError:
        """
        Gère les erreurs de validation et retourne une exception formatée.

        Args:
            data: Données à valider
            expected_type: Type attendu
            context: Contexte de l'erreur

        Returns:
            RuntimeError formaté
        """
        error_msg = self._create_validation_error_message(data, expected_type, context)
        return RuntimeError(error_msg)

    def _create_http_error_message(
        self,
        url: str,
        params: Dict[str, Any],
        response,
        context: str,
    ) -> str:
        """Crée un message d'erreur HTTP formaté."""
        base_msg = f"Erreur HTTP Bybit GET {url}"

        # Ajouter le contexte si fourni
        if context:
            base_msg += f" | {context}"

        # Ajouter les paramètres importants
        base_msg += f" | limit={params.get('limit', 'N/A')}"
        base_msg += f" | cursor={params.get('cursor', '-')}"
        base_msg += f" | status={response.status_code}"

        # Ajouter un extrait de la réponse
        response_text = response.text[:200] if hasattr(response, 'text') else str(response)
        base_msg += f' | detail="{response_text}"'

        return base_msg

    def _create_api_error_message(
        self,
        url: str,
        params: Dict[str, Any],
        data: Dict[str, Any],
        context: str,
    ) -> str:
        """Crée un message d'erreur API formaté."""
        base_msg = f"Erreur API Bybit GET {url}"

        # Ajouter le contexte si fourni
        if context:
            base_msg += f" | {context}"

        # Ajouter les paramètres importants
        base_msg += f" | limit={params.get('limit', 'N/A')}"
        base_msg += f" | cursor={params.get('cursor', '-')}"

        # Ajouter les codes d'erreur API
        ret_code = data.get("retCode", "N/A")
        ret_msg = data.get("retMsg", "")
        base_msg += f" | retCode={ret_code}"
        base_msg += f' | retMsg="{ret_msg}"'

        return base_msg

    def _create_network_error_message(
        self,
        url: str,
        params: Dict[str, Any],
        error: Exception,
        context: str,
    ) -> str:
        """Crée un message d'erreur réseau formaté."""
        base_msg = f"Erreur réseau Bybit GET {url}"

        # Ajouter le contexte si fourni
        if context:
            base_msg += f" | {context}"

        # Ajouter les paramètres importants
        base_msg += f" | limit={params.get('limit', 'N/A')}"
        base_msg += f" | cursor={params.get('cursor', '-')}"

        # Ajouter le type d'erreur
        error_type = type(error).__name__
        base_msg += f" | error_type={error_type}"
        base_msg += f" | error_msg={str(error)}"

        return base_msg

    def _create_validation_error_message(
        self,
        data: Any,
        expected_type: str,
        context: str,
    ) -> str:
        """Crée un message d'erreur de validation formaté."""
        base_msg = "Erreur validation données"

        # Ajouter le contexte si fourni
        if context:
            base_msg += f" | {context}"

        # Ajouter les informations de validation
        actual_type = type(data).__name__
        base_msg += f" | expected_type={expected_type}"
        base_msg += f" | actual_type={actual_type}"
        base_msg += f" | data={str(data)[:100]}"

        return base_msg

    def log_error(self, error: Exception, context: str = ""):
        """
        Log une erreur avec le contexte approprié.

        Args:
            error: Exception à logger
            context: Contexte de l'erreur
        """
        if isinstance(error, (httpx.RequestError, httpx.TimeoutException, httpx.HTTPStatusError)):
            self.logger.error(f"Erreur réseau {context}: {type(error).__name__}: {error}")
        elif isinstance(error, (ValueError, TypeError, KeyError)):
            self.logger.warning(f"Erreur données {context}: {type(error).__name__}: {error}")
        else:
            self.logger.error(f"Erreur inattendue {context}: {type(error).__name__}: {error}")

    def should_retry(self, error: Exception, attempt: int, max_attempts: int = 3) -> bool:
        """
        Détermine si une opération doit être retentée.

        Args:
            error: Exception rencontrée
            attempt: Numéro de la tentative actuelle
            max_attempts: Nombre maximum de tentatives

        Returns:
            True si l'opération doit être retentée
        """
        if attempt >= max_attempts:
            return False

        # Retry pour les erreurs réseau temporaires
        if isinstance(error, (httpx.TimeoutException, httpx.ConnectError)):
            return True

        # Retry pour les erreurs HTTP 5xx
        if isinstance(error, httpx.HTTPStatusError):
            if hasattr(error, 'response') and error.response.status_code >= 500:
                return True

        return False
