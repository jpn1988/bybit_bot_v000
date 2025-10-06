#!/usr/bin/env python3
"""
Gestionnaire d'arrêt pour le bot Bybit.

Cette classe gère uniquement :
- L'arrêt propre des managers
- Le nettoyage des ressources
- La gestion des signaux d'arrêt
- Le résumé d'arrêt
"""

import os
import sys
import time
import signal
import asyncio
import threading
import gc
from typing import Optional, Dict, Any
try:
    from .logging_setup import setup_logging, log_shutdown_summary, disable_logging, safe_log_info
except ImportError:
    from logging_setup import setup_logging, log_shutdown_summary, disable_logging, safe_log_info


class ShutdownManager:
    """
    Gestionnaire d'arrêt pour le bot Bybit.
    
    Responsabilités :
    - Arrêt propre des managers
    - Nettoyage des ressources système
    - Gestion des signaux d'arrêt
    - Affichage du résumé d'arrêt
    """
    
    def __init__(self, logger=None):
        """
        Initialise le gestionnaire d'arrêt.
        
        Args:
            logger: Logger pour les messages (optionnel)
        """
        self.logger = logger or setup_logging()
        self.start_time = time.time()
        self._shutdown_in_progress = False
    
    def setup_signal_handler(self, orchestrator):
        """
        Configure le gestionnaire de signal pour Ctrl+C.
        
        Args:
            orchestrator: Instance du BotOrchestrator
        """
        signal.signal(signal.SIGINT, lambda signum, frame: self._signal_handler(orchestrator, signum, frame))
    
    def _signal_handler(self, orchestrator, signum, frame):
        """
        Gestionnaire de signal pour Ctrl+C - Version simplifiée.
        
        Args:
            orchestrator: Instance du BotOrchestrator
            signum: Numéro du signal
            frame: Frame actuel
        """
        # Éviter les appels multiples
        if not orchestrator.running or self._shutdown_in_progress:
            return
            
        # Désactiver le logging pour éviter les reentrant calls
        disable_logging()
        
        # Utiliser safe_log_info pour éviter les reentrant calls
        safe_log_info("🛑 Signal d'arrêt reçu (Ctrl+C)...")
        orchestrator.running = False
        self._shutdown_in_progress = True
        
        # Arrêt simple et direct
        try:
            # Calculer l'uptime
            uptime_seconds = time.time() - self.start_time
            
            # Récupérer les derniers candidats surveillés
            last_candidates = getattr(orchestrator.monitoring_manager, 'candidate_symbols', [])
            
            # Afficher le résumé d'arrêt professionnel
            log_shutdown_summary(self.logger, last_candidates, uptime_seconds)
            
            # Arrêt immédiat du processus - pas de nettoyage complexe
            safe_log_info("✅ Arrêt du bot terminé")
            
            # Forcer l'arrêt immédiat
            os._exit(0)
            
        except Exception as e:
            # Utiliser safe_log_info pour éviter les reentrant calls
            safe_log_info(f"⚠️ Erreur lors de l'arrêt: {e}")
            # Arrêt forcé même en cas d'erreur
            os._exit(0)
    
    async def stop_all_managers_async(self, managers: Dict[str, Any]):
        """
        Arrêt asynchrone de tous les managers.
        
        Args:
            managers: Dictionnaire des managers à arrêter
        """
        managers_to_stop = [
            ("WebSocket", lambda: managers.get('ws_manager').stop() if managers.get('ws_manager') else None),
            ("Display", lambda: managers.get('display_manager').stop_display_loop() if managers.get('display_manager') else None),
            ("Monitoring", lambda: managers.get('monitoring_manager').stop_continuous_monitoring() if managers.get('monitoring_manager') else None),
            ("Volatility", lambda: managers.get('volatility_tracker').stop_refresh_task() if managers.get('volatility_tracker') else None)
        ]
        
        for name, stop_func in managers_to_stop:
            try:
                if stop_func():
                    if asyncio.iscoroutinefunction(stop_func):
                        await stop_func()
                    else:
                        stop_func()
                    self.logger.debug(f"✅ {name} manager arrêté")
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur arrêt {name} manager: {e}")
        
        # Nettoyage des ressources
        self._cleanup_resources(managers)
        
        # Attendre très peu pour que les tâches se terminent
        await asyncio.sleep(0.2)
    
    def stop_all_managers_sync(self, managers: Dict[str, Any]):
        """
        Arrêt synchrone de tous les managers.
        
        Args:
            managers: Dictionnaire des managers à arrêter
        """
        # Arrêt simple sans nettoyage complexe
        try:
            # Juste marquer les managers comme arrêtés
            if managers.get('ws_manager'):
                managers['ws_manager'].running = False
            if managers.get('display_manager'):
                managers['display_manager']._running = False
            if managers.get('monitoring_manager'):
                managers['monitoring_manager']._running = False
            if managers.get('volatility_tracker'):
                managers['volatility_tracker']._running = False
            if managers.get('metrics_monitor'):
                managers['metrics_monitor'].running = False
                
            self.logger.debug("✅ Managers marqués comme arrêtés")
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur arrêt managers: {e}")
    
    def stop_websocket_manager_sync(self, ws_manager):
        """
        Arrête le gestionnaire WebSocket de manière synchrone.
        
        Args:
            ws_manager: Gestionnaire WebSocket à arrêter
        """
        if not ws_manager:
            return
            
        try:
            # WebSocket - arrêt forcé et nettoyage complet
            if hasattr(ws_manager, 'stop_sync'):
                ws_manager.stop_sync()
            else:
                # Arrêt forcé des WebSockets
                ws_manager.running = False
                
            # Nettoyage supplémentaire des WebSockets
            self._close_websocket_connections(ws_manager)
            
            # Attendre un peu pour que l'arrêt se propage
            time.sleep(0.2)
                    
            self.logger.debug("✅ WebSocket manager arrêté")
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur arrêt WebSocket manager: {e}")
    
    def stop_display_manager_sync(self, display_manager):
        """
        Arrête le gestionnaire d'affichage de manière synchrone.
        
        Args:
            display_manager: Gestionnaire d'affichage à arrêter
        """
        if not display_manager:
            return
            
        try:
            # Display - arrêt forcé
            if hasattr(display_manager, 'display_running'):
                display_manager.display_running = False
            self.logger.debug("✅ Display manager arrêté")
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur arrêt Display manager: {e}")
    
    def stop_monitoring_manager_sync(self, monitoring_manager):
        """
        Arrête le gestionnaire de surveillance de manière synchrone.
        
        Args:
            monitoring_manager: Gestionnaire de surveillance à arrêter
        """
        if not monitoring_manager:
            return
            
        try:
            # Monitoring - utiliser la méthode synchrone si disponible
            if hasattr(monitoring_manager, 'stop_monitoring'):
                monitoring_manager.stop_monitoring()
            elif hasattr(monitoring_manager, 'stop_candidate_monitoring'):
                monitoring_manager.stop_candidate_monitoring()
            else:
                # Arrêt forcé
                if hasattr(monitoring_manager, '_running'):
                    monitoring_manager._running = False
            self.logger.debug("✅ Monitoring manager arrêté")
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur arrêt Monitoring manager: {e}")
    
    def stop_volatility_manager_sync(self, volatility_tracker):
        """
        Arrête le gestionnaire de volatilité de manière synchrone.
        
        Args:
            volatility_tracker: Tracker de volatilité à arrêter
        """
        if not volatility_tracker:
            return
            
        try:
            # Volatility - arrêt direct (synchrone)
            volatility_tracker.stop_refresh_task()
            self.logger.debug("✅ Volatility manager arrêté")
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur arrêt Volatility manager: {e}")
    
    def stop_metrics_monitor_sync(self, metrics_monitor):
        """
        Arrête le moniteur de métriques de manière synchrone.
        
        Args:
            metrics_monitor: Moniteur de métriques à arrêter
        """
        if not metrics_monitor:
            return
            
        try:
            # Arrêter le moniteur de métriques
            metrics_monitor.stop()
            self.logger.debug("✅ Metrics monitor arrêté")
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur arrêt Metrics monitor: {e}")
    
    def _close_websocket_connections(self, ws_manager):
        """
        Ferme les connexions WebSocket publiques et privées.
        
        Args:
            ws_manager: Gestionnaire WebSocket
        """
        if hasattr(ws_manager, 'ws_public'):
            try:
                ws_manager.ws_public.close()
            except:
                pass
        if hasattr(ws_manager, 'ws_private'):
            try:
                ws_manager.ws_private.close()
            except:
                pass
    
    def _cleanup_resources(self, managers: Dict[str, Any]):
        """
        Nettoie toutes les ressources pour éviter les fuites mémoire.
        
        Args:
            managers: Dictionnaire des managers à nettoyer
        """
        try:
            # Nettoyer les références des managers de manière plus approfondie
            self._cleanup_managers(managers)
            
            # Nettoyer les références circulaires
            self._break_circular_references(managers)
            
            # Forcer le garbage collection
            self._force_garbage_collection()
            
            self.logger.debug("🧹 Ressources nettoyées avec succès")
            
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur nettoyage ressources: {e}")
    
    def _cleanup_managers(self, managers: Dict[str, Any]):
        """
        Nettoie les managers de manière approfondie.
        
        Args:
            managers: Dictionnaire des managers à nettoyer
        """
        # Nettoyer le data_manager
        data_manager = managers.get('data_manager')
        if data_manager:
            if hasattr(data_manager, 'volatility_cache'):
                data_manager.volatility_cache.clear_all_cache()
            # Nettoyer les références internes
            if hasattr(data_manager, '_linear_symbols'):
                data_manager._linear_symbols.clear()
            if hasattr(data_manager, '_inverse_symbols'):
                data_manager._inverse_symbols.clear()
        
        # Nettoyer le ws_manager
        ws_manager = managers.get('ws_manager')
        if ws_manager:
            ws_manager._ticker_callback = None
            if hasattr(ws_manager, '_ws_conns'):
                ws_manager._ws_conns.clear()
            if hasattr(ws_manager, '_ws_tasks'):
                ws_manager._ws_tasks.clear()
        
        # Nettoyer le monitoring_manager
        monitoring_manager = managers.get('monitoring_manager')
        if monitoring_manager:
            monitoring_manager._on_new_opportunity_callback = None
            monitoring_manager._on_candidate_ticker_callback = None
            if hasattr(monitoring_manager, 'candidate_symbols'):
                monitoring_manager.candidate_symbols.clear()
    
    def _break_circular_references(self, managers: Dict[str, Any]):
        """
        Brise les références circulaires.
        
        Args:
            managers: Dictionnaire des managers
        """
        # Nettoyer les références des composants
        for manager_name in ['display_manager', 'volatility_tracker', 'watchlist_manager', 
                           'callback_manager', 'opportunity_manager']:
            if manager_name in managers and managers[manager_name]:
                managers[manager_name] = None
    
    def _force_garbage_collection(self):
        """
        Force le garbage collection pour libérer la mémoire.
        """
        import gc
        
        # Forcer le garbage collection
        collected = gc.collect()
        if collected > 0:
            self.logger.debug(f"🧹 Garbage collection: {collected} objets libérés")
    
    def cleanup_system_resources(self):
        """
        Nettoie les ressources système (buffers de sortie).
        """
        # Nettoyer les buffers de sortie
        sys.stdout.flush()
        sys.stderr.flush()
    
    def perform_final_cleanup(self, managers: Dict[str, Any]):
        """
        Nettoyage final simplifié.
        
        Args:
            managers: Dictionnaire des managers
        """
        # Nettoyage simple - pas de gestion complexe des threads
        try:
            self.logger.debug("🧹 Nettoyage final simplifié")
            # Juste nettoyer les références principales
            self._cleanup_resources(managers)
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur nettoyage final: {e}")
    
    def force_cleanup_threads(self):
        """
        Nettoyage des threads simplifié.
        """
        # Pas de gestion complexe des threads - laisser le système gérer
        try:
            self.logger.debug("🧹 Nettoyage threads simplifié")
            # Juste forcer le garbage collection
            gc.collect()
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur nettoyage threads: {e}")
    
    def stop_active_threads(self):
        """
        Arrêt des threads simplifié.
        """
        # Pas de gestion complexe des threads
        pass
    
    def force_close_network_connections(self, managers: Dict[str, Any]):
        """
        Force la fermeture de toutes les connexions réseau.
        
        Args:
            managers: Dictionnaire des managers
        """
        try:
            # Fermer les clients HTTP
            if 'http_client_manager' in managers:
                managers['http_client_manager'].close_all()
                self.logger.debug("✅ Clients HTTP fermés")
            
            # Fermer les WebSockets de manière plus agressive
            ws_manager = managers.get('ws_manager')
            if ws_manager:
                # Fermer toutes les connexions WebSocket
                if hasattr(ws_manager, '_ws_conns'):
                    for conn in ws_manager._ws_conns:
                        try:
                            # Arrêt forcé de la WebSocket
                            conn.running = False
                            if hasattr(conn, 'ws') and conn.ws:
                                conn.ws.close()
                                # Forcer la fermeture du socket
                                if hasattr(conn.ws, 'sock') and conn.ws.sock:
                                    conn.ws.sock.close()
                            conn.close()
                        except:
                            pass
                    ws_manager._ws_conns.clear()
                
                # Annuler toutes les tâches WebSocket
                if hasattr(ws_manager, '_ws_tasks'):
                    for task in ws_manager._ws_tasks:
                        try:
                            if not task.done():
                                task.cancel()
                        except:
                            pass
                    ws_manager._ws_tasks.clear()
                
                self.logger.debug("✅ Connexions WebSocket fermées")
            
            # Fermer les connexions de monitoring
            monitoring_manager = managers.get('monitoring_manager')
            if monitoring_manager:
                if hasattr(monitoring_manager, 'candidate_ws_client'):
                    try:
                        monitoring_manager.candidate_ws_client.close()
                    except:
                        pass
                self.logger.debug("✅ Connexions monitoring fermées")
                
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur fermeture connexions réseau: {e}")
