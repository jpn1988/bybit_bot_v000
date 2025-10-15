#!/usr/bin/env python3
"""
Tests pour CircuitBreaker (circuit_breaker.py)

Couvre:
- États du circuit (CLOSED, OPEN, HALF_OPEN)
- Transitions d'états et mécanismes
- Gestion des succès et échecs
- Thread safety
- Statistiques et monitoring
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch
from circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerOpen


class TestCircuitBreakerInitialization:
    """Tests d'initialisation du Circuit Breaker."""

    def test_init_default_parameters(self):
        """Test initialisation avec paramètres par défaut."""
        cb = CircuitBreaker()
        
        assert cb.failure_threshold == 5
        assert cb.timeout_seconds == 60
        assert cb.name == "CircuitBreaker"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.last_failure_time is None
        assert cb.logger is not None

    def test_init_custom_parameters(self):
        """Test initialisation avec paramètres personnalisés."""
        mock_logger = Mock()
        cb = CircuitBreaker(
            failure_threshold=3,
            timeout_seconds=30,
            name="TestAPI",
            logger=mock_logger
        )
        
        assert cb.failure_threshold == 3
        assert cb.timeout_seconds == 30
        assert cb.name == "TestAPI"
        assert cb.logger is mock_logger
        assert cb.state == CircuitState.CLOSED

    def test_init_logs_initialization(self):
        """Test que l'initialisation est loggée."""
        with patch('circuit_breaker.setup_logging') as mock_setup:
            mock_logger = Mock()
            mock_setup.return_value = mock_logger
            
            CircuitBreaker(name="TestLogger", failure_threshold=2, timeout_seconds=15)
            
            mock_logger.debug.assert_called_once()
            call_args = mock_logger.debug.call_args[0][0]
            assert "TestLogger" in call_args
            assert "seuil=2" in call_args
            assert "timeout=15s" in call_args


class TestCircuitBreakerStates:
    """Tests des états du Circuit Breaker."""

    def test_initial_state_is_closed(self):
        """Test que l'état initial est CLOSED."""
        cb = CircuitBreaker()
        assert cb.get_state() == CircuitState.CLOSED
        assert cb.state == CircuitState.CLOSED

    def test_get_state_thread_safe(self):
        """Test que get_state est thread-safe."""
        cb = CircuitBreaker()
        
        # Tester l'accès concurrent à get_state
        results = []
        
        def get_state():
            results.append(cb.get_state())
        
        threads = [threading.Thread(target=get_state) for _ in range(10)]
        
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        
        # Tous les résultats doivent être CLOSED
        assert all(state == CircuitState.CLOSED for state in results)
        assert len(results) == 10


class TestCircuitBreakerCallSuccess:
    """Tests pour les appels réussis."""

    def test_call_successful_function(self):
        """Test appel d'une fonction qui réussit."""
        cb = CircuitBreaker()
        
        def successful_func():
            return "success"
        
        result = cb.call(successful_func)
        
        assert result == "success"
        assert cb.get_state() == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_call_with_args_and_kwargs(self):
        """Test appel avec arguments et keyword arguments."""
        cb = CircuitBreaker()
        
        def func_with_params(x, y, z=None):
            return x + y + (z or 0)
        
        result = cb.call(func_with_params, 1, 2, z=3)
        assert result == 6

    def test_call_resets_failure_count_after_success(self):
        """Test que les succès réinitialisent le compteur d'échecs."""
        cb = CircuitBreaker(failure_threshold=2)
        
        def failing_func():
            raise RuntimeError("Test error")
        
        def success_func():
            return "success"
        
        # Provoquer un échec
        try:
            cb.call(failing_func)
        except RuntimeError:
            pass
        
        # Vérifier que le compteur d'échecs a été incrémenté
        assert cb.failure_count == 1
        
        # Appel réussi - doit réinitialiser le compteur
        result = cb.call(success_func)
        
        assert result == "success"
        assert cb.failure_count == 0


class TestCircuitBreakerCallFailure:
    """Tests pour les appels qui échouent."""

    def test_call_failing_function(self):
        """Test appel d'une fonction qui échoue."""
        cb = CircuitBreaker(failure_threshold=2)
        
        def failing_func():
            raise ValueError("Test error")
        
        # Premier échec
        with pytest.raises(ValueError, match="Test error"):
            cb.call(failing_func)
        
        assert cb.failure_count == 1
        assert cb.get_state() == CircuitState.CLOSED
        
        # Deuxième échec - seuil atteint, circuit ouvert
        with pytest.raises(ValueError, match="Test error"):
            cb.call(failing_func)
        
        assert cb.failure_count == 2
        assert cb.get_state() == CircuitState.OPEN

    def test_circuit_opens_after_threshold_failures(self):
        """Test ouverture du circuit après le seuil d'échecs."""
        cb = CircuitBreaker(failure_threshold=3)
        
        def failing_func():
            raise ConnectionError("Connection failed")
        
        # 3 échecs pour atteindre le seuil
        for i in range(3):
            with pytest.raises(ConnectionError):
                cb.call(failing_func)
            
            if i < 2:  # Les deux premiers échecs
                assert cb.get_state() == CircuitState.CLOSED
            else:  # Le troisième échec
                assert cb.get_state() == CircuitState.OPEN

    def test_open_circuit_blocks_calls(self):
        """Test que le circuit ouvert bloque les appels."""
        cb = CircuitBreaker(failure_threshold=1)
        
        def failing_func():
            raise Exception("Always fails")
        
        # Provoquer l'ouverture du circuit
        with pytest.raises(Exception):
            cb.call(failing_func)
        
        assert cb.get_state() == CircuitState.OPEN
        
        # Tenter un appel - doit être bloqué
        with pytest.raises(CircuitBreakerOpen) as exc_info:
            cb.call(failing_func)
        
        assert "Circuit Breaker" in str(exc_info.value)
        assert "indisponible" in str(exc_info.value)


class TestCircuitBreakerHalfOpen:
    """Tests pour l'état HALF_OPEN."""

    def test_circuit_transitions_to_half_open_after_timeout(self):
        """Test transition vers HALF_OPEN après timeout."""
        cb = CircuitBreaker(failure_threshold=1, timeout_seconds=0.1)
        
        def failing_func():
            raise Exception("Fails")
        
        # Ouvrir le circuit
        with pytest.raises(Exception):
            cb.call(failing_func)
        
        assert cb.get_state() == CircuitState.OPEN
        
        # Attendre le timeout
        time.sleep(0.15)
        
        # Un appel doit maintenant passer en HALF_OPEN
        # (la transition se fait dans _check_state lors de l'appel)
        try:
            cb.call(failing_func)
        except Exception:
            pass  # On ignore l'exception, on teste juste la transition
        
        assert cb.get_state() == CircuitState.HALF_OPEN

    def test_half_open_success_closes_circuit(self):
        """Test qu'un succès en HALF_OPEN ferme le circuit."""
        cb = CircuitBreaker(failure_threshold=1, timeout_seconds=0.1)
        
        def failing_func():
            raise Exception("Fails")
        
        def success_func():
            return "recovered"
        
        # Ouvrir le circuit
        with pytest.raises(Exception):
            cb.call(failing_func)
        
        # Attendre le timeout
        time.sleep(0.15)
        
        # Test de récupération réussi
        result = cb.call(success_func)
        
        assert result == "recovered"
        assert cb.get_state() == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_half_open_failure_reopens_circuit(self):
        """Test qu'un échec en HALF_OPEN réouvre le circuit."""
        cb = CircuitBreaker(failure_threshold=1, timeout_seconds=0.1)
        
        def failing_func():
            raise Exception("Still failing")
        
        # Ouvrir le circuit
        with pytest.raises(Exception):
            cb.call(failing_func)
        
        # Attendre le timeout
        time.sleep(0.15)
        
        # Test de récupération échoué
        with pytest.raises(Exception):
            cb.call(failing_func)
        
        assert cb.get_state() == CircuitState.OPEN


class TestCircuitBreakerReset:
    """Tests pour la réinitialisation du circuit."""

    def test_manual_reset_closes_circuit(self):
        """Test réinitialisation manuelle."""
        cb = CircuitBreaker(failure_threshold=1)
        
        def failing_func():
            raise Exception("Fails")
        
        # Ouvrir le circuit
        with pytest.raises(Exception):
            cb.call(failing_func)
        
        assert cb.get_state() == CircuitState.OPEN
        assert cb.failure_count == 1
        
        # Réinitialiser
        cb.reset()
        
        assert cb.get_state() == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.last_failure_time is None

    def test_reset_from_half_open(self):
        """Test réinitialisation depuis HALF_OPEN."""
        cb = CircuitBreaker(failure_threshold=1, timeout_seconds=0.1)
        
        def failing_func():
            raise Exception("Fails")
        
        # Ouvrir le circuit
        with pytest.raises(Exception):
            cb.call(failing_func)
        
        # Attendre timeout pour passer en HALF_OPEN
        time.sleep(0.15)
        
        # S'assurer qu'on passe en HALF_OPEN avec un appel
        try:
            cb.call(failing_func)
        except Exception:
            pass
        
        assert cb.get_state() == CircuitState.HALF_OPEN
        
        # Réinitialiser
        cb.reset()
        
        assert cb.get_state() == CircuitState.CLOSED
        assert cb.failure_count == 0


class TestCircuitBreakerStats:
    """Tests pour les statistiques du circuit."""

    def test_get_stats_closed_state(self):
        """Test statistiques en état CLOSED."""
        cb = CircuitBreaker(failure_threshold=5, timeout_seconds=60)
        
        stats = cb.get_stats()
        
        assert stats["state"] == "closed"
        assert stats["failure_count"] == 0
        assert stats["failure_threshold"] == 5
        assert stats["last_failure_time"] is None
        assert "time_until_retry" not in stats

    def test_get_stats_open_state(self):
        """Test statistiques en état OPEN."""
        cb = CircuitBreaker(failure_threshold=1, timeout_seconds=10)
        
        def failing_func():
            raise Exception("Fails")
        
        # Ouvrir le circuit
        with pytest.raises(Exception):
            cb.call(failing_func)
        
        stats = cb.get_stats()
        
        assert stats["state"] == "open"
        assert stats["failure_count"] == 1
        assert stats["failure_threshold"] == 1
        assert stats["last_failure_time"] is not None
        assert "time_until_retry" in stats
        assert stats["time_until_retry"] <= 10

    def test_get_stats_half_open_state(self):
        """Test statistiques en état HALF_OPEN."""
        cb = CircuitBreaker(failure_threshold=1, timeout_seconds=0.1)
        
        def failing_func():
            raise Exception("Fails")
        
        # Ouvrir le circuit
        with pytest.raises(Exception):
            cb.call(failing_func)
        
        # Attendre timeout
        time.sleep(0.15)
        
        # S'assurer qu'on passe en HALF_OPEN avec un appel
        try:
            cb.call(failing_func)
        except Exception:
            pass
        
        stats = cb.get_stats()
        
        assert stats["state"] == "half_open"
        assert stats["failure_count"] == 1


class TestCircuitBreakerThreadSafety:
    """Tests de thread safety."""

    def test_concurrent_calls_thread_safe(self):
        """Test que les appels concurrents sont thread-safe."""
        cb = CircuitBreaker(failure_threshold=2)
        results = []
        errors = []
        
        def successful_call():
            try:
                result = cb.call(lambda: "success")
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        def failing_call():
            try:
                cb.call(lambda: (_ for _ in ()).throw(Exception("Failing")))
            except Exception as e:
                errors.append(e)
        
        # Lancer des threads concurrents
        threads = []
        for i in range(5):
            threads.append(threading.Thread(target=successful_call))
            threads.append(threading.Thread(target=failing_call))
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Vérifier que les résultats sont cohérents
        assert len(results) + len(errors) == 10

    def test_concurrent_state_changes(self):
        """Test que les changements d'état concurrents sont gérés."""
        cb = CircuitBreaker(failure_threshold=10)  # Seuil élevé pour éviter l'ouverture rapide
        states = []
        
        def get_state_repeatedly():
            for _ in range(50):
                states.append(cb.get_state())
                time.sleep(0.001)
        
        threads = [threading.Thread(target=get_state_repeatedly) for _ in range(3)]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Vérifier que tous les états sont valides
        valid_states = {CircuitState.CLOSED, CircuitState.OPEN, CircuitState.HALF_OPEN}
        assert all(state in valid_states for state in states)


class TestCircuitBreakerEdgeCases:
    """Tests des cas limites."""

    def test_zero_failure_threshold(self):
        """Test avec seuil d'échecs à 0 (circuit s'ouvre immédiatement)."""
        cb = CircuitBreaker(failure_threshold=0)
        
        def failing_func():
            raise Exception("Fails")
        
        # Avec un seuil de 0, le circuit s'ouvre dès le premier échec
        try:
            cb.call(failing_func)
        except Exception:
            pass
        
        # Le seuil de 0 signifie que le circuit s'ouvre immédiatement
        assert cb.get_state() == CircuitState.OPEN

    def test_negative_timeout(self):
        """Test avec timeout négatif."""
        cb = CircuitBreaker(timeout_seconds=-1)
        
        # Le circuit devrait toujours considérer que le timeout est écoulé
        assert cb._should_attempt_reset() is True

    def test_call_none_function(self):
        """Test appel avec une fonction None."""
        cb = CircuitBreaker()
        
        with pytest.raises(TypeError):
            cb.call(None)

    def test_call_with_exception_in_kwargs(self):
        """Test appel avec exception dans kwargs."""
        cb = CircuitBreaker()
        
        def func_that_uses_kwargs(**kwargs):
            return kwargs.get('value', 'default')
        
        # Test normal
        result = cb.call(func_that_uses_kwargs, value="test")
        assert result == "test"
        
        # Test avec exception dans kwargs
        result = cb.call(func_that_uses_kwargs)
        assert result == "default"
