#!/usr/bin/env python3
"""
Script utilitaire pour fermer manuellement les positions ouvertes.

Ce script permet de fermer toutes les positions ouvertes sur Bybit
en cas de problème avec la fermeture automatique.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from bybit_client import BybitClient
from logging_setup import setup_logging
from config import get_settings

def main():
    """Ferme toutes les positions ouvertes."""
    logger = setup_logging()
    
    try:
        # Récupérer la configuration
        settings = get_settings()
        testnet = settings.get("testnet", True)
        
        # Créer le client Bybit
        client = BybitClient(
            testnet=testnet,
            api_key=settings["api_key"],
            api_secret=settings["api_secret"],
            logger=logger
        )
        
        logger.info("🔍 Recherche des positions ouvertes...")
        
        # Récupérer toutes les positions
        positions_response = client.get_positions(category="linear")
        
        if not positions_response or not positions_response.get("result", {}).get("list"):
            logger.info("✅ Aucune position ouverte trouvée")
            return
        
        positions = positions_response["result"]["list"]
        open_positions = [pos for pos in positions if pos.get("size", "0") != "0" and float(pos.get("size", "0")) > 0]
        
        if not open_positions:
            logger.info("✅ Aucune position ouverte trouvée")
            return
        
        logger.info(f"📊 {len(open_positions)} position(s) ouverte(s) trouvée(s)")
        
        # Fermer chaque position
        for position in open_positions:
            symbol = position.get("symbol")
            side = position.get("side")
            size = position.get("size")
            
            if not symbol or not side or not size:
                continue
            
            logger.info(f"🔄 Fermeture de {symbol} {side} {size}...")
            
            # Déterminer le côté opposé pour fermer
            close_side = "Sell" if side == "Buy" else "Buy"
            
            # Fermer la position (ordre market pour fermeture immédiate)
            close_response = client.place_order(
                symbol=symbol,
                side=close_side,
                order_type="Market",
                qty=size,
                category="linear"
            )
            
            if close_response and close_response.get("orderId"):
                logger.info(f"✅ Position {symbol} fermée - OrderID: {close_response['orderId']}")
            else:
                logger.error(f"❌ Échec fermeture {symbol}: {close_response}")
        
        logger.info("🎉 Fermeture des positions terminée")
        
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
