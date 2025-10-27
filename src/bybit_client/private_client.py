#!/usr/bin/env python3
"""
Client privé Bybit (authentifié).

Ce module réexporte temporairement la classe BybitClient depuis l'ancien module
pendant la phase de migration. Dans une future itération, la logique sera
refactorisée pour utiliser les helpers créés (auth, error_handler, etc.).
"""

# Import temporaire depuis l'ancien module
import sys
import os

# Ajouter le répertoire parent au path pour importer l'ancien module
parent_dir = os.path.dirname(os.path.dirname(__file__))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Importer la classe complète depuis l'ancien fichier (maintenant .old)
# Note: On importe depuis bybit_client.py qui existe toujours
try:
    # Essayer d'importer depuis le module actuel
    import bybit_client as old_module
    if hasattr(old_module, 'BybitClient'):
        BybitClient = old_module.BybitClient
    else:
        # Fallback: charger directement depuis le fichier .old
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "bybit_client_old",
            os.path.join(parent_dir, "bybit_client.py.old")
        )
        old_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(old_module)
        BybitClient = old_module.BybitClient
except Exception as e:
    raise ImportError(f"Impossible d'importer BybitClient: {e}")

# Exposer la classe
__all__ = ['BybitClient']

