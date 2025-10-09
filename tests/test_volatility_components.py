#!/usr/bin/env python3
"""
Tests pour les composants de volatilité refactorisés.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from async_rate_limiter import AsyncRateLimiter, get_async_rate_limiter
from volatility_computer import VolatilityComputer, get_volatility_cache_key
from volatility_filter import VolatilityFilter
from volatility import VolatilityCalculator, is_cache_valid


class TestAsyncRateLimiter:
    """Tests pour AsyncRateLimiter"""

    def test_init_sets_parameters(self):
        """Test que l'initialisation configure correctement les paramètres"""
        limiter = AsyncRateLimiter(max_calls=10, window_seconds=2.0)
        assert limiter.max_calls == 10
        assert limiter.window_seconds == 2.0

    @pytest.mark.asyncio
    async def test_acquire_allows_calls_within_limit(self):
        """Test que acquire permet les appels dans la limite"""
        limiter = AsyncRateLimiter(max_calls=3, window_seconds=1.0)
        
        # Faire 3 appels rapides (dans la limite)
        await limiter.acquire()
        await limiter.acquire()
        await limiter.acquire()
        
        # Vérifier qu'on a bien 3 appels enregistrés
        assert limiter.get_current_count() == 3

    @pytest.mark.asyncio
    async def test_acquire_blocks_when_limit_exceeded(self):
        """Test que acquire bloque quand la limite est dépassée"""
        limiter = AsyncRateLimiter(max_calls=2, window_seconds=0.5)
        
        start = time.time()
        
        # Faire 2 appels (limite)
        await limiter.acquire()
        await limiter.acquire()
        
        # Le 3e devrait attendre
        await limiter.acquire()
        
        elapsed = time.time() - start
        
        # Devrait avoir attendu au moins un peu (pas exactement 0.5s à cause du polling)
        assert elapsed >= 0.4

    def test_reset_clears_timestamps(self):
        """Test que reset vide l'historique"""
        limiter = AsyncRateLimiter(max_calls=5, window_seconds=1.0)
        limiter._timestamps.append(time.time())
        limiter._timestamps.append(time.time())
        
        assert len(limiter._timestamps) == 2
        
        limiter.reset()
        
        assert len(limiter._timestamps) == 0

    def test_get_current_count_returns_valid_count(self):
        """Test que get_current_count retourne le bon nombre"""
        limiter = AsyncRateLimiter(max_calls=5, window_seconds=1.0)
        
        # Ajouter des timestamps récents
        now = time.time()
        limiter._timestamps.append(now - 0.5)
        limiter._timestamps.append(now - 0.3)
        
        assert limiter.get_current_count() == 2

    def test_get_async_rate_limiter_default_values(self):
        """Test que get_async_rate_limiter utilise les valeurs par défaut"""
        limiter = get_async_rate_limiter()
        assert limiter.max_calls == 5
        assert limiter.window_seconds == 1.0

    def test_get_async_rate_limiter_custom_values(self):
        """Test que get_async_rate_limiter accepte des valeurs custom"""
        limiter = get_async_rate_limiter(max_calls=10, window_seconds=2.0)
        assert limiter.max_calls == 10
        assert limiter.window_seconds == 2.0


class TestVolatilityComputer:
    """Tests pour VolatilityComputer"""

    def test_init_sets_parameters(self):
        """Test que l'initialisation configure correctement les paramètres"""
        computer = VolatilityComputer(timeout=15)
        assert computer.timeout == 15
        assert computer._symbol_categories == {}

    def test_set_symbol_categories(self):
        """Test que set_symbol_categories définit les catégories"""
        computer = VolatilityComputer()
        categories = {"BTCUSDT": "linear", "BTCUSD": "inverse"}
        computer.set_symbol_categories(categories)
        assert computer._symbol_categories == categories

    @pytest.mark.asyncio
    async def test_compute_batch_empty_list(self):
        """Test que compute_batch retourne {} pour une liste vide"""
        computer = VolatilityComputer()
        result = await computer.compute_batch("http://test", [])
        assert result == {}

    def test_calculate_volatility_valid_data(self):
        """Test le calcul de volatilité avec des données valides"""
        computer = VolatilityComputer()
        
        # Créer des klines fictives : [timestamp, open, high, low, close, volume, turnover]
        klines = [
            ["1234567890000", "50000", "51000", "49000", "50500", "100", "5000000"],
            ["1234567880000", "50500", "52000", "50000", "51000", "100", "5000000"],
            ["1234567870000", "51000", "51500", "50500", "51200", "100", "5000000"],
            ["1234567860000", "51200", "51800", "51000", "51500", "100", "5000000"],
            ["1234567850000", "51500", "52000", "51200", "51800", "100", "5000000"],
        ]
        
        result = computer._calculate_volatility(klines)
        
        # Vérifier qu'on a un résultat
        assert result is not None
        assert isinstance(result, float)
        assert result > 0

    def test_calculate_volatility_insufficient_data(self):
        """Test que calculate_volatility retourne None si pas assez de données"""
        computer = VolatilityComputer()
        
        # Seulement 2 klines (moins que le minimum de 3)
        klines = [
            ["1234567890000", "50000", "51000", "49000", "50500", "100", "5000000"],
            ["1234567880000", "50500", "52000", "50000", "51000", "100", "5000000"],
        ]
        
        result = computer._calculate_volatility(klines)
        assert result is None

    def test_get_volatility_cache_key(self):
        """Test que get_volatility_cache_key génère la bonne clé"""
        key = get_volatility_cache_key("BTCUSDT")
        assert key == "volatility_5m_BTCUSDT"


class TestVolatilityFilter:
    """Tests pour VolatilityFilter"""

    def test_init_sets_parameters(self):
        """Test que l'initialisation configure correctement les paramètres"""
        filter_obj = VolatilityFilter()
        assert filter_obj.logger is not None

    def test_filter_symbols_no_filters(self):
        """Test que filter_symbols accepte tous quand pas de filtres"""
        filter_obj = VolatilityFilter()
        
        symbols_data = [
            ("BTCUSDT", 0.0001, 1000000, "1h", 0.001),
            ("ETHUSDT", 0.0002, 2000000, "2h", 0.002),
        ]
        
        volatilities = {
            "BTCUSDT": 0.05,
            "ETHUSDT": 0.10,
        }
        
        result = filter_obj.filter_symbols(
            symbols_data, volatilities, None, None
        )
        
        # Tous les symboles devraient passer
        assert len(result) == 2

    def test_filter_symbols_with_min_filter(self):
        """Test le filtrage avec seuil minimum"""
        filter_obj = VolatilityFilter()
        
        symbols_data = [
            ("BTCUSDT", 0.0001, 1000000, "1h", 0.001),
            ("ETHUSDT", 0.0002, 2000000, "2h", 0.002),
            ("SOLUSDT", 0.0003, 3000000, "3h", 0.003),
        ]
        
        volatilities = {
            "BTCUSDT": 0.03,  # Trop faible
            "ETHUSDT": 0.06,  # OK
            "SOLUSDT": 0.09,  # OK
        }
        
        result = filter_obj.filter_symbols(
            symbols_data, volatilities, volatility_min=0.05, volatility_max=None
        )
        
        # Seulement ETHUSDT et SOLUSDT devraient passer
        assert len(result) == 2
        assert result[0][0] == "ETHUSDT"
        assert result[1][0] == "SOLUSDT"

    def test_filter_symbols_with_max_filter(self):
        """Test le filtrage avec seuil maximum"""
        filter_obj = VolatilityFilter()
        
        symbols_data = [
            ("BTCUSDT", 0.0001, 1000000, "1h", 0.001),
            ("ETHUSDT", 0.0002, 2000000, "2h", 0.002),
        ]
        
        volatilities = {
            "BTCUSDT": 0.03,  # OK
            "ETHUSDT": 0.15,  # Trop élevé
        }
        
        result = filter_obj.filter_symbols(
            symbols_data, volatilities, volatility_min=None, volatility_max=0.10
        )
        
        # Seulement BTCUSDT devrait passer
        assert len(result) == 1
        assert result[0][0] == "BTCUSDT"

    def test_filter_symbols_rejects_none_volatility(self):
        """Test que les symboles sans volatilité sont rejetés si filtres actifs"""
        filter_obj = VolatilityFilter()
        
        symbols_data = [
            ("BTCUSDT", 0.0001, 1000000, "1h", 0.001),
            ("ETHUSDT", 0.0002, 2000000, "2h", 0.002),
        ]
        
        volatilities = {
            "BTCUSDT": 0.05,
            "ETHUSDT": None,  # Pas de volatilité
        }
        
        result = filter_obj.filter_symbols(
            symbols_data, volatilities, volatility_min=0.01, volatility_max=None
        )
        
        # Seulement BTCUSDT devrait passer
        assert len(result) == 1
        assert result[0][0] == "BTCUSDT"

    def test_get_statistics_empty(self):
        """Test que get_statistics gère les données vides"""
        filter_obj = VolatilityFilter()
        
        stats = filter_obj.get_statistics({})
        
        assert stats["count"] == 0
        assert stats["min"] == 0.0
        assert stats["max"] == 0.0
        assert stats["average"] == 0.0

    def test_get_statistics_with_data(self):
        """Test que get_statistics calcule correctement"""
        filter_obj = VolatilityFilter()
        
        volatilities = {
            "BTCUSDT": 0.05,
            "ETHUSDT": 0.10,
            "SOLUSDT": 0.15,
        }
        
        stats = filter_obj.get_statistics(volatilities)
        
        assert stats["count"] == 3
        assert stats["min"] == 0.05
        assert stats["max"] == 0.15
        assert abs(stats["average"] - 0.10) < 0.0001  # Comparaison approximative


class TestVolatilityCalculatorRefactored:
    """Tests pour VolatilityCalculator refactorisé"""

    def test_init_sets_parameters(self):
        """Test que l'initialisation configure correctement les paramètres"""
        calc = VolatilityCalculator(testnet=False, timeout=15)
        assert calc.testnet is False
        assert calc.timeout == 15
        assert calc.computer is not None
        assert calc.filter is not None

    def test_set_symbol_categories_propagates(self):
        """Test que set_symbol_categories propage aux composants"""
        calc = VolatilityCalculator()
        categories = {"BTCUSDT": "linear"}
        
        calc.set_symbol_categories(categories)
        
        assert calc._symbol_categories == categories
        assert calc.computer._symbol_categories == categories

    @pytest.mark.asyncio
    async def test_compute_volatility_batch_empty(self):
        """Test que compute_volatility_batch gère les listes vides"""
        calc = VolatilityCalculator()
        result = await calc.compute_volatility_batch([])
        assert result == {}

    def test_get_statistics_delegates(self):
        """Test que get_statistics délègue au filtre"""
        calc = VolatilityCalculator()
        volatilities = {"BTCUSDT": 0.05}
        
        stats = calc.get_statistics(volatilities)
        
        assert stats["count"] == 1
        assert stats["min"] == 0.05


class TestUtilityFunctions:
    """Tests pour les fonctions utilitaires"""

    def test_is_cache_valid_fresh(self):
        """Test que is_cache_valid retourne True pour un cache frais"""
        timestamp = time.time() - 30  # 30 secondes ago
        assert is_cache_valid(timestamp, ttl_seconds=60) is True

    def test_is_cache_valid_expired(self):
        """Test que is_cache_valid retourne False pour un cache expiré"""
        timestamp = time.time() - 120  # 2 minutes ago
        assert is_cache_valid(timestamp, ttl_seconds=60) is False

    def test_is_cache_valid_custom_ttl(self):
        """Test que is_cache_valid respecte le TTL personnalisé"""
        timestamp = time.time() - 90  # 90 secondes ago
        assert is_cache_valid(timestamp, ttl_seconds=120) is True
        assert is_cache_valid(timestamp, ttl_seconds=60) is False

