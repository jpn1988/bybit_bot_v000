#!/usr/bin/env python3
"""
Module de calcul de volatilité 5 minutes pour le bot Bybit.

Calcule la volatilité basée sur la plage de prix (high-low) des 5 dernières bougies 1 minute.
"""

import time
import httpx
from typing import Optional


def compute_5m_range_pct(bybit_client, symbol: str) -> Optional[float]:
    """
    Calcule la volatilité 5 minutes basée sur la plage de prix des 5 dernières bougies 1 minute.
    
    Args:
        bybit_client: Instance du client Bybit (pour récupérer l'URL de base)
        symbol (str): Symbole à analyser (ex: "BTCUSDT")
        
    Returns:
        Optional[float]: Volatilité en pourcentage (0.007 = 0.7%) ou None si erreur
    """
    try:
        # Récupérer l'URL de base du client
        base_url = bybit_client.public_base_url()
        
        # Déterminer la catégorie selon le symbole
        category = "linear" if "USDT" in symbol else "inverse"
        
        # Construire l'URL pour récupérer les bougies 1 minute
        url = f"{base_url}/v5/market/kline"
        params = {
            "category": category,
            "symbol": symbol,
            "interval": "1",  # 1 minute
            "limit": 6  # 6 bougies pour avoir 5 minutes + 1 de sécurité
        }
        
        # Faire la requête HTTP
        with httpx.Client(timeout=10) as client:
            response = client.get(url, params=params)
            
            # Vérifier le statut HTTP
            if response.status_code >= 400:
                return None
            
            data = response.json()
            
            # Vérifier le retCode
            if data.get("retCode") != 0:
                return None
            
            result = data.get("result", {})
            klines = result.get("list", [])
            
            # Vérifier qu'on a assez de données
            if len(klines) < 5:
                return None
            
            # Extraire les prix (high et low de chaque bougie)
            # Les bougies sont triées par timestamp décroissant (plus récent en premier)
            prices_high = []
            prices_low = []
            
            for kline in klines[:5]:  # Prendre les 5 plus récentes
                try:
                    high = float(kline[2])  # Index 2 = high
                    low = float(kline[3])   # Index 3 = low
                    prices_high.append(high)
                    prices_low.append(low)
                except (ValueError, TypeError, IndexError):
                    # Ignorer les bougies avec des données invalides
                    continue
            
            # Vérifier qu'on a assez de données valides
            if len(prices_high) < 3:  # Au moins 3 bougies valides
                return None
            
            # Calculer la volatilité
            pmax = max(prices_high)  # Prix maximum sur la période
            pmin = min(prices_low)   # Prix minimum sur la période
            pmid = (pmax + pmin) / 2  # Prix médian
            
            # Éviter la division par zéro
            if pmid <= 0:
                return None
            
            # Calculer la volatilité en pourcentage
            vol_pct = (pmax - pmin) / pmid
            
            return vol_pct
            
    except Exception:
        # En cas d'erreur, retourner None
        return None


def get_volatility_cache_key(symbol: str) -> str:
    """
    Génère une clé de cache pour la volatilité d'un symbole.
    
    Args:
        symbol (str): Symbole
        
    Returns:
        str: Clé de cache
    """
    return f"volatility_5m_{symbol}"


def is_cache_valid(timestamp: float, ttl_seconds: int = 60) -> bool:
    """
    Vérifie si un cache est encore valide.
    
    Args:
        timestamp (float): Timestamp du cache
        ttl_seconds (int): Durée de vie en secondes
        
    Returns:
        bool: True si le cache est valide
    """
    return (time.time() - timestamp) < ttl_seconds
