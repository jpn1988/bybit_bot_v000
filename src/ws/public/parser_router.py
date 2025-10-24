#!/usr/bin/env python3
import json
from typing import Callable, Optional
from .models import TickerData, OrderbookData


class PublicMessageParser:
    """Parse les messages WS publics en objets structurés."""

    @staticmethod
    def parse_ticker(payload: dict) -> Optional[TickerData]:
        data = payload.get("data") or {}
        if not data:
            return None
        try:
            return TickerData(
                symbol=str(data.get("symbol", "")),
                last_price=float(data.get("lastPrice")) if data.get("lastPrice") is not None else None,
                mark_price=float(data.get("markPrice")) if data.get("markPrice") is not None else None,
                bid1_price=float(data.get("bid1Price")) if data.get("bid1Price") is not None else None,
                ask1_price=float(data.get("ask1Price")) if data.get("ask1Price") is not None else None,
                volume24h=float(data.get("volume24h")) if data.get("volume24h") is not None else None,
                turnover24h=float(data.get("turnover24h")) if data.get("turnover24h") is not None else None,
            )
        except (TypeError, ValueError):
            return None

    @staticmethod
    def parse_orderbook(payload: dict) -> Optional[OrderbookData]:
        data = payload.get("data") or {}
        if not data:
            return None
        try:
            # Exemple minimal pour depth=1
            return OrderbookData(
                symbol=str(data.get("s") or data.get("symbol") or ""),
                bid1_price=float(data.get("b")[0][0]) if data.get("b") else None,
                bid1_size=float(data.get("b")[0][1]) if data.get("b") else None,
                ask1_price=float(data.get("a")[0][0]) if data.get("a") else None,
                ask1_size=float(data.get("a")[0][1]) if data.get("a") else None,
            )
        except (TypeError, ValueError, IndexError):
            return None


class PublicMessageRouter:
    """Routage des messages WS publics vers les callbacks applicatifs."""

    def __init__(self, on_ticker: Optional[Callable[[dict], None]] = None) -> None:
        self.on_ticker_raw = on_ticker

    def route(self, raw_message: str, logger, category: str) -> None:
        try:
            payload = json.loads(raw_message)
        except json.JSONDecodeError as e:
            try:
                logger.warning(f"⚠️ Erreur JSON ({category}): {e}")
            except Exception:
                pass
            return

        topic: str = payload.get("topic", "")
        if topic.startswith("tickers.") and self.on_ticker_raw:
            ticker_obj = PublicMessageParser.parse_ticker(payload)
            if ticker_obj:
                # Repasse en dict (compat rétro) pour les callbacks existants
                self.on_ticker_raw({
                    "symbol": ticker_obj.symbol,
                    "lastPrice": ticker_obj.last_price,
                    "markPrice": ticker_obj.mark_price,
                    "bid1Price": ticker_obj.bid1_price,
                    "ask1Price": ticker_obj.ask1_price,
                    "volume24h": ticker_obj.volume24h,
                    "turnover24h": ticker_obj.turnover24h,
                })


