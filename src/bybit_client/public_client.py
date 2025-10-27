#!/usr/bin/env python3
"""
Client public Bybit (non authentifié).

Ce module fournit un client simple pour l'API publique Bybit
sans nécessiter de clés API.
"""

from typing import Optional, Dict, Any
from config.timeouts import TimeoutConfig
from interfaces.bybit_client_interface import BybitClientInterface


class BybitPublicClient(BybitClientInterface):
    """
    Client public Bybit v5 (aucune clé requise).
    
    Ce client implémente l'interface BybitClientInterface mais
    toutes les méthodes lèvent NotImplementedError car ce client
    est principalement utilisé pour les tests et la compatibilité.
    """
    
    def __init__(self, testnet: bool = True, timeout: int = None):
        """
        Initialise le client public.
        
        Args:
            testnet: Utiliser le testnet (True) ou mainnet (False)
            timeout: Timeout pour les requêtes HTTP en secondes
        """
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
    
    # Méthodes privées (non disponibles pour le client public)
    def get_wallet_balance(self, account_type: str = "UNIFIED") -> Dict[str, Any]:
        """Non implémenté - nécessite authentification."""
        raise NotImplementedError("Méthode privée - nécessite authentification")
    
    def get_positions(self, category: str = "linear", settleCoin: str = None) -> Dict[str, Any]:
        """Non implémenté - nécessite authentification."""
        raise NotImplementedError("Méthode privée - nécessite authentification")
    
    def get_open_orders(self, category: str = "linear") -> Dict[str, Any]:
        """Non implémenté - nécessite authentification."""
        raise NotImplementedError("Méthode privée - nécessite authentification")
    
    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str = "Limit",
        qty: str = None,
        price: str = None,
        category: str = "linear"
    ) -> Dict[str, Any]:
        """Non implémenté - nécessite authentification."""
        raise NotImplementedError("Méthode privée - nécessite authentification")

