#!/usr/bin/env python3
"""
Script CLI pour compter les contrats perpétuels disponibles sur Bybit.

Usage:
    python src/run_instruments.py
"""

import sys
from config import get_settings
from logging_setup import setup_logging
from bybit_client import BybitClient
from instruments import get_perp_symbols


def main():
    """Fonction principale du script."""
    # Configuration du logging
    logger = setup_logging()
    
    try:
        # Charger la configuration
        settings = get_settings()
        logger.info("🚀 Lancement du comptage des perp disponibles")
        logger.info(f"📂 Configuration chargée (testnet={settings['testnet']})")
        
        # Créer un client Bybit pour récupérer l'URL publique
        # On utilise des clés factices car on n'a besoin que de l'URL publique
        client = BybitClient(
            testnet=settings["testnet"],
            timeout=settings["timeout"],
            api_key="dummy_key",  # Clé factice pour l'URL publique
            api_secret="dummy_secret"  # Secret factice pour l'URL publique
        )
        
        base_url = client.public_base_url()
        logger.info("🌐 Appel /v5/market/instruments-info pour linear & inverse…")
        
        # Récupérer et compter les perpétuels
        result = get_perp_symbols(base_url, timeout=settings["timeout"])
        
        # Afficher les résultats
        logger.info(f"✅ Perp USDT (linear) trouvés : {len(result['linear'])}")
        logger.info(f"✅ Perp coin-margined (inverse) trouvés : {len(result['inverse'])}")
        logger.info(f"🏁 Total perp disponibles : {result['total']}")
        
        # Exit avec succès
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du comptage des perpétuels : {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
