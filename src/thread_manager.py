#!/usr/bin/env python3
"""
Gestionnaire de threads pour le bot Bybit.

Cette classe gère uniquement :
- L'arrêt forcé des threads récalcitrants
- La gestion des threads asyncio
- Le nettoyage des threads de monitoring
- L'interruption des threads avec ctypes
"""

import os
import sys
import time
import threading
import asyncio
import gc
from typing import Optional, List
try:
    from .logging_setup import setup_logging
except ImportError:
    from logging_setup import setup_logging


class ThreadManager:
    """
    Gestionnaire de threads pour le bot Bybit.
    
    Responsabilités :
    - Arrêt forcé des threads récalcitrants
    - Gestion des threads asyncio
    - Nettoyage des threads de monitoring
    - Interruption des threads avec ctypes
    """
    
    def __init__(self, logger=None):
        """
        Initialise le gestionnaire de threads.
        
        Args:
            logger: Logger pour les messages (optionnel)
        """
        self.logger = logger or setup_logging()
    
    def force_stop_stubborn_threads(self):
        """
        Force l'arrêt des threads qui ne se sont pas arrêtés.
        """
        # Attendre plus longtemps pour que les threads se terminent
        time.sleep(0.5)
        
        # Forcer l'arrêt des threads qui ne se sont pas arrêtés
        for thread in threading.enumerate():
            if thread != threading.current_thread() and thread.is_alive():
                try:
                    # Forcer l'arrêt du thread
                    if hasattr(thread, 'daemon'):
                        thread.daemon = True
                    # Marquer le thread comme arrêté
                    if hasattr(thread, '_running'):
                        thread._running = False
                    if hasattr(thread, 'running'):
                        thread.running = False
                except:
                    pass
        
        # Attendre un peu plus pour que les threads se terminent
        time.sleep(0.2)
        
        # Forcer le nettoyage des ressources système
        try:
            gc.collect()
        except:
            pass
        
        # Nettoyer les buffers de sortie pour libérer le terminal
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except:
            pass
        
        # Forcer l'arrêt de l'event loop asyncio si nécessaire
        self._stop_asyncio_event_loop()
        
        # Si des threads sont encore actifs, essayer un arrêt plus propre
        time.sleep(0.3)
        active_threads = [t for t in threading.enumerate() if t != threading.current_thread() and t.is_alive()]
        if active_threads:
            self.logger.warning(f"⚠️ {len(active_threads)} threads encore actifs, tentative d'arrêt propre...")
            self._stop_active_threads_properly(active_threads)
    
    def _stop_asyncio_event_loop(self):
        """
        Arrête l'event loop asyncio si nécessaire.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                self.logger.warning("⚠️ Event loop asyncio encore actif, arrêt forcé...")
                
                # Annuler toutes les tâches d'abord
                try:
                    tasks = asyncio.all_tasks(loop)
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    
                    # Ne pas essayer d'exécuter des coroutines dans un event loop déjà en cours
                    # Juste annuler les tâches et arrêter l'event loop
                    self.logger.debug(f"✅ {len(tasks)} tâches asyncio annulées")
                    
                except Exception as e:
                    self.logger.warning(f"⚠️ Erreur annulation tâches asyncio: {e}")
                
                # Arrêter l'event loop directement
                try:
                    loop.stop()
                    self.logger.debug("✅ Event loop asyncio arrêté")
                except Exception as e:
                    self.logger.warning(f"⚠️ Erreur arrêt event loop: {e}")
                
                # Attendre un peu pour que l'arrêt se propage
                time.sleep(0.2)
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur arrêt event loop asyncio: {e}")
    
    def _stop_active_threads_properly(self, active_threads: List[threading.Thread]):
        """
        Arrête les threads actifs de manière plus propre.
        
        Args:
            active_threads: Liste des threads actifs
        """
        # Identifier et logger les threads récalcitrants
        for i, thread in enumerate(active_threads):
            self.logger.warning(f"  Thread {i+1}: {thread.name} (daemon={thread.daemon})")
        
        # Essayer d'arrêter les threads de manière plus propre
        for thread in active_threads:
            try:
                if hasattr(thread, 'daemon'):
                    thread.daemon = True
                if hasattr(thread, '_running'):
                    thread._running = False
                if hasattr(thread, 'running'):
                    thread.running = False
            except:
                pass
        
        # Attendre un peu plus pour que les threads se terminent
        time.sleep(0.5)
        
        # Vérifier si des threads sont encore actifs
        remaining_threads = [t for t in threading.enumerate() if t != threading.current_thread() and t.is_alive()]
        if remaining_threads:
            self.logger.warning(f"⚠️ {len(remaining_threads)} threads récalcitrants, tentative d'arrêt forcé...")
            self._stop_threads_aggressively(remaining_threads)
    
    def _stop_threads_aggressively(self, remaining_threads: List[threading.Thread]):
        """
        Arrête les threads de manière plus agressive.
        
        Args:
            remaining_threads: Liste des threads restants
        """
        # Essayer d'arrêter les threads de manière plus agressive
        for thread in remaining_threads:
            try:
                # Traitement spécifique selon le nom du thread
                if 'asyncio' in thread.name:
                    # Thread asyncio - forcer l'arrêt
                    self.logger.warning(f"  Forçage arrêt thread asyncio: {thread.name}")
                    if hasattr(thread, '_stop'):
                        thread._stop()
                    # Forcer l'interruption du thread asyncio
                    self._interrupt_thread(thread, SystemExit)
                elif '_send_ping' in thread.name:
                    # Thread ping WebSocket - arrêter proprement
                    self.logger.warning(f"  Arrêt thread ping WebSocket: {thread.name}")
                    if hasattr(thread, '_running'):
                        thread._running = False
                    # Forcer l'interruption du thread ping
                    self._interrupt_thread(thread, SystemExit)
                elif '_monitor_loop' in thread.name:
                    # Thread monitoring - arrêter proprement
                    self.logger.warning(f"  Arrêt thread monitoring: {thread.name}")
                    if hasattr(thread, '_running'):
                        thread._running = False
                elif '_run_safe_shutdown_loop' in thread.name:
                    # Thread shutdown - arrêter proprement
                    self.logger.warning(f"  Arrêt thread shutdown: {thread.name}")
                    if hasattr(thread, '_running'):
                        thread._running = False
                    # Forcer l'interruption du thread shutdown
                    self._interrupt_thread(thread, SystemExit)
                elif 'loguru' in thread.name:
                    # Thread logging - laisser se terminer naturellement
                    self.logger.warning(f"  Thread logging détecté: {thread.name}")
                
                # Marquer comme arrêté
                if hasattr(thread, '_running'):
                    thread._running = False
                if hasattr(thread, 'running'):
                    thread.running = False
                
                # Essayer de marquer comme daemon seulement si possible
                try:
                    if not thread.is_alive():
                        thread.daemon = True
                except:
                    # Ignorer l'erreur si on ne peut pas modifier le statut daemon
                    pass
            except:
                pass
        
        # Attendre un peu plus
        time.sleep(0.3)
        
        # Vérifier à nouveau
        final_threads = [t for t in threading.enumerate() if t != threading.current_thread() and t.is_alive()]
        if final_threads:
            self.logger.warning(f"⚠️ {len(final_threads)} threads toujours actifs, solution radicale...")
            self._stop_threads_radically(final_threads)
        else:
            self.logger.info("✅ Tous les threads arrêtés après tentative forcée")
    
    def _stop_threads_radically(self, final_threads: List[threading.Thread]):
        """
        Arrête les threads de manière radicale.
        
        Args:
            final_threads: Liste des threads finaux
        """
        # Solution radicale : forcer l'arrêt de tous les threads
        for thread in final_threads:
            try:
                # Forcer l'arrêt radical
                thread.daemon = True
                # Essayer d'interrompre le thread
                if hasattr(thread, '_stop'):
                    thread._stop()
                # Marquer comme arrêté
                if hasattr(thread, '_running'):
                    thread._running = False
                if hasattr(thread, 'running'):
                    thread.running = False
                # Forcer l'arrêt du thread
                if hasattr(thread, '_tstate_lock'):
                    thread._tstate_lock = None
            except:
                pass
        
        # Attendre un peu plus
        time.sleep(0.2)
        
        # Vérifier une dernière fois
        ultimate_threads = [t for t in threading.enumerate() if t != threading.current_thread() and t.is_alive()]
        if ultimate_threads:
            self.logger.warning(f"⚠️ {len(ultimate_threads)} threads ultimes, arrêt forcé du processus")
            self._stop_ultimate_threads(ultimate_threads)
        else:
            self.logger.info("✅ Tous les threads arrêtés après solution radicale")
    
    def _stop_ultimate_threads(self, ultimate_threads: List[threading.Thread]):
        """
        Arrête les threads ultimes avec arrêt forcé du processus.
        
        Args:
            ultimate_threads: Liste des threads ultimes
        """
        # Dernière tentative : forcer l'arrêt de tous les threads
        for thread in ultimate_threads:
            try:
                # Traitement spécifique selon le type de thread
                if 'loguru' in thread.name:
                    # Thread de logging - laisser se terminer naturellement
                    self.logger.debug(f"Thread logging détecté: {thread.name}")
                    continue
                elif 'asyncio' in thread.name:
                    # Thread asyncio - forcer l'interruption
                    self.logger.warning(f"Forçage arrêt thread asyncio: {thread.name}")
                elif '_run_safe_shutdown_loop' in thread.name:
                    # Thread shutdown - forcer l'interruption
                    self.logger.warning(f"Forçage arrêt thread shutdown: {thread.name}")
                else:
                    # Autres threads - forcer l'interruption
                    self.logger.warning(f"Forçage arrêt thread: {thread.name}")
                
                # Essayer de marquer comme daemon seulement si le thread n'est pas encore actif
                try:
                    if not thread.is_alive():
                        thread.daemon = True
                except:
                    # Ignorer l'erreur si on ne peut pas modifier le statut daemon
                    pass
                
                # Forcer l'interruption du thread avec plusieurs méthodes
                self._interrupt_thread(thread, SystemExit)
                self._interrupt_thread(thread, KeyboardInterrupt)
                
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur interruption thread {thread.name}: {e}")
        
        # Attendre un peu pour voir si les threads se terminent
        time.sleep(0.5)
        
        # Vérifier une dernière fois
        final_threads = [t for t in threading.enumerate() if t != threading.current_thread() and t.is_alive()]
        if final_threads:
            self.logger.warning(f"⚠️ {len(final_threads)} threads toujours actifs, arrêt forcé du processus")
            
            # Identifier les threads qui persistent
            for thread in final_threads:
                self.logger.warning(f"  Thread persistant: {thread.name} (daemon={thread.daemon})")
            
            # Arrêt forcé du processus avec plusieurs méthodes
            self._force_process_exit()
        else:
            self.logger.info("✅ Tous les threads arrêtés après solution radicale")
    
    def _interrupt_thread(self, thread: threading.Thread, exception_type):
        """
        Interrompt un thread avec une exception.
        
        Args:
            thread: Thread à interrompre
            exception_type: Type d'exception à lever
        """
        try:
            import ctypes
            ctypes.pythonapi.PyThreadState_SetAsyncExc(
                ctypes.c_long(thread.ident), 
                ctypes.py_object(exception_type)
            )
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur {exception_type.__name__} pour {thread.name}: {e}")
    
    def _force_process_exit(self):
        """
        Force l'arrêt du processus avec plusieurs méthodes.
        """
        try:
            self.logger.warning("⚠️ Arrêt forcé du processus avec os._exit(0)")
            # Forcer l'arrêt immédiat sans nettoyage
            os._exit(0)
        except Exception as e:
            self.logger.error(f"❌ Erreur os._exit: {e}")
            try:
                # Dernière tentative avec sys.exit
                self.logger.warning("⚠️ Arrêt forcé du processus avec sys.exit(0)")
                sys.exit(0)
            except Exception as e2:
                self.logger.error(f"❌ Erreur sys.exit: {e2}")
                # Dernière tentative avec exit()
                try:
                    exit(0)
                except:
                    # Si tout échoue, forcer l'arrêt avec le système
                    import subprocess
                    subprocess.run(['taskkill', '/F', '/PID', str(os.getpid())], shell=True)
    
    def stop_specific_threads(self, managers: dict):
        """
        Arrête spécifiquement les threads connus pour causer des problèmes.
        
        Args:
            managers: Dictionnaire des managers
        """
        try:
            # Arrêter le thread de volatilité de manière plus propre
            volatility_tracker = managers.get('volatility_tracker')
            if volatility_tracker and hasattr(volatility_tracker, 'scheduler'):
                if hasattr(volatility_tracker.scheduler, '_refresh_thread'):
                    thread = volatility_tracker.scheduler._refresh_thread
                    if thread and thread.is_alive():
                        # Arrêt propre d'abord
                        volatility_tracker.stop_refresh_task()
                        # Attendre un peu
                        time.sleep(0.2)
                        # Si toujours actif, forcer l'arrêt
                        if thread.is_alive():
                            thread.daemon = True
                            self.logger.debug("✅ Thread volatilité arrêté proprement")
            
            # Arrêter le thread de monitoring de manière plus propre
            monitoring_manager = managers.get('monitoring_manager')
            if monitoring_manager:
                if hasattr(monitoring_manager, 'stop_continuous_monitoring'):
                    try:
                        monitoring_manager.stop_continuous_monitoring()
                        self.logger.debug("✅ Thread monitoring arrêté proprement")
                    except:
                        pass
                elif hasattr(monitoring_manager, '_candidate_ws_thread'):
                    thread = monitoring_manager._candidate_ws_thread
                    if thread and thread.is_alive():
                        thread.daemon = True
                        self.logger.debug("✅ Thread monitoring forcé à s'arrêter")
            
            # Arrêter le thread de métriques de manière plus propre
            metrics_monitor = managers.get('metrics_monitor')
            if metrics_monitor and hasattr(metrics_monitor, 'monitor_thread'):
                thread = metrics_monitor.monitor_thread
                if thread and thread.is_alive():
                    # Essayer l'arrêt propre d'abord
                    if hasattr(metrics_monitor, 'stop_monitoring'):
                        try:
                            metrics_monitor.stop_monitoring()
                        except:
                            pass
                    # Si toujours actif, forcer l'arrêt
                    if thread.is_alive():
                        thread.daemon = True
                        self.logger.debug("✅ Thread métriques arrêté proprement")
                    
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur arrêt threads spécifiques: {e}")
    
    def stop_all_managers(self, managers: dict):
        """
        Arrête tous les managers avec timeout.
        
        Args:
            managers: Dictionnaire des managers
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
                    stop_func()
                    self.logger.debug(f"✅ {name} manager arrêté")
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur arrêt {name} manager: {e}")
        
        # Attendre que les threads se terminent
        for thread in threading.enumerate():
            if thread != threading.current_thread() and thread.is_alive():
                if hasattr(thread, 'daemon') and thread.daemon:
                    thread.join(timeout=1)
        
        # Attendre un peu pour que les threads se terminent
        time.sleep(0.5)
