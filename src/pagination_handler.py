#!/usr/bin/env python3
"""
Gestionnaire de pagination pour le bot Bybit - Version refactorisée.

Cette classe gère uniquement :
- La logique de pagination des requêtes API
- La gestion des curseurs et paramètres
- La détection de fin de pagination
"""

import httpx
from typing import Dict, List, Optional, Any
try:
    from .logging_setup import setup_logging
    from .http_utils import get_rate_limiter
    from .http_client_manager import get_http_client
except ImportError:
    from logging_setup import setup_logging
    from http_utils import get_rate_limiter
    from http_client_manager import get_http_client


class PaginationHandler:
    """
    Gestionnaire de pagination pour le bot Bybit.

    Responsabilités :
    - Gestion de la pagination des requêtes API
    - Gestion des curseurs et paramètres
    - Détection de fin de pagination
    """

    def __init__(self, logger=None):
        """
        Initialise le gestionnaire de pagination.

        Args:
            logger: Logger pour les messages (optionnel)
        """
        self.logger = logger or setup_logging()

    def fetch_paginated_data(
        self,
        base_url: str,
        endpoint: str,
        params: Dict[str, Any],
        timeout: int = 10,
        max_pages: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Récupère toutes les données via pagination.

        Args:
            base_url: URL de base de l'API
            endpoint: Endpoint à appeler (ex: "/v5/market/tickers")
            params: Paramètres de la requête
            timeout: Timeout HTTP
            max_pages: Nombre maximum de pages à récupérer

        Returns:
            Liste de toutes les données récupérées

        Raises:
            RuntimeError: En cas d'erreur HTTP ou API
        """
        all_data = []
        cursor = ""
        page_index = 0
        rate_limiter = get_rate_limiter()

        while page_index < max_pages:
            try:
                # Préparer les paramètres de la page
                page_params = self._prepare_page_params(params, cursor)
                
                # Effectuer la requête
                page_data = self._make_paginated_request(
                    base_url, endpoint, page_params, timeout, page_index + 1, rate_limiter
                )
                
                # Extraire les données de la page
                page_items = page_data.get("list", [])
                if not page_items:
                    break
                
                all_data.extend(page_items)
                
                # Vérifier s'il y a une page suivante
                next_cursor = page_data.get("nextPageCursor")
                if not next_cursor:
                    break
                
                cursor = next_cursor
                page_index += 1
                
            except Exception as e:
                self.logger.error(f"❌ Erreur pagination page {page_index + 1}: {e}")
                raise

        self.logger.debug(
            f"📄 Pagination terminée: {page_index + 1} pages, {len(all_data)} éléments"
        )
        return all_data

    def _prepare_page_params(self, base_params: Dict[str, Any], cursor: str) -> Dict[str, Any]:
        """
        Prépare les paramètres pour une page spécifique.

        Args:
            base_params: Paramètres de base
            cursor: Curseur de pagination

        Returns:
            Paramètres pour la page
        """
        page_params = base_params.copy()
        if cursor:
            page_params["cursor"] = cursor
        else:
            page_params.pop("cursor", None)
        return page_params

    def _make_paginated_request(
        self,
        base_url: str,
        endpoint: str,
        params: Dict[str, Any],
        timeout: int,
        page_index: int,
        rate_limiter,
    ) -> Dict[str, Any]:
        """
        Effectue une requête paginée et retourne le résultat.

        Args:
            base_url: URL de base de l'API
            endpoint: Endpoint à appeler
            params: Paramètres de la requête
            timeout: Timeout HTTP
            page_index: Index de la page (pour les logs)
            rate_limiter: Gestionnaire de rate limiting

        Returns:
            Données de la page

        Raises:
            RuntimeError: En cas d'erreur HTTP ou API
        """
        url = f"{base_url}{endpoint}"
        
        # Respecter le rate limit
        rate_limiter.acquire()
        
        # Effectuer la requête
        client = get_http_client(timeout=timeout)
        response = client.get(url, params=params)

        # Vérifier le statut HTTP
        if response.status_code >= 400:
            self._raise_http_error(url, params, response, page_index)

        # Parser la réponse JSON
        data = response.json()

        # Vérifier le retCode de l'API
        if data.get("retCode") != 0:
            self._raise_api_error(url, params, data, page_index)

        return data.get("result", {})

    def _raise_http_error(self, url: str, params: Dict, response, page_index: int):
        """Lève une erreur HTTP formatée."""
        error_msg = (
            f"Erreur HTTP Bybit GET {url} | "
            f"page={page_index} limit={params.get('limit')} "
            f"cursor={params.get('cursor', '-')} "
            f"status={response.status_code} "
            f'detail="{response.text[:200]}"'
        )
        raise RuntimeError(error_msg)

    def _raise_api_error(self, url: str, params: Dict, data: Dict, page_index: int):
        """Lève une erreur API formatée."""
        ret_code = data.get("retCode")
        ret_msg = data.get("retMsg", "")
        error_msg = (
            f"Erreur API Bybit GET {url} | "
            f"page={page_index} retCode={ret_code} "
            f'retMsg="{ret_msg}"'
        )
        raise RuntimeError(error_msg)

    def should_continue_pagination(
        self, current_data: List, found_items: int, target_items: int
    ) -> bool:
        """
        Détermine si la pagination doit continuer.

        Args:
            current_data: Données de la page actuelle
            found_items: Nombre d'éléments trouvés
            target_items: Nombre d'éléments cibles

        Returns:
            True si la pagination doit continuer
        """
        # Arrêt anticipé si on a trouvé tous les éléments cibles
        if target_items > 0 and found_items >= target_items:
            return False
        
        # Continuer si on a des données
        return len(current_data) > 0
