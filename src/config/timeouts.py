#!/usr/bin/env python3
"""
Configuration centralisée des timeouts pour le bot Bybit.

Ce module centralise tous les timeouts utilisés dans l'application
pour faciliter la maintenance et la testabilité.

╔═══════════════════════════════════════════════════════════════════╗
║                    📖 GUIDE D'UTILISATION                         ║
╚═══════════════════════════════════════════════════════════════════╝

Import :
    from config.timeouts import TimeoutConfig

Utilisation :
    client = BybitClient(timeout=TimeoutConfig.HTTP_REQUEST)
    session = httpx.Client(timeout=TimeoutConfig.DATA_FETCH)
"""

import os


class TimeoutConfig:
    """
    Configuration centralisée des timeouts.
    
    Tous les timeouts sont en secondes.
    Les valeurs peuvent être surchargées via les variables d'environnement.
    """
    
    # ===== TIMEOUTS HTTP =====
    
    # Timeout par défaut pour les requêtes HTTP standard
    DEFAULT = int(os.getenv("TIMEOUT_DEFAULT", "10"))
    
    # Timeout pour les requêtes HTTP génériques
    HTTP_REQUEST = int(os.getenv("TIMEOUT_HTTP_REQUEST", "15"))
    
    # Timeout pour les requêtes de récupération de données
    DATA_FETCH = int(os.getenv("TIMEOUT_DATA_FETCH", "30"))
    
    # Timeout pour les requêtes de spread
    SPREAD_FETCH = int(os.getenv("TIMEOUT_SPREAD_FETCH", "10"))
    
    # Timeout pour les requêtes de funding
    FUNDING_FETCH = int(os.getenv("TIMEOUT_FUNDING_FETCH", "10"))
    
    # Timeout pour les requêtes de volatilité
    VOLATILITY_FETCH = int(os.getenv("TIMEOUT_VOLATILITY_FETCH", "15"))
    
    # Timeout pour les requêtes d'instruments
    INSTRUMENTS_FETCH = int(os.getenv("TIMEOUT_INSTRUMENTS_FETCH", "10"))
    
    # ===== TIMEOUTS WEBSOCKET =====
    
    # Timeout pour les connexions WebSocket
    WEBSOCKET_CONNECT = int(os.getenv("TIMEOUT_WEBSOCKET_CONNECT", "20"))
    
    # Timeout pour les messages WebSocket
    WEBSOCKET_MESSAGE = int(os.getenv("TIMEOUT_WEBSOCKET_MESSAGE", "10"))
    
    # ===== TIMEOUTS OPERATIONS =====
    
    # Timeout pour les opérations de monitoring
    MONITORING_OPERATION = int(os.getenv("TIMEOUT_MONITORING_OPERATION", "5"))
    
    # Timeout pour les opérations de display
    DISPLAY_OPERATION = int(os.getenv("TIMEOUT_DISPLAY_OPERATION", "3"))
    
    # Timeout pour l'arrêt des tâches asynchrones
    ASYNC_TASK_SHUTDOWN = int(os.getenv("TIMEOUT_ASYNC_TASK_SHUTDOWN", "3"))
    
    # Timeout pour l'arrêt des threads
    THREAD_SHUTDOWN = int(os.getenv("TIMEOUT_THREAD_SHUTDOWN", "5"))
    
    @classmethod
    def get_all_timeouts(cls) -> dict:
        """
        Retourne un dictionnaire de tous les timeouts configurés.
        
        Returns:
            dict: Dictionnaire {nom: valeur} de tous les timeouts
        """
        return {
            key: value
            for key, value in cls.__dict__.items()
            if not key.startswith("_") and isinstance(value, int)
        }
    
    @classmethod
    def validate_timeouts(cls) -> bool:
        """
        Valide que tous les timeouts sont des valeurs positives.
        
        Returns:
            bool: True si tous les timeouts sont valides
            
        Raises:
            ValueError: Si un timeout est invalide
        """
        for key, value in cls.get_all_timeouts().items():
            if value <= 0:
                raise ValueError(
                    f"Timeout invalide : {key} = {value}. "
                    f"Les timeouts doivent être positifs."
                )
        return True


class ScanIntervalConfig:
    """
    Configuration centralisée des intervalles de scan.
    
    Tous les intervalles sont en secondes.
    Les valeurs peuvent être surchargées via les variables d'environnement.
    """
    
    # Intervalle de scan du marché pour détecter de nouvelles opportunités
    MARKET_SCAN = int(os.getenv("SCAN_INTERVAL_MARKET", "60"))
    
    # Intervalle de rafraîchissement de la volatilité
    VOLATILITY_REFRESH = int(os.getenv("SCAN_INTERVAL_VOLATILITY", "120"))
    
    # Intervalle de vérification de santé des composants
    HEALTH_CHECK = int(os.getenv("SCAN_INTERVAL_HEALTH_CHECK", "1"))
    
    # Intervalle de monitoring de la mémoire
    MEMORY_MONITORING = int(os.getenv("SCAN_INTERVAL_MEMORY", "60"))
    
    # Intervalle d'affichage des métriques
    METRICS_DISPLAY = int(os.getenv("SCAN_INTERVAL_METRICS", "300"))
    
    @classmethod
    def get_all_intervals(cls) -> dict:
        """
        Retourne un dictionnaire de tous les intervalles configurés.
        
        Returns:
            dict: Dictionnaire {nom: valeur} de tous les intervalles
        """
        return {
            key: value
            for key, value in cls.__dict__.items()
            if not key.startswith("_") and isinstance(value, int)
        }
    
    @classmethod
    def validate_intervals(cls) -> bool:
        """
        Valide que tous les intervalles sont des valeurs positives.
        
        Returns:
            bool: True si tous les intervalles sont valides
            
        Raises:
            ValueError: Si un intervalle est invalide
        """
        for key, value in cls.get_all_intervals().items():
            if value <= 0:
                raise ValueError(
                    f"Intervalle invalide : {key} = {value}. "
                    f"Les intervalles doivent être positifs."
                )
        return True


# Validation au chargement du module (optionnel)
if __name__ != "__main__":
    try:
        TimeoutConfig.validate_timeouts()
        ScanIntervalConfig.validate_intervals()
    except ValueError as e:
        # Log l'erreur mais ne bloque pas l'import
        import logging
        logging.warning(f"⚠️ Configuration timeout/interval invalide : {e}")


# Export pour faciliter l'import
__all__ = ["TimeoutConfig", "ScanIntervalConfig"]

