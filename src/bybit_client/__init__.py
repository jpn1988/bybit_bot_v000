#!/usr/bin/env python3
"""
Client Bybit pour les opérations synchrones avec authentification privée.

Ce package fournit deux clients :
- BybitClient : Client authentifié pour l'API privée
- BybitPublicClient : Client non authentifié pour l'API publique

Exemple d'utilisation :
    ```python
    from bybit_client import BybitClient

    # Créer le client
    client = BybitClient(
        testnet=True,
        api_key="YOUR_API_KEY",
        api_secret="YOUR_API_SECRET"
    )

    # Récupérer le solde
    balance = client.get_wallet_balance(account_type="UNIFIED")
    ```
"""

# Import de BybitClient depuis private_client.py (refactorisé)
from .private_client import BybitClient

# Importer BybitPublicClient depuis le nouveau module
from .public_client import BybitPublicClient

__all__ = ['BybitClient', 'BybitPublicClient']
