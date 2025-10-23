#!/usr/bin/env python3
"""
Gestionnaire de pool de connexions WebSocket.

Ce module gère le ThreadPoolExecutor et le lifecycle des connexions WebSocket
pour éviter la duplication de code et centraliser la gestion des threads.
"""

import asyncio
import concurrent.futures
import threading
import time
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from typing import List, Optional, Callable, Any
from logging_setup import setup_logging
from config.timeouts import TimeoutConfig


class WebSocketConnectionPool:
    """
    Gestionnaire de pool de connexions WebSocket.
    
    Responsabilités :
    - Créer et gérer le ThreadPoolExecutor
    - Exécuter les connexions WebSocket dans des threads
    - Gérer l'arrêt propre avec timeout
    - Surveiller l'état des threads
    """
    
    def __init__(self, logger=None):
        """
        Initialise le pool de connexions.
        
        Args:
            logger: Logger pour les messages
        """
        self.logger = logger or setup_logging()
        self._executor: Optional[concurrent.futures.ThreadPoolExecutor] = None
        self._running = False
        
    def create_executor(self, max_workers: int = 2, thread_name_prefix: str = "ws_executor"):
        """
        Crée un nouveau ThreadPoolExecutor.
        
        Args:
            max_workers: Nombre maximum de threads
            thread_name_prefix: Préfixe des noms de threads
        """
        if self._executor and not self._executor._shutdown:
            self.logger.warning("⚠️ ThreadPoolExecutor déjà créé")
            return
            
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=thread_name_prefix
        )
        self.logger.debug(f"✅ ThreadPoolExecutor créé ({max_workers} workers)")
    
    async def run_websocket_in_thread(self, websocket_func: Callable, *args, **kwargs):
        """
        Exécute une fonction WebSocket dans un thread du pool.
        
        Args:
            websocket_func: Fonction WebSocket à exécuter
            *args: Arguments positionnels
            **kwargs: Arguments nommés
            
        Returns:
            Résultat de l'exécution
        """
        if not self._executor:
            raise RuntimeError("ThreadPoolExecutor non créé")
            
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, websocket_func, *args, **kwargs)
    
    async def shutdown_with_timeout(self, timeout: float = 10.0):
        """
        Arrête le pool avec timeout pour éviter les blocages.
        
        Args:
            timeout: Timeout en secondes
        """
        if not self._executor:
            return
            
        self._running = False
        
        try:
            # Shutdown avec wait=False pour éviter blocage
            self._executor.shutdown(wait=False)
            
            # Trouver et attendre les threads du pool
            ws_threads = [
                t for t in threading.enumerate() 
                if t.name.startswith("ws_executor")
            ]
            
            start_time = time.time()
            
            # Attendre les threads avec timeout global
            for thread in ws_threads:
                remaining = timeout - (time.time() - start_time)
                if remaining <= 0:
                    alive_count = len([t for t in ws_threads if t.is_alive()])
                    self.logger.error(f"⏱️ Timeout global atteint, {alive_count} threads orphelins")
                    break
                    
                thread.join(timeout=remaining)
                if thread.is_alive():
                    self.logger.warning(f"⚠️ Thread {thread.name} ne répond pas, abandonné")
            
            elapsed = time.time() - start_time
            if elapsed < timeout:
                self.logger.debug(f"✅ ThreadPoolExecutor arrêté proprement en {elapsed:.2f}s")
            else:
                self.logger.warning(f"⚠️ Arrêt ThreadPoolExecutor forcé après timeout {timeout}s")
                
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur arrêt executor: {e}")
            # Fallback: shutdown forcé en cas d'erreur
            try:
                self._executor.shutdown(wait=False)
            except Exception:
                pass
        finally:
            self._executor = None
    
    def is_running(self) -> bool:
        """Vérifie si le pool est actif."""
        return self._executor is not None and not self._executor._shutdown
    
    def get_thread_count(self) -> int:
        """Retourne le nombre de threads actifs."""
        if not self._executor:
            return 0
        return len([t for t in threading.enumerate() if t.name.startswith("ws_executor")])
    
    def get_active_threads(self) -> List[threading.Thread]:
        """Retourne la liste des threads actifs du pool."""
        return [t for t in threading.enumerate() if t.name.startswith("ws_executor")]
