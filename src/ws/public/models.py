#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TickerData:
    symbol: str
    last_price: float
    mark_price: Optional[float] = None
    bid1_price: Optional[float] = None
    ask1_price: Optional[float] = None
    volume24h: Optional[float] = None
    turnover24h: Optional[float] = None


@dataclass(frozen=True)
class OrderbookData:
    symbol: str
    bid1_price: Optional[float]
    ask1_price: Optional[float]
    bid1_size: Optional[float]
    ask1_size: Optional[float]


