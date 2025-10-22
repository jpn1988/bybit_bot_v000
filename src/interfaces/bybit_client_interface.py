#!/usr/bin/env python3
"""
Interface pour BybitClient - Contrat pour les clients API Bybit.

Cette interface définit le contrat que doivent respecter tous les clients
API Bybit, permettant une meilleure testabilité et une architecture flexible.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any


class BybitClientInterface(ABC):
    """
    Interface pour les clients API Bybit.
    
    Cette interface définit les méthodes que doit implémenter tout client
    API Bybit, permettant de facilement créer des mocks pour les tests.
    """
    
    @abstractmethod
    def get_tickers(self, category: str = "linear", symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Récupère les données de tickers.
        
        Args:
            category: Catégorie des symboles ("linear", "inverse", "spot")
            symbol: Symbole spécifique (optionnel)
            
        Returns:
            Dict contenant les données de tickers
            
        Raises:
            Exception: En cas d'erreur API
        """
        pass
    
    @abstractmethod
    def get_funding_rate_history(
        self, 
        category: str = "linear", 
        symbol: Optional[str] = None,
        limit: int = 200
    ) -> Dict[str, Any]:
        """
        Récupère l'historique des taux de funding.
        
        Args:
            category: Catégorie des symboles ("linear", "inverse")
            symbol: Symbole spécifique (optionnel)
            limit: Nombre maximum d'entrées à récupérer
            
        Returns:
            Dict contenant l'historique des taux de funding
            
        Raises:
            Exception: En cas d'erreur API
        """
        pass
    
    @abstractmethod
    def get_instruments_info(
        self, 
        category: str = "linear", 
        symbol: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Récupère les informations sur les instruments.
        
        Args:
            category: Catégorie des symboles ("linear", "inverse", "spot")
            symbol: Symbole spécifique (optionnel)
            
        Returns:
            Dict contenant les informations sur les instruments
            
        Raises:
            Exception: En cas d'erreur API
        """
        pass
    
    @abstractmethod
    def get_orderbook(
        self, 
        category: str = "linear", 
        symbol: str = "BTCUSDT",
        limit: int = 25
    ) -> Dict[str, Any]:
        """
        Récupère le carnet d'ordres.
        
        Args:
            category: Catégorie des symboles ("linear", "inverse", "spot")
            symbol: Symbole pour lequel récupérer le carnet d'ordres
            limit: Nombre maximum d'ordres par côté
            
        Returns:
            Dict contenant le carnet d'ordres
            
        Raises:
            Exception: En cas d'erreur API
        """
        pass
    
    @abstractmethod
    def get_kline(
        self,
        category: str = "linear",
        symbol: str = "BTCUSDT",
        interval: str = "1",
        limit: int = 200
    ) -> Dict[str, Any]:
        """
        Récupère les données de chandeliers (kline).
        
        Args:
            category: Catégorie des symboles ("linear", "inverse", "spot")
            symbol: Symbole pour lequel récupérer les données
            interval: Intervalle de temps ("1", "3", "5", "15", "30", "60", "120", "240", "360", "720", "D", "W", "M")
            limit: Nombre maximum de chandeliers
            
        Returns:
            Dict contenant les données de chandeliers
            
        Raises:
            Exception: En cas d'erreur API
        """
        pass
    
    @abstractmethod
    def get_wallet_balance(self, account_type: str = "UNIFIED") -> Dict[str, Any]:
        """
        Récupère le solde du portefeuille (API privée).
        
        Args:
            account_type: Type de compte ("UNIFIED", "CONTRACT", "SPOT")
            
        Returns:
            Dict contenant le solde du portefeuille
            
        Raises:
            Exception: En cas d'erreur API ou d'authentification
        """
        pass
    
    @abstractmethod
    def get_positions(self, category: str = "linear") -> Dict[str, Any]:
        """
        Récupère les positions ouvertes (API privée).
        
        Args:
            category: Catégorie des symboles ("linear", "inverse", "spot")
            
        Returns:
            Dict contenant les positions ouvertes
            
        Raises:
            Exception: En cas d'erreur API ou d'authentification
        """
        pass
    
    @abstractmethod
    def get_open_orders(self, category: str = "linear") -> Dict[str, Any]:
        """
        Récupère les ordres ouverts (API privée).
        
        Args:
            category: Catégorie des symboles ("linear", "inverse", "spot")
            
        Returns:
            Dict contenant les ordres ouverts
            
        Raises:
            Exception: En cas d'erreur API ou d'authentification
        """
        pass
    
    @abstractmethod
    def public_base_url(self) -> str:
        """
        Retourne l'URL de base publique.
        
        Returns:
            str: URL de base publique (testnet ou mainnet)
        """
        pass
    
    @abstractmethod
    def is_testnet(self) -> bool:
        """
        Indique si le client utilise le testnet.
        
        Returns:
            bool: True si testnet, False si mainnet
        """
        pass
    
    @abstractmethod
    def get_timeout(self) -> int:
        """
        Retourne le timeout configuré.
        
        Returns:
            int: Timeout en secondes
        """
        pass
    
    @abstractmethod
    def set_timeout(self, timeout: int) -> None:
        """
        Définit le timeout.
        
        Args:
            timeout: Timeout en secondes
        """
        pass
    
    @abstractmethod
    def is_authenticated(self) -> bool:
        """
        Indique si le client est authentifié pour les API privées.
        
        Returns:
            bool: True si authentifié, False sinon
        """
        pass
    
    @abstractmethod
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """
        Retourne le statut du rate limiting.
        
        Returns:
            Dict contenant les informations de rate limiting
        """
        pass
    
    @abstractmethod
    def reset_rate_limit(self) -> None:
        """
        Remet à zéro le compteur de rate limiting.
        """
        pass
    
    @abstractmethod
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
        Place un ordre sur Bybit (API privée).
        
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
            Exception: En cas d'erreur API ou d'authentification
        """
        pass