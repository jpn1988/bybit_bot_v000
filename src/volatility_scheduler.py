#!/usr/bin/env python3
"""
Planificateur de volatilité pour le bot Bybit.

Cette classe gère uniquement :
- Le rafraîchissement périodique des données de volatilité
- La gestion des threads de rafraîchissement
- La coordination des cycles de rafraîchissement
"""

import time
import threading
import concurrent.futures
import asyncio
from typing import List, Optional, Callable, Dict
from logging_setup import setup_logging
from volatility import VolatilityCalculator
from volatility_cache import VolatilityCache
from config.timeouts import TimeoutConfig


class VolatilityScheduler:
    """
    Planificateur de volatilité pour le bot Bybit.

    Responsabilités :
    - Rafraîchissement périodique des données de volatilité
    - Gestion des threads de rafraîchissement
    - Coordination des cycles de rafraîchissement
    """

    def __init__(
        self,
        calculator: VolatilityCalculator,
        cache: VolatilityCache,
        logger=None,
    ):
        """
        Initialise le planificateur de volatilité.

        Args:
            calculator: Calculateur de volatilité
            cache: Cache de volatilité
            logger: Logger pour les messages (optionnel)
        """
        self.calculator = calculator
        self.cache = cache
        self.logger = logger or setup_logging()

        # Thread de rafraîchissement
        self._refresh_thread: Optional[threading.Thread] = None
        self._running = False

        # Event loop persistant pour éviter la création/destruction répétée
        self._thread_loop: Optional[asyncio.AbstractEventLoop] = None

        # Callback pour obtenir la liste des symboles actifs
        self._get_active_symbols_callback: Optional[
            Callable[[], List[str]]
        ] = None

        # Journalisation synthétique
        self._summary_interval = 60
        self._last_summary_ts = 0.0

    def set_active_symbols_callback(self, callback: Callable[[], List[str]]):
        """
        Définit le callback pour obtenir la liste des symboles actifs.

        Args:
            callback: Fonction qui retourne la liste des symboles actifs
        """
        self._get_active_symbols_callback = callback

    def start_refresh_task(self):
        """Démarre la tâche de rafraîchissement automatique."""
        if self._refresh_thread and self._refresh_thread.is_alive():
            self.logger.info("[VOLATILITY] ℹ️ Thread volatilité déjà actif")
            return

        self._running = True
        self._refresh_thread = threading.Thread(target=self._refresh_loop)
        self._refresh_thread.daemon = True
        self._refresh_thread.start()

        # Thread volatilité démarré

    def stop_refresh_task(self):
        """
        Arrête la tâche de rafraîchissement de manière plus robuste.

        CORRECTIF : N'attend plus le thread car il peut être bloqué dans
        un calcul de volatilité qui prend 30-45 secondes. Le thread daemon
        sera automatiquement tué par Python lors de la fermeture.
        """
        self._running = False

        # Ne pas faire de join() car le thread peut être bloqué dans
        # un calcul de volatilité long (30-45s avec timeout).
        # Comme c'est un thread daemon, Python le tuera automatiquement.
        # Les vérifications de self._running dans le code empêchent
        # de nouvelles opérations coûteuses.

        if self._refresh_thread and self._refresh_thread.is_alive():
            self.logger.debug("🛑 Thread volatilité marqué pour arrêt (daemon)")

        # Nettoyer la référence du thread
        self._refresh_thread = None
        # Thread volatilité arrêté

    def _refresh_loop(self):
        """Boucle de rafraîchissement périodique du cache de volatilité."""
        refresh_interval = self._calculate_refresh_interval()

        # OPTIMISATION: Créer l'event loop une seule fois pour le thread
        # au lieu de le créer/détruire à chaque calcul de volatilité
        self._thread_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._thread_loop)

        try:
            while self._running:
                try:
                    # CORRECTIF : Vérifier à chaque début de cycle
                    if not self._running:
                        break

                    # Obtenir les symboles à rafraîchir
                    symbols_to_refresh = self._get_symbols_to_refresh()

                    if not symbols_to_refresh:
                        if not self._running:
                            break
                        from config.timeouts import TimeoutConfig
                        time.sleep(TimeoutConfig.VOLATILITY_RETRY_SLEEP)
                        continue

                    # CORRECTIF : Dernière vérification avant le cycle coûteux
                    if not self._running:
                        break

                    # Effectuer le cycle de rafraîchissement
                    self._perform_refresh_cycle(symbols_to_refresh)

                except Exception as e:
                    # CORRECTIF : Ne pas logger les erreurs pendant l'arrêt
                    if self._running:
                        try:
                            self.logger.warning(f"[VOLATILITY] ⚠️ Erreur refresh volatilité: {e}")
                        except (ValueError, RuntimeError):
                            # Logging désactivé, arrêt en cours
                            break
                    else:
                        # Arrêt en cours, ignorer silencieusement
                        break
                    from config.timeouts import TimeoutConfig
                    time.sleep(TimeoutConfig.VOLATILITY_RETRY_SLEEP)

                # Attendre l'intervalle de rafraîchissement avec vérification d'interruption
                self._wait_for_next_cycle(refresh_interval)

        finally:
            # NETTOYAGE: Fermer l'event loop persistant
            if self._thread_loop and not self._thread_loop.is_closed():
                try:
                    self._thread_loop.close()
                except Exception:
                    pass  # Ignorer les erreurs de fermeture
            asyncio.set_event_loop(None)
            self._thread_loop = None

    def _calculate_refresh_interval(self) -> int:
        """
        Calcule l'intervalle de rafraîchissement optimal.

        Returns:
            Intervalle en secondes (entre 30 et 60s)
        """
        return max(
            20, min(40, self.cache.ttl_seconds - 10)
        )  # Intervalle plus court : 20-40s

    def _get_symbols_to_refresh(self) -> List[str]:
        """
        Récupère la liste des symboles actifs à rafraîchir.

        Returns:
            Liste des symboles ou liste vide si erreur
        """
        if not self._get_active_symbols_callback:
            return []

        try:
            return self._get_active_symbols_callback()
        except Exception as e:
            self.logger.warning(f"[VOLATILITY] ⚠️ Erreur callback symboles actifs: {e}")
            return []

    def _perform_refresh_cycle(self, symbols: List[str]):
        """
        Effectue un cycle complet de rafraîchissement de volatilité.

        Args:
            symbols: Liste des symboles à rafraîchir
        """
        # CORRECTIF : Vérifier si on est en train de s'arrêter
        if not self._running:
            return

        # Calculer la volatilité pour tous les symboles
        results = self._run_async_volatility_batch(symbols)

        # Vérifier si on est toujours en cours d'exécution
        if not self._running:
            return

        # Mettre à jour le cache avec les résultats
        now_ts = time.time()
        ok_count, fail_count = self.cache.update_cache_with_results(
            results, now_ts
        )

        # CORRECTIF : Ne logger que si on tourne encore ET que le logging fonctionne
        if self._running:
            try:
                self._log_periodic_summary(len(symbols), ok_count, fail_count)
            except (ValueError, RuntimeError):
                # Logging désactivé ou arrêt en cours, ignorer
                pass

        # Retry pour les symboles en échec
        failed_symbols = [s for s, v in results.items() if v is None]
        if failed_symbols and self._running:
            self._retry_failed_symbols(failed_symbols, now_ts)

        # Nettoyer le cache des symboles non suivis
        if self._running:
            self.cache.clear_stale_cache(symbols)

    def _log_periodic_summary(self, symbol_count: int, ok_count: int, fail_count: int) -> None:
        """Émet un résumé synthétique du rafraîchissement (≤ une fois par minute)."""
        now = time.time()
        if now - self._last_summary_ts < self._summary_interval:
            return

        self._last_summary_ts = now
        self.logger.info(
            f"[VOLATILITY] Summary rafraichis={symbol_count} ok={ok_count} fail={fail_count}"
        )

    def _run_async_volatility_batch(
        self, symbols: List[str]
    ) -> Dict[str, Optional[float]]:
        """
        Exécute le calcul de volatilité en batch en utilisant l'event loop persistant.

        OPTIMISATION: Utilise l'event loop du thread au lieu d'en créer un nouveau
        à chaque calcul, ce qui réduit l'overhead de création/destruction.

        Args:
            symbols: Liste des symboles

        Returns:
            Dictionnaire {symbol: volatility_pct}
        """
        # CORRECTIF : Vérifier si on est en train de s'arrêter
        if not self._running:
            return {symbol: None for symbol in symbols}

        # Vérifier que l'event loop persistant est disponible
        if not self._thread_loop or self._thread_loop.is_closed():
            self.logger.warning("[VOLATILITY] ⚠️ Event loop volatilité non disponible")
            return {symbol: None for symbol in symbols}

        try:
            # OPTIMISATION: Utiliser l'event loop persistant du thread
            return self._thread_loop.run_until_complete(
                self.calculator.compute_volatility_batch(symbols)
            )
        except Exception as e:
            # CORRECTIF : Vérifier si c'est une erreur d'arrêt
            if not self._running:
                return {symbol: None for symbol in symbols}

            error_msg = str(e).lower()
            if "interpreter shutdown" in error_msg or "cannot schedule" in error_msg:
                # Arrêt en cours, ne pas logger
                return {symbol: None for symbol in symbols}

            self.logger.warning(f"[VOLATILITY] ⚠️ Erreur calcul volatilité: {e}")
            return {symbol: None for symbol in symbols}

    def _retry_failed_symbols(
        self, failed_symbols: List[str], timestamp: float
    ):
        """
        Effectue un retry pour les symboles en échec.

        Args:
            failed_symbols: Liste des symboles à retry
            timestamp: Timestamp pour le cache
        """
        # CORRECTIF : Ne pas faire de retry si on est en train de s'arrêter
        if not self._running:
            return

        # Logger avec protection contre l'arrêt
        try:
            self.logger.info(
                f"[VOLATILITY] 🔁 Retry volatilité pour {len(failed_symbols)} symboles…"
            )
        except (ValueError, RuntimeError):
            # Logging désactivé ou arrêt en cours, abandonner le retry
            return

        # Attendre avec vérification d'interruption
        for _ in range(50):  # 5 secondes = 50 * 0.1s
            if not self._running:
                return
            from config.timeouts import TimeoutConfig
            time.sleep(TimeoutConfig.SHORT_SLEEP)

        # Vérifier encore une fois avant le retry
        if not self._running:
            return

        # Retry du calcul
        retry_results = self._run_async_volatility_batch(failed_symbols)

        # Mettre à jour le cache avec les résultats du retry
        retry_ok = 0
        for symbol, vol_pct in retry_results.items():
            if vol_pct is not None:
                self.cache.set_cached_volatility(symbol, vol_pct)
                retry_ok += 1

        # CORRECTIF : Ne logger que si on tourne encore ET que le logging fonctionne
        if self._running:
            try:
                self.logger.info(
                    f"[VOLATILITY] 🔁 Retry volatilité terminé: récupérés={retry_ok}/{len(failed_symbols)}"
                )
            except (ValueError, RuntimeError):
                # Logging désactivé ou arrêt en cours, ignorer
                pass

    def _wait_for_next_cycle(self, interval: int):
        """
        Attend l'intervalle spécifié avec vérification d'interruption.

        Args:
            interval: Intervalle en secondes
        """
        # Vérification très fréquente pour un arrêt plus réactif
        for _ in range(
            interval * 10
        ):  # Vérifier 10 fois par seconde (plus efficace)
            if not self._running:
                break
            from config.timeouts import TimeoutConfig
            time.sleep(TimeoutConfig.SHORT_SLEEP)  # Attendre 100ms entre chaque vérification

    def is_running(self) -> bool:
        """
        Vérifie si le planificateur est en cours d'exécution.

        Returns:
            True si le rafraîchissement est actif
        """
        return (
            self._running
            and self._refresh_thread
            and self._refresh_thread.is_alive()
        )
