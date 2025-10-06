#!/usr/bin/env python3
"""
Cache de volatilité pour le bot Bybit.

Cette classe gère uniquement :
- Le stockage temporaire avec TTL (time-to-live)
- Les opérations CRUD sur le cache
- Le nettoyage automatique du cache
"""

import time
from typing import Dict, Tuple, List, Optional
from logging_setup import setup_logging
from volatility import get_volatility_cache_key, is_cache_valid


class VolatilityCache:
    """
    Cache de volatilité pour le bot Bybit.

    Responsabilités :
    - Stockage temporaire avec TTL pour les données de volatilité
    - Opérations CRUD sur le cache
    - Nettoyage automatique du cache
    """

    def __init__(self, ttl_seconds: int = 120, max_cache_size: int = 1000, logger=None):
        """
        Initialise le cache de volatilité.

        Args:
            ttl_seconds (int): Durée de vie du cache en secondes
            max_cache_size (int): Taille maximale du cache
            logger: Logger pour les messages (optionnel)
        """
        self.ttl_seconds = ttl_seconds
        self.max_cache_size = max_cache_size
        self.logger = logger or setup_logging()

        # Cache de volatilité {cache_key: (timestamp, volatility_pct)}
        self.volatility_cache: Dict[str, Tuple[float, float]] = {}

        # Nettoyage automatique
        self._last_cleanup = time.time()
        self._cleanup_interval = 60  # Nettoyer toutes les minutes
        self._auto_cleanup_enabled = True

    def get_cached_volatility(self, symbol: str) -> Optional[float]:
        """
        Récupère la volatilité en cache pour un symbole.

        Args:
            symbol: Symbole à rechercher

        Returns:
            Volatilité en pourcentage ou None si absent/expiré
        """
        # Nettoyage automatique périodique
        self._auto_cleanup_if_needed()

        cache_key = get_volatility_cache_key(symbol)
        cached_data = self.volatility_cache.get(cache_key)

        if cached_data and is_cache_valid(cached_data[0], ttl_seconds=self.ttl_seconds):
            return cached_data[1]

        return None

    def set_cached_volatility(self, symbol: str, volatility_pct: float):
        """
        Met à jour le cache de volatilité pour un symbole.

        Args:
            symbol: Symbole
            volatility_pct: Volatilité en pourcentage
        """
        cache_key = get_volatility_cache_key(symbol)
        self.volatility_cache[cache_key] = (time.time(), volatility_pct)

        # Nettoyer le cache si nécessaire
        if len(self.volatility_cache) > self.max_cache_size:
            self._cleanup_cache()

    def clear_stale_cache(self, active_symbols: List[str]):
        """
        Nettoie le cache des symboles non actifs.

        Args:
            active_symbols: Liste des symboles actifs
        """
        try:
            active_set = set(active_symbols)
            stale_keys = []

            for cache_key in list(self.volatility_cache.keys()):
                # Extraire le symbole du cache_key (format: "volatility_5m_SYMBOL")
                symbol = cache_key.split("volatility_5m_")[-1]
                if symbol not in active_set:
                    stale_keys.append(cache_key)

            for key in stale_keys:
                self.volatility_cache.pop(key, None)

            if stale_keys:
                self.logger.debug(f"🧹 Cache volatilité nettoyé: {len(stale_keys)} entrées supprimées")

        except Exception as e:
            self.logger.warning(f"⚠️ Erreur nettoyage cache volatilité: {e}")

    def _cleanup_cache(self):
        """Nettoie le cache en supprimant les entrées les plus anciennes."""
        try:
            if len(self.volatility_cache) <= self.max_cache_size:
                return

            # Trier par timestamp et garder les plus récents
            sorted_items = sorted(self.volatility_cache.items(), key=lambda x: x[1][0], reverse=True)
            items_to_keep = sorted_items[:self.max_cache_size]

            # Reconstruire le cache
            self.volatility_cache = dict(items_to_keep)

            removed_count = len(sorted_items) - len(items_to_keep)
            if removed_count > 0:
                self.logger.debug(f"🧹 Cache volatilité nettoyé: {removed_count} entrées supprimées")

        except Exception as e:
            self.logger.warning(f"⚠️ Erreur nettoyage cache volatilité: {e}")

    def update_cache_with_results(self, results: Dict[str, Optional[float]], timestamp: float) -> Tuple[int, int]:
        """
        Met à jour le cache de volatilité avec les résultats.

        Args:
            results: Résultats du calcul de volatilité
            timestamp: Timestamp pour le cache

        Returns:
            Tuple (ok_count, fail_count)
        """
        ok_count = 0
        fail_count = 0

        for symbol, vol_pct in results.items():
            if vol_pct is not None:
                self.set_cached_volatility(symbol, vol_pct)
                ok_count += 1
            else:
                fail_count += 1

        return ok_count, fail_count

    def get_cache_stats(self) -> Dict[str, int]:
        """
        Retourne les statistiques du cache.

        Returns:
            Dictionnaire avec les stats du cache
        """
        time.time()
        total = len(self.volatility_cache)
        valid = sum(1 for timestamp, _ in self.volatility_cache.values()
                   if is_cache_valid(timestamp, self.ttl_seconds))
        expired = total - valid

        return {
            "total": total,
            "valid": valid,
            "expired": expired
        }

    def clear_all_cache(self):
        """Vide complètement le cache."""
        self.volatility_cache.clear()
        self.logger.debug("🧹 Cache volatilité vidé complètement")

    def _auto_cleanup_if_needed(self):
        """
        Effectue un nettoyage automatique si nécessaire.
        """
        if not self._auto_cleanup_enabled:
            return

        now = time.time()
        if now - self._last_cleanup >= self._cleanup_interval:
            self._cleanup_expired_entries()
            self._last_cleanup = now

    def _cleanup_expired_entries(self):
        """
        Nettoie les entrées expirées du cache.
        """
        try:
            time.time()
            expired_keys = []

            for cache_key, (timestamp, _) in self.volatility_cache.items():
                if not is_cache_valid(timestamp, self.ttl_seconds):
                    expired_keys.append(cache_key)

            # Supprimer les entrées expirées
            for key in expired_keys:
                self.volatility_cache.pop(key, None)

            if expired_keys:
                self.logger.debug(f"🧹 Cache volatilité nettoyé automatiquement: {len(expired_keys)} entrées expirées supprimées")

        except Exception as e:
            self.logger.warning(f"⚠️ Erreur nettoyage automatique cache volatilité: {e}")

    def enable_auto_cleanup(self, enabled: bool = True):
        """
        Active ou désactive le nettoyage automatique.

        Args:
            enabled: True pour activer, False pour désactiver
        """
        self._auto_cleanup_enabled = enabled
        if enabled:
            self.logger.debug("🧹 Nettoyage automatique du cache activé")
        else:
            self.logger.debug("🧹 Nettoyage automatique du cache désactivé")
