#!/usr/bin/env python3
"""
🚀 Orchestrateur du bot (filters + WebSocket prix) - VERSION REFACTORISÉE

Script pour filtrer les contrats perpétuels par funding ET suivre leurs prix en temps réel.

Architecture modulaire :
- WatchlistManager : Gestion des filtres et sélection de symboles
- WebSocketManager : Gestion des connexions WebSocket publiques  
- VolatilityTracker : Calcul et cache de volatilité
- DataManager : Gestion des données en temps réel
- DisplayManager : Gestion de l'affichage
- MonitoringManager : Surveillance continue du marché
- BotOrchestrator : Orchestration principale (refactorisée)
- CallbackManager : Gestion des callbacks entre managers
- OpportunityManager : Gestion des opportunités

Usage:
    python src/bot.py
"""

import time
import signal
import atexit
from typing import List, Dict, Optional
from logging_setup import setup_logging
from bot_orchestrator import BotOrchestrator


class PriceTracker:
    """
    Wrapper pour maintenir la compatibilité avec l'ancienne interface.
    
    Cette classe délègue toute la logique au BotOrchestrator refactorisé.
    """
    
    def __init__(self):
        """Initialise le wrapper en créant un BotOrchestrator."""
        self.orchestrator = BotOrchestrator()
        self.logger = self.orchestrator.logger
        self.running = self.orchestrator.running
    
    def start(self):
        """Démarre le bot via l'orchestrateur."""
        self.orchestrator.start()
    
    def _signal_handler(self, signum, frame):
        """Délègue la gestion des signaux à l'orchestrateur."""
        self.orchestrator._signal_handler(signum, frame)
        self.running = self.orchestrator.running


def main():
    """Fonction principale."""
    tracker = PriceTracker()
    
    # Configurer le signal handler AVANT de démarrer
    def signal_handler(signum, frame):
        print("\n🛑 Arrêt demandé par l'utilisateur")
        tracker.running = False
        
        # Essayer d'abord un arrêt propre
        try:
            tracker._signal_handler(signal.SIGINT, None)
            # Attendre un peu pour l'arrêt propre
            import time
            time.sleep(1)
        except:
            pass
        
        # Si l'arrêt propre échoue, forcer l'arrêt
        print("🔄 Arrêt forcé pour libérer le terminal...")
        import os
        os._exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        tracker.start()
        
        # Boucle d'attente pour maintenir le bot actif
        while tracker.running:
            time.sleep(0.1)  # Réduire l'intervalle pour une réponse plus rapide
            
    except KeyboardInterrupt:
        print("\n🛑 Arrêt demandé par l'utilisateur")
        tracker.running = False
    except Exception as e:
        tracker.logger.error(f"❌ Erreur : {e}")
        tracker.running = False
    finally:
        # Arrêt immédiat sans nettoyage
        print("🔄 Arrêt immédiat...")
        import os
        os._exit(0)


if __name__ == "__main__":
    main()
