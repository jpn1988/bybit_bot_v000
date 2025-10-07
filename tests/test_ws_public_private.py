#!/usr/bin/env python3
"""
Tests ciblés pour ws_public.PublicWSClient et ws_private.PrivateWSClient.
"""

import pytest
from unittest.mock import Mock, patch


class TestPublicWSClient:
    def test_build_url_linear_inverse(self):
        from ws_public import PublicWSClient

        c_lin_tn = PublicWSClient("linear", ["BTCUSDT"], True, Mock(), lambda d: None)
        c_inv_mn = PublicWSClient("inverse", ["BTCUSD"], False, Mock(), lambda d: None)
        assert "public/linear" in c_lin_tn._build_url()
        assert "public/inverse" in c_inv_mn._build_url()

    def test_on_open_subscribes_and_callbacks(self):
        from ws_public import PublicWSClient

        client = PublicWSClient("linear", ["BTCUSDT"], True, Mock(), lambda d: None)
        client.on_open_callback = Mock()
        fake_ws = Mock()
        with patch('ws_public.record_ws_connection') as rec:
            client._on_open(fake_ws)
            rec.assert_called_with(connected=True)
            assert fake_ws.send.called
            client.on_open_callback.assert_called_once()

    def test_on_message_ticker_and_json_errors(self):
        from ws_public import PublicWSClient

        cb = Mock()
        client = PublicWSClient("linear", ["BTCUSDT"], True, Mock(), cb)

        # Message ticker valide
        msg = '{"topic":"tickers.BTCUSDT","data":{"symbol":"BTCUSDT"}}'
        client._on_message(Mock(), msg)
        cb.assert_called_once()

        # JSON invalide
        cb.reset_mock()
        client._on_message(Mock(), "{" )
        cb.assert_not_called()

    def test_on_error_and_close_callbacks(self):
        from ws_public import PublicWSClient

        client = PublicWSClient("linear", [], True, Mock(), lambda d: None)
        client.running = True
        client.on_error_callback = Mock()
        client._on_error(Mock(), "boom")
        client.on_error_callback.assert_called_once()

        client.on_close_callback = Mock()
        client._on_close(Mock(), 1000, "bye")
        client.on_close_callback.assert_called_once()

    def test_close_cleans(self):
        from ws_public import PublicWSClient

        client = PublicWSClient("linear", [], True, Mock(), lambda d: None)
        client.ws = Mock()
        client.running = True
        client.close()
        assert client.ws is None
        assert client.on_ticker_callback is None


class TestPrivateWSClient:
    def test_ws_url_and_signature(self):
        from ws_private import PrivateWSClient

        cli = PrivateWSClient(testnet=True, api_key="k", api_secret="s", channels=["p"], logger=Mock())
        assert "testnet" in cli.ws_url
        sig = cli._generate_ws_signature(1234567890000)
        assert isinstance(sig, str) and len(sig) == 64

    def test_on_open_sends_auth(self):
        from ws_private import PrivateWSClient

        cli = PrivateWSClient(testnet=True, api_key="k", api_secret="s", channels=[], logger=Mock())
        fake_ws = Mock()
        cli.ws = fake_ws
        cli._on_open(fake_ws)
        assert cli.connected is True
        assert fake_ws.send.called

    def test_on_message_auth_success_subscribe_and_topic(self):
        from ws_private import PrivateWSClient

        cli = PrivateWSClient(testnet=True, api_key="k", api_secret="s", channels=["order"], logger=Mock())
        fake_ws = Mock()
        cli.ws = fake_ws

        # Auth success
        cli._on_message(fake_ws, '{"op":"auth","retCode":0,"success":true}')
        assert cli._authed is True
        assert fake_ws.send.called

        # Topic message
        got = {}
        cli.on_topic = lambda topic, data: got.setdefault("t", topic)
        cli._on_message(fake_ws, '{"topic":"order","data":{}}')
        assert got.get("t") == "order"

    def test_on_message_auth_failure_closes(self):
        from ws_private import PrivateWSClient

        cli = PrivateWSClient(testnet=True, api_key="k", api_secret="s", channels=[], logger=Mock())
        fake_ws = Mock()
        cli.ws = fake_ws
        cli._on_message(fake_ws, '{"op":"auth","retCode":10005,"retMsg":"bad"}')
        assert cli._authed is False
        assert fake_ws.close.called

    def test_on_message_pong_triggers_callback(self):
        from ws_private import PrivateWSClient

        cli = PrivateWSClient(testnet=True, api_key="k", api_secret="s", channels=[], logger=Mock())
        cb = Mock()
        cli.on_pong = cb
        cli._on_message(Mock(), '{"op":"pong"}')
        cb.assert_called_once()

    def test_close_stops_running(self):
        from ws_private import PrivateWSClient

        cli = PrivateWSClient(testnet=True, api_key="k", api_secret="s", channels=[], logger=Mock())
        cli.ws = Mock()
        cli.close()
        assert cli.running is False

