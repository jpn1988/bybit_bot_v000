#!/usr/bin/env python3
"""
Spot Availability Checker for Bybit Bot.

This module provides caching functionality to check which perpetual symbols
are also available in spot markets, enabling efficient filtering of the watchlist
to show only symbols that can be hedged.
"""

from typing import Set, List, Optional
from logging_setup import setup_logging


class SpotAvailabilityChecker:
    """
    Checks and caches which perpetual symbols are available in spot markets.

    This class provides efficient O(1) lookup for spot availability by caching
    results at startup, avoiding repeated API calls during runtime.
    """

    def __init__(self, testnet: bool = True, logger=None, bybit_client=None):
        """
        Initialize the spot availability checker.

        Args:
            testnet: Whether to use testnet (True) or mainnet (False)
            logger: Logger instance for messages
            bybit_client: Bybit client for API calls (optional)
        """
        self.testnet = testnet
        self.logger = logger or setup_logging()
        self.bybit_client = bybit_client
        self._spot_available_cache: Set[str] = set()
        self._cache_initialized = False

    def initialize_cache(self, perp_symbols: List, spot_symbols: Set[str]) -> None:
        """
        Initialize the spot availability cache by checking which perp symbols exist in spot.

        Args:
            perp_symbols: List of perpetual instrument dictionaries
            spot_symbols: Set of all available spot symbols
        """
        try:
            self.logger.info(f"🔍 Initialisation du cache spot pour {len(perp_symbols)} symboles perp...")

            # Extract symbol names from perp instrument dictionaries
            perp_symbol_names = []
            for instrument in perp_symbols:
                if isinstance(instrument, dict):
                    symbol = instrument.get('symbol', '')
                    if symbol:
                        perp_symbol_names.append(symbol)
                elif isinstance(instrument, str):
                    perp_symbol_names.append(instrument)

            # Find intersection of perp and spot symbols
            spot_compatible = [s for s in perp_symbol_names if s in spot_symbols]

            # Build cache
            for symbol in spot_compatible:
                self._spot_available_cache.add(symbol)

            self._cache_initialized = True

            self.logger.info(
                f"✅ Cache spot initialisé: {len(spot_compatible)}/{len(perp_symbol_names)} "
                f"symboles perp disponibles en spot"
            )

            if spot_compatible:
                self.logger.debug(f"🔍 Symboles spot-compatibles: {sorted(spot_compatible)[:10]}{'...' if len(spot_compatible) > 10 else ''}")

        except Exception as e:
            self.logger.error(f"❌ Erreur initialisation cache spot: {e}")
            self._cache_initialized = False

    def is_spot_available(self, symbol: str) -> bool:
        """
        Check if a symbol is available in spot (from cache).

        Args:
            symbol: Symbol to check

        Returns:
            True if symbol is available in spot, False otherwise
        """
        if not self._cache_initialized:
            self.logger.warning(f"⚠️ Cache spot non initialisé pour {symbol}")
            return False

        return symbol in self._spot_available_cache

    def get_spot_available_symbols(self) -> Set[str]:
        """
        Get all cached spot-available symbols.

        Returns:
            Set of symbols available in spot
        """
        return self._spot_available_cache.copy()

    def get_cache_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dict with cache statistics
        """
        return {
            "initialized": self._cache_initialized,
            "total_spot_available": len(self._spot_available_cache),
            "testnet": self.testnet
        }
