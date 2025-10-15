#!/usr/bin/env python3
"""
Configuration centralisée des URLs pour le bot Bybit.

Ce module centralise toutes les URLs utilisées dans l'application
pour faciliter la maintenance, la testabilité et la configuration.

╔═══════════════════════════════════════════════════════════════════╗
║                    📖 GUIDE D'UTILISATION                         ║
╚═══════════════════════════════════════════════════════════════════╝

Import :
    from config.urls import URLConfig

Utilisation :
    # URLs API
    api_url = URLConfig.get_api_url(testnet=True)
    
    # URLs WebSocket
    ws_url = URLConfig.get_websocket_url(category="linear", testnet=True)
    
    # URLs spécifiques
    funding_url = URLConfig.get_funding_url(testnet=True)
"""

import os
from typing import Dict, Optional


class URLConfig:
    """
    Configuration centralisée des URLs.
    
    Toutes les URLs peuvent être surchargées via les variables d'environnement.
    Les valeurs par défaut correspondent aux URLs officielles de Bybit.
    """
    
    # ===== URLs API BYBIT =====
    
    # URL de base pour l'API testnet
    BYBIT_API_TESTNET = os.getenv("BYBIT_API_TESTNET_URL", "https://api-testnet.bybit.com")
    
    # URL de base pour l'API mainnet
    BYBIT_API_MAINNET = os.getenv("BYBIT_API_MAINNET_URL", "https://api.bybit.com")
    
    # ===== URLs WEBSOCKET BYBIT =====
    
    # URL de base WebSocket testnet
    BYBIT_WS_TESTNET = os.getenv("BYBIT_WS_TESTNET_URL", "wss://stream-testnet.bybit.com")
    
    # URL de base WebSocket mainnet
    BYBIT_WS_MAINNET = os.getenv("BYBIT_WS_MAINNET_URL", "wss://stream.bybit.com")
    
    # ===== ENDPOINTS API =====
    
    # Endpoints pour les données de marché
    ENDPOINT_TICKERS = "/v5/market/tickers"
    ENDPOINT_FUNDING_RATE = "/v5/market/funding/history"
    ENDPOINT_ORDERBOOK = "/v5/market/orderbook"
    ENDPOINT_INSTRUMENTS = "/v5/market/instruments-info"
    ENDPOINT_KLINE = "/v5/market/kline"
    
    # Endpoints pour les données de portefeuille (privé)
    ENDPOINT_WALLET_BALANCE = "/v5/account/wallet-balance"
    ENDPOINT_POSITIONS = "/v5/position/list"
    ENDPOINT_ORDERS = "/v5/order/realtime"
    
    # ===== ENDPOINTS WEBSOCKET =====
    
    # Endpoints WebSocket public
    WS_PUBLIC_LINEAR = "/v5/public/linear"
    WS_PUBLIC_INVERSE = "/v5/public/inverse"
    WS_PUBLIC_SPOT = "/v5/public/spot"
    
    # Endpoints WebSocket privé
    WS_PRIVATE = "/v5/private"
    
    # ===== URLS DE DOCUMENTATION =====
    
    # URLs de documentation Bybit
    DOCS_API = "https://bybit-exchange.github.io/docs/v5/intro"
    DOCS_WEBSOCKET = "https://bybit-exchange.github.io/docs/v5/ws/connect"
    
    # URLs de gestion des clés API
    API_MANAGEMENT_TESTNET = "https://testnet.bybit.com/app/user/api-management"
    API_MANAGEMENT_MAINNET = "https://www.bybit.com/app/user/api-management"
    
    @classmethod
    def get_api_url(cls, testnet: bool = True) -> str:
        """
        Retourne l'URL de base de l'API selon l'environnement.
        
        Args:
            testnet: Utiliser le testnet (True) ou le mainnet (False)
            
        Returns:
            str: URL de base de l'API
        """
        return cls.BYBIT_API_TESTNET if testnet else cls.BYBIT_API_MAINNET
    
    @classmethod
    def get_websocket_url(cls, category: str = "linear", testnet: bool = True) -> str:
        """
        Retourne l'URL WebSocket selon la catégorie et l'environnement.
        
        Args:
            category: Catégorie des symboles ("linear", "inverse", "spot")
            testnet: Utiliser le testnet (True) ou le mainnet (False)
            
        Returns:
            str: URL WebSocket complète
            
        Raises:
            ValueError: Si la catégorie n'est pas supportée
        """
        base_url = cls.BYBIT_WS_TESTNET if testnet else cls.BYBIT_WS_MAINNET
        
        endpoint_map = {
            "linear": cls.WS_PUBLIC_LINEAR,
            "inverse": cls.WS_PUBLIC_INVERSE,
            "spot": cls.WS_PUBLIC_SPOT,
        }
        
        if category not in endpoint_map:
            raise ValueError(
                f"Catégorie WebSocket non supportée : {category}. "
                f"Catégories supportées : {list(endpoint_map.keys())}"
            )
        
        return base_url + endpoint_map[category]
    
    @classmethod
    def get_websocket_private_url(cls, testnet: bool = True) -> str:
        """
        Retourne l'URL WebSocket privé selon l'environnement.
        
        Args:
            testnet: Utiliser le testnet (True) ou le mainnet (False)
            
        Returns:
            str: URL WebSocket privé complète
        """
        base_url = cls.BYBIT_WS_TESTNET if testnet else cls.BYBIT_WS_MAINNET
        return base_url + cls.WS_PRIVATE
    
    @classmethod
    def get_funding_url(cls, testnet: bool = True) -> str:
        """
        Retourne l'URL complète pour les données de funding.
        
        Args:
            testnet: Utiliser le testnet (True) ou le mainnet (False)
            
        Returns:
            str: URL complète pour les données de funding
        """
        return cls.get_api_url(testnet) + cls.ENDPOINT_FUNDING_RATE
    
    @classmethod
    def get_tickers_url(cls, testnet: bool = True) -> str:
        """
        Retourne l'URL complète pour les données de tickers.
        
        Args:
            testnet: Utiliser le testnet (True) ou le mainnet (False)
            
        Returns:
            str: URL complète pour les données de tickers
        """
        return cls.get_api_url(testnet) + cls.ENDPOINT_TICKERS
    
    @classmethod
    def get_instruments_url(cls, testnet: bool = True) -> str:
        """
        Retourne l'URL complète pour les données d'instruments.
        
        Args:
            testnet: Utiliser le testnet (True) ou le mainnet (False)
            
        Returns:
            str: URL complète pour les données d'instruments
        """
        return cls.get_api_url(testnet) + cls.ENDPOINT_INSTRUMENTS
    
    @classmethod
    def get_wallet_balance_url(cls, testnet: bool = True) -> str:
        """
        Retourne l'URL complète pour les données de portefeuille.
        
        Args:
            testnet: Utiliser le testnet (True) ou le mainnet (False)
            
        Returns:
            str: URL complète pour les données de portefeuille
        """
        return cls.get_api_url(testnet) + cls.ENDPOINT_WALLET_BALANCE
    
    @classmethod
    def get_all_urls(cls, testnet: bool = True) -> Dict[str, str]:
        """
        Retourne un dictionnaire de toutes les URLs configurées.
        
        Args:
            testnet: Utiliser le testnet (True) ou le mainnet (False)
            
        Returns:
            Dict[str, str]: Dictionnaire de toutes les URLs
        """
        return {
            "api_base": cls.get_api_url(testnet),
            "ws_linear": cls.get_websocket_url("linear", testnet),
            "ws_inverse": cls.get_websocket_url("inverse", testnet),
            "ws_spot": cls.get_websocket_url("spot", testnet),
            "ws_private": cls.get_websocket_private_url(testnet),
            "funding": cls.get_funding_url(testnet),
            "tickers": cls.get_tickers_url(testnet),
            "instruments": cls.get_instruments_url(testnet),
            "wallet_balance": cls.get_wallet_balance_url(testnet),
        }
    
    @classmethod
    def validate_urls(cls) -> bool:
        """
        Valide que toutes les URLs sont correctement formatées.
        
        Returns:
            bool: True si toutes les URLs sont valides
            
        Raises:
            ValueError: Si une URL est invalide
        """
        import re
        
        # Pattern pour valider les URLs
        url_pattern = re.compile(
            r'^https?://'  # http:// ou https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domaine
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
            r'(?::\d+)?'  # port optionnel
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        ws_pattern = re.compile(
            r'^wss?://'  # ws:// ou wss://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domaine
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
            r'(?::\d+)?'  # port optionnel
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        # Valider les URLs API
        for url in [cls.BYBIT_API_TESTNET, cls.BYBIT_API_MAINNET]:
            if not url_pattern.match(url):
                raise ValueError(f"URL API invalide : {url}")
        
        # Valider les URLs WebSocket
        for url in [cls.BYBIT_WS_TESTNET, cls.BYBIT_WS_MAINNET]:
            if not ws_pattern.match(url):
                raise ValueError(f"URL WebSocket invalide : {url}")
        
        return True


# Validation au chargement du module (optionnel)
if __name__ != "__main__":
    try:
        URLConfig.validate_urls()
    except ValueError as e:
        # Log l'erreur mais ne bloque pas l'import
        import logging
        logging.warning(f"⚠️ Configuration URL invalide : {e}")


# Export pour faciliter l'import
__all__ = ["URLConfig"]
