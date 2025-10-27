#!/usr/bin/env python3
"""
Authentification HMAC-SHA256 pour le client Bybit.

Ce module gère :
- Génération des signatures HMAC-SHA256
- Construction des headers d'authentification
- Validation des credentials
"""

import time
import hashlib
import hmac


class BybitAuthenticator:
    """
    Gestionnaire d'authentification HMAC-SHA256 pour l'API Bybit v5.
    
    Cette classe gère la signature des requêtes privées selon la spécification
    d'authentification Bybit v5.
    
    Processus d'authentification :
    1. Générer un timestamp en millisecondes
    2. Trier les paramètres par ordre alphabétique
    3. Construire le payload : timestamp + api_key + recv_window + query_string
    4. Signer le payload avec HMAC-SHA256 et le secret API
    5. Ajouter les headers : X-BAPI-API-KEY, X-BAPI-SIGN, X-BAPI-TIMESTAMP, etc.
    """
    
    def __init__(self, api_key: str, api_secret: str):
        """
        Initialise l'authenticator.
        
        Args:
            api_key: Clé API Bybit
            api_secret: Secret API Bybit
            
        Raises:
            ValueError: Si les credentials sont invalides
        """
        self.validate_credentials(api_key, api_secret)
        self.api_key = api_key
        self.api_secret = api_secret
    
    @staticmethod
    def validate_credentials(api_key: str, api_secret: str):
        """
        Valide les credentials (pas de placeholder).
        
        Args:
            api_key: Clé API à valider
            api_secret: Secret API à valider
            
        Raises:
            RuntimeError: Si les clés sont manquantes
            ValueError: Si les clés utilisent des valeurs placeholder
        """
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
    
    def build_auth_headers(self, params: dict, json_data: str = None) -> tuple[dict, str]:
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
            params: Paramètres de la requête à envoyer à l'API
            json_data: Données JSON pour les requêtes POST (optionnel)

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
        timestamp = int(time.time() * 1000)
        
        # Fenêtre de réception : durée pendant laquelle la requête est valide
        recv_window_ms = 10000
        
        # Créer la query string triée par ordre alphabétique des clés
        query_string = "&".join(
            [f"{k}={v}" for k, v in sorted(params.items())]
        )
        
        # Pour les requêtes POST, inclure les données JSON dans la signature
        if json_data:
            payload_data = json_data
        else:
            payload_data = query_string
        
        # Générer la signature HMAC-SHA256 du payload
        signature = self.generate_signature(
            timestamp, recv_window_ms, payload_data
        )
        
        # Construire les headers d'authentification
        headers = {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-SIGN": signature,
            "X-BAPI-SIGN-TYPE": "2",
            "X-BAPI-TIMESTAMP": str(timestamp),
            "X-BAPI-RECV-WINDOW": str(recv_window_ms),
            "Content-Type": "application/json",
        }
        
        return headers, query_string
    
    def generate_signature(
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
            timestamp: Timestamp en millisecondes (epoch time * 1000)
            recv_window_ms: Fenêtre de réception en millisecondes (ex: 10000)
            query_string: Paramètres triés au format "key1=val1&key2=val2"

        Returns:
            str: Signature HMAC-SHA256 en hexadécimal (64 caractères)
                
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
        payload = f"{timestamp}{self.api_key}{recv_window_ms}{query_string}"
        
        # Calculer la signature HMAC-SHA256
        return hmac.new(
            self.api_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

