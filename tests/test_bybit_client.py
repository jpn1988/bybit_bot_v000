"""Tests pour le client Bybit."""

import pytest
from unittest.mock import Mock, patch
import httpx
from bybit_client import BybitClient, BybitPublicClient


class _MockResponse:
    def __init__(self, status_code=200, json_data=None, text="", headers=None):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.text = text
        self.headers = headers or {}

    def json(self):
        return self._json


class _SeqClient:
    """Client httpx-like dont get() renvoie une séquence de réponses/erreurs."""

    def __init__(self, seq):
        self._seq = list(seq)

    def get(self, url, headers=None):
        item = self._seq.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class TestBybitClient:
    """Tests pour BybitClient."""
    
    def test_init_with_valid_credentials(self):
        """Test d'initialisation avec des credentials valides."""
        client = BybitClient(
            testnet=True,
            timeout=10,
            api_key="test_key",
            api_secret="test_secret"
        )
        
        assert client.testnet is True
        assert client.timeout == 10
        assert client.api_key == "test_key"
        assert client.api_secret == "test_secret"
        assert client.base_url == "https://api-testnet.bybit.com"
    
    def test_init_without_credentials_raises_error(self):
        """Test qu'une erreur est levée sans credentials."""
        with pytest.raises(RuntimeError, match="Clés API manquantes"):
            BybitClient(testnet=True, timeout=10, api_key=None, api_secret=None)
    
    def test_init_mainnet_url(self):
        """Test de l'URL mainnet."""
        client = BybitClient(
            testnet=False,
            timeout=10,
            api_key="test_key",
            api_secret="test_secret"
        )
        assert client.base_url == "https://api.bybit.com"
    
    def test_get_wallet_balance_success(self, mock_wallet_balance_response):
        """Test de récupération du solde avec succès."""
        client = BybitClient(
            testnet=True,
            timeout=10,
            api_key="test_key",
            api_secret="test_secret"
        )
        
        # Mock directement la méthode qui fait l'appel HTTP
        with patch.object(client, '_execute_request_with_retry') as mock_execute:
            mock_execute.return_value = mock_wallet_balance_response["result"]
            
            result = client.get_wallet_balance("UNIFIED")
            
            assert result == mock_wallet_balance_response["result"]
            mock_execute.assert_called_once()
    
    def test_get_wallet_balance_http_error(self):
        """Test de gestion d'erreur HTTP."""
        client = BybitClient(
            testnet=True,
            timeout=10,
            api_key="test_key",
            api_secret="test_secret"
        )
        
        # Mock directement la méthode qui fait l'appel HTTP pour lever une erreur HTTP
        with patch.object(client, '_execute_request_with_retry') as mock_execute:
            mock_execute.side_effect = RuntimeError("Erreur réseau/HTTP Bybit : Bad Request")
            
            with pytest.raises(RuntimeError, match="Erreur réseau/HTTP Bybit"):
                client.get_wallet_balance("UNIFIED")
    
    def test_get_wallet_balance_api_error(self):
        """Test de gestion d'erreur API."""
        client = BybitClient(
            testnet=True,
            timeout=10,
            api_key="test_key",
            api_secret="test_secret"
        )
        
        # Mock directement la méthode qui fait l'appel HTTP pour lever une erreur API
        with patch.object(client, '_execute_request_with_retry') as mock_execute:
            mock_execute.side_effect = RuntimeError("Authentification échouée : clé/secret invalides ou signature incorrecte")
            
            with pytest.raises(RuntimeError, match="Authentification échouée"):
                client.get_wallet_balance("UNIFIED")

    def test_public_base_url_helper(self):
        client_tn = BybitClient(testnet=True, timeout=5, api_key="k", api_secret="s")
        client_mn = BybitClient(testnet=False, timeout=5, api_key="k", api_secret="s")
        assert client_tn.public_base_url() == "https://api-testnet.bybit.com"
        assert client_mn.public_base_url() == "https://api.bybit.com"

    def test_execute_request_2xx_retcode0_returns_result(self, monkeypatch):
        client = BybitClient(testnet=True, timeout=5, api_key="k", api_secret="s")

        def _mock_http_client(timeout):
            return _SeqClient([
                _MockResponse(
                    status_code=200,
                    json_data={"retCode": 0, "result": {"ok": True}},
                )
            ])

        monkeypatch.setattr("bybit_client.get_http_client", _mock_http_client)
        monkeypatch.setattr("bybit_client.record_api_call", lambda latency, success: None)

        res = client._execute_request_with_retry("http://x", headers={})
        assert res == {"ok": True}

    def test_execute_request_http_4xx_raises_runtimeerror_with_detail(self, monkeypatch):
        client = BybitClient(testnet=True, timeout=5, api_key="k", api_secret="s")

        long_text = "X" * 300

        def _mock_http_client(timeout):
            return _SeqClient([
                _MockResponse(status_code=400, text=long_text),
            ])

        monkeypatch.setattr("bybit_client.get_http_client", _mock_http_client)
        monkeypatch.setattr("bybit_client.record_api_call", lambda latency, success: None)

        with pytest.raises(RuntimeError) as e:
            client._execute_request_with_retry("http://x", headers={})
        # Détail tronqué par _handle_http_response (100 chars max)
        assert "Erreur HTTP Bybit" in str(e.value)

    def test_execute_request_http_5xx_retries_then_error(self, monkeypatch):
        client = BybitClient(testnet=True, timeout=5, api_key="k", api_secret="s")

        def _mock_http_client(timeout):
            # Toutes les tentatives renvoient 5xx pour forcer l'échec final
            return _SeqClient([
                _MockResponse(status_code=500),
                _MockResponse(status_code=503),
                _MockResponse(status_code=500),
                _MockResponse(status_code=502),
            ])

        sleeps = []
        monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))
        monkeypatch.setattr("bybit_client.get_http_client", _mock_http_client)

        called = {"ok": 0, "err": 0}

        def _rec(latency, success):
            called["ok" if success else "err"] += 1

        monkeypatch.setattr("bybit_client.record_api_call", _rec)

        with pytest.raises(RuntimeError, match="Erreur réseau/HTTP Bybit"):
            client._execute_request_with_retry("http://x", headers={})

        # Des sleeps ont eu lieu (backoff)
        assert len(sleeps) >= 1
        # Échec enregistré
        assert called["err"] == 1

    def test_execute_request_http_429_retry_after_then_success(self, monkeypatch):
        client = BybitClient(testnet=True, timeout=5, api_key="k", api_secret="s")

        def _mock_http_client(timeout):
            return _SeqClient([
                _MockResponse(status_code=429, headers={"Retry-After": "0"}),
                _MockResponse(status_code=200, json_data={"retCode": 0, "result": {"ok": True}}),
            ])

        sleeps = []
        monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))
        monkeypatch.setattr("bybit_client.get_http_client", _mock_http_client)
        monkeypatch.setattr("bybit_client.record_api_call", lambda latency, success: None)

        res = client._execute_request_with_retry("http://x", headers={})
        assert res == {"ok": True}
        # Respect du Retry-After (sleep appelé)
        assert len(sleeps) >= 1

    def test_api_errors_specific_codes(self, monkeypatch):
        client = BybitClient(testnet=True, timeout=5, api_key="k", api_secret="s")

        for code, msg in [
            (10005, "Authentification échouée"),
            (10006, "Authentification échouée"),
            (10018, "Accès refusé"),
            (10017, "Horodatage invalide"),
        ]:
            def _mk(timeout):
                return _SeqClient([
                    _MockResponse(status_code=200, json_data={"retCode": code, "retMsg": msg}),
                ])

            monkeypatch.setattr("bybit_client.get_http_client", _mk)
            monkeypatch.setattr("bybit_client.record_api_call", lambda latency, success: None)

            with pytest.raises(RuntimeError):
                client._execute_request_with_retry("http://x", headers={})

    def test_api_rate_limit_retcode_10016_retry_then_success(self, monkeypatch):
        client = BybitClient(testnet=True, timeout=5, api_key="k", api_secret="s")

        # Première réponse retCode 10016 (rate limit), puis succès
        def _mk(timeout):
            return _SeqClient([
                _MockResponse(status_code=200, json_data={"retCode": 10016}),
                _MockResponse(status_code=200, json_data={"retCode": 0, "result": {"ok": True}}),
            ])

        sleeps = []
        monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))
        monkeypatch.setattr("bybit_client.get_http_client", _mk)
        monkeypatch.setattr("bybit_client.record_api_call", lambda latency, success: None)

        res = client._execute_request_with_retry("http://x", headers={})
        assert res == {"ok": True}
        assert len(sleeps) >= 1

    def test_api_rate_limit_retcode_10016_retry_then_fail(self, monkeypatch):
        client = BybitClient(testnet=True, timeout=5, api_key="k", api_secret="s")

        def _mk(timeout):
            return _SeqClient([
                _MockResponse(status_code=200, json_data={"retCode": 10016}),
                _MockResponse(status_code=200, json_data={"retCode": 10016}),
                _MockResponse(status_code=200, json_data={"retCode": 10016}),
                _MockResponse(status_code=200, json_data={"retCode": 10016}),
            ])

        monkeypatch.setattr("time.sleep", lambda s: None)
        monkeypatch.setattr("bybit_client.get_http_client", _mk)
        monkeypatch.setattr("bybit_client.record_api_call", lambda latency, success: None)

        with pytest.raises(RuntimeError, match="Limite de requêtes atteinte|Erreur réseau/HTTP Bybit|Erreur API Bybit"):
            client._execute_request_with_retry("http://x", headers={})

    def test_retry_backoff_and_jitter(self, monkeypatch):
        client = BybitClient(testnet=True, timeout=5, api_key="k", api_secret="s")

        # Jitter déterministe
        monkeypatch.setattr("random.uniform", lambda a, b: 0.0)
        # Vérifie progression de backoff: base=0.5 -> 0.5, 1.0, 2.0
        assert client._calculate_retry_delay(1, 0.5) == 0.5
        assert client._calculate_retry_delay(2, 0.5) == 1.0
        assert client._calculate_retry_delay(3, 0.5) == 2.0

    def test_robustness_timeouts_and_request_errors(self, monkeypatch):
        client = BybitClient(testnet=True, timeout=5, api_key="k", api_secret="s")

        seq = [
            httpx.TimeoutException("t1"),
            httpx.RequestError("r1", request=None),
            _MockResponse(status_code=200, json_data={"retCode": 0, "result": {"ok": True}}),
        ]

        def _mk(timeout):
            return _SeqClient(seq.copy())

        monkeypatch.setattr("bybit_client.get_http_client", _mk)
        monkeypatch.setattr("time.sleep", lambda s: None)
        monkeypatch.setattr("bybit_client.record_api_call", lambda latency, success: None)

        res = client._execute_request_with_retry("http://x", headers={})
        assert res == {"ok": True}


class TestBybitPublicClient:
    """Tests pour BybitPublicClient."""
    
    def test_init_testnet(self):
        """Test d'initialisation en mode testnet."""
        client = BybitPublicClient(testnet=True, timeout=10)
        assert client.testnet is True
        assert client.timeout == 10
        assert client.public_base_url() == "https://api-testnet.bybit.com"
    
    def test_init_mainnet(self):
        """Test d'initialisation en mode mainnet."""
        client = BybitPublicClient(testnet=False, timeout=10)
        assert client.testnet is False
        assert client.timeout == 10
        assert client.public_base_url() == "https://api.bybit.com"
