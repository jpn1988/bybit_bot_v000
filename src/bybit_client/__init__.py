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

# Import de BybitClient depuis l'ancien module (temporaire)
import sys
import os
import importlib.util

# Obtenir le chemin vers le fichier backup
src_dir = os.path.dirname(os.path.dirname(__file__))
backup_file_path = os.path.join(src_dir, "bybit_client_backup.py")

# Vérifier que le fichier existe
if not os.path.exists(backup_file_path):
    raise ImportError(f"Fichier bybit_client_backup.py introuvable: {backup_file_path}")

# Charger le module depuis le fichier backup
spec = importlib.util.spec_from_file_location("bybit_client_backup", backup_file_path)
if spec is None or spec.loader is None:
    raise ImportError(f"Impossible de charger le module depuis {backup_file_path}")

old_module = importlib.util.module_from_spec(spec)
sys.modules['bybit_client_backup'] = old_module
spec.loader.exec_module(old_module)

# Importer BybitClient depuis l'ancien module
BybitClient = old_module.BybitClient

# Importer BybitPublicClient depuis le nouveau module
from .public_client import BybitPublicClient

__all__ = ['BybitClient', 'BybitPublicClient']
