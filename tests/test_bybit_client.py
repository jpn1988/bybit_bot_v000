"""Tests pour le client Bybit."""

import pytest
from unittest.mock import Mock, patch
import httpx
from bybit_client import BybitClient, BybitPublicClient


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
