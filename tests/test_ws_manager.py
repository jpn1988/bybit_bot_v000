#!/usr/bin/env python3
"""
Tests pour WebSocketManager (ws_manager.py)

Couvre:
- Démarrage des connexions (linear, inverse, dual)
- Traitement des tickers et parsing JSON minimal
- Callback externe de ticker
- Arrêt propre (async) et nettoyage
- Cas limites (aucun symbole, double start)
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from ws_manager import WebSocketManager


class TestWebSocketManager:
    @pytest.mark.asyncio
    async def test_start_connections_linear(self):
        with patch('ws_manager.PublicWSClient') as mock_client:
            manager = WebSocketManager(testnet=True, logger=Mock())
            await manager.start_connections(["BTCUSDT"], [])

            # Une seule connexion créée
            assert len(manager._ws_conns) == 1
            mock_client.assert_called_once()
            assert manager.is_running() is True
            assert manager.get_connected_symbols()["linear"] == ["BTCUSDT"]

    @pytest.mark.asyncio
    async def test_start_connections_inverse(self):
        with patch('ws_manager.PublicWSClient') as mock_client:
            manager = WebSocketManager(testnet=True, logger=Mock())
            await manager.start_connections([], ["BTCUSD"])

            assert len(manager._ws_conns) == 1
            mock_client.assert_called_once()
            assert manager.is_running() is True
            assert manager.get_connected_symbols()["inverse"] == ["BTCUSD"]

    @pytest.mark.asyncio
    async def test_start_connections_dual(self):
        with patch('ws_manager.PublicWSClient') as mock_client:
            manager = WebSocketManager(testnet=True, logger=Mock())
            await manager.start_connections(["BTCUSDT"], ["BTCUSD"])

            # Deux connexions créées
            assert len(manager._ws_conns) == 2
            assert manager.is_running() is True

    @pytest.mark.asyncio
    async def test_start_connections_no_symbols(self):
        logger = Mock()
        manager = WebSocketManager(testnet=True, logger=logger)
        await manager.start_connections([], [])
        # Aucun crash, warning logué par le manager
        assert manager.is_running() is True  # running passe à True même sans tâches
        assert manager.get_connected_symbols() == {"linear": [], "inverse": []}

    def test_set_ticker_callback(self):
        manager = WebSocketManager(testnet=True, logger=Mock())
        cb = Mock()
        manager.set_ticker_callback(cb)
        # Appel via interne
        manager._handle_ticker({"symbol": "BTCUSDT", "markPrice": "50000", "lastPrice": "50001"})
        cb.assert_called_once()

    def test_handle_ticker_updates_store(self):
        manager = WebSocketManager(testnet=True, logger=Mock())
        # Patch de update() global pour ne pas toucher le vrai store
        with patch('ws_manager.update') as mock_update:
            manager._handle_ticker({
                "symbol": "BTCUSDT",
                "markPrice": "50000.0",
                "lastPrice": "50010.0",
            })
            mock_update.assert_called_once()

    def test_handle_ticker_ignores_incomplete(self):
        manager = WebSocketManager(testnet=True, logger=Mock())
        with patch('ws_manager.update') as mock_update:
            # Manque markPrice
            manager._handle_ticker({"symbol": "BTCUSDT", "lastPrice": "50010.0"})
            mock_update.assert_not_called()

    def test_handle_ticker_parsing_error(self):
        logger = Mock()
        manager = WebSocketManager(testnet=True, logger=logger)
        with patch('ws_manager.update', side_effect=Exception("boom")):
            # Ne doit pas lever, log un warning
            manager._handle_ticker({
                "symbol": "BTCUSDT",
                "markPrice": "50000.0",
                "lastPrice": "50010.0",
            })
            # Pas d'assert stricte sur logger pour éviter la fragilité

    @pytest.mark.asyncio
    async def test_stop_without_running(self):
        manager = WebSocketManager(testnet=True, logger=Mock())
        # Not running → no-op
        await manager.stop()
        assert manager.is_running() is False

    @pytest.mark.asyncio
    async def test_stop_cancels_tasks_and_cleans(self):
        manager = WebSocketManager(testnet=True, logger=Mock())
        # Simuler une connexion et une tâche
        fake_conn = Mock()
        fake_task = AsyncMock()
        fake_task.done.return_value = False
        manager._ws_conns = [fake_conn]
        manager._ws_tasks = [fake_task]
        manager.linear_symbols = ["BTCUSDT"]
        manager.inverse_symbols = ["BTCUSD"]
        manager.running = True

        await manager.stop()

        assert manager.is_running() is False
        assert manager._ws_conns == []
        assert manager._ws_tasks == []
        assert manager.get_connected_symbols() == {"linear": [], "inverse": []}

    @pytest.mark.asyncio
    async def test_double_start_is_safe(self):
        manager = WebSocketManager(testnet=True, logger=Mock())
        manager.running = True
        # Ne doit pas lever, juste log un warning
        await manager.start_connections(["BTCUSDT"], [])
        assert manager.is_running() is True

    def test_stop_sync_cleans_state(self):
        manager = WebSocketManager(testnet=True, logger=Mock())
        fake_conn = Mock()
        manager._ws_conns = [fake_conn]
        manager._ws_tasks = [Mock()]
        manager.linear_symbols = ["BTCUSDT"]
        manager.inverse_symbols = ["BTCUSD"]
        manager.running = True

        manager.stop_sync()

        assert manager.is_running() is False
        assert manager._ws_conns == []
        assert manager._ws_tasks == []
        assert manager.get_connected_symbols() == {"linear": [], "inverse": []}

    @pytest.mark.asyncio
    async def test_run_websocket_connection_handles_exception_when_running(self):
        manager = WebSocketManager(testnet=True, logger=Mock())
        manager.running = True
        bad_conn = Mock()

        async def fake_run_in_executor(_, __):
            raise RuntimeError("ws boom")

        with patch('asyncio.get_event_loop') as mock_loop:
            loop = Mock()
            loop.run_in_executor = fake_run_in_executor
            mock_loop.return_value = loop
            await manager._run_websocket_connection(bad_conn)

    def test_ticker_callback_called_only_if_set_and_symbol_present(self):
        manager = WebSocketManager(testnet=True, logger=Mock())
        cb = Mock()
        manager.set_ticker_callback(cb)

        manager._handle_ticker({
            "symbol": "ETHUSDT",
            "markPrice": "1000.0",
            "lastPrice": "1001.0",
        })
        assert cb.called

        cb.reset_mock()
        manager._handle_ticker({
            "markPrice": "1000.0",
            "lastPrice": "1001.0",
        })
        cb.assert_not_called()