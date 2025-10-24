#!/usr/bin/env python3
from typing import List, Dict


class SubscriptionBuilder:
    """Construit les messages de souscription aux topics publics Bybit."""

    @staticmethod
    def tickers(symbols: List[str]) -> Dict:
        args = [f"tickers.{s}" for s in symbols if s]
        return {"op": "subscribe", "args": args}

    @staticmethod
    def orderbook(symbols: List[str], depth: int = 1) -> Dict:
        args = [f"orderbook.{depth}.{s}" for s in symbols if s]
        return {"op": "subscribe", "args": args}


