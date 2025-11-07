#!/usr/bin/env python3
"""
Gestionnaire de configuration pour la parallélisation des appels API.

Ce module charge et gère la configuration de parallélisation
depuis le fichier parallel_config.yaml.
"""

import yaml
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path

from parallel_api_manager import ParallelConfig, ExecutionMode


@dataclass
class VolatilityConfig:
    """Configuration spécifique pour le calcul de volatilité."""
    max_concurrent: int = 5
    batch_size: int = 20
    timeout: float = 15.0


@dataclass
class FundingConfig:
    """Configuration spécifique pour la récupération de funding."""
    max_concurrent: int = 8
    batch_size: int = 30
    timeout: float = 10.0


@dataclass
class SpreadConfig:
    """Configuration spécifique pour la récupération de spread."""
    max_concurrent: int = 6
    batch_size: int = 25
    timeout: float = 8.0


@dataclass
class RateLimitingConfig:
    """Configuration du rate limiting."""
    enabled: bool = True
    public_max_calls_per_sec: int = 5
    public_window_seconds: float = 1.0
    private_max_calls_per_sec: int = 10
    private_window_seconds: float = 1.0


@dataclass
class TimeoutsConfig:
    """Configuration des timeouts."""
    http_request: int = 15
    bybit_api_request: int = 30
    data_fetch: int = 30
    spread_fetch: int = 10
    funding_fetch: int = 10
    volatility_fetch: int = 15
    websocket_connect: int = 20
    websocket_message: int = 10


@dataclass
class ConcurrencyConfig:
    """Configuration de la concurrence."""
    volatility_max_concurrent_requests: int = 5
    http_max_concurrent_requests: int = 10
    max_thread_pool_workers: int = 4


@dataclass
class ScanIntervalsConfig:
    """Configuration des intervalles de scan."""
    market_scan: int = 60
    volatility_refresh: int = 120
    health_check: int = 1
    memory_monitoring: int = 60
    metrics_display: int = 300


@dataclass
class SleepDelaysConfig:
    """Configuration des délais de sommeil."""
    short: float = 0.1
    medium: float = 0.2
    reconnect: float = 1.0
    volatility_retry: float = 5.0
    rate_limit: float = 0.05


class ParallelConfigManager:
    """
    Gestionnaire de configuration pour la parallélisation.

    Cette classe charge et gère la configuration de parallélisation
    depuis le fichier YAML et fournit des configurations optimisées
    pour différents types d'opérations.
    """

    def __init__(self, config_path: str = "src/parallel_config.yaml"):
        """
        Initialise le gestionnaire de configuration.

        Args:
            config_path: Chemin vers le fichier de configuration
        """
        self.config_path = config_path
        self._config: Optional[Dict[str, Any]] = None
        self._load_config()

    def _load_config(self) -> None:
        """Charge la configuration depuis le fichier YAML."""
        try:
            config_file = Path(self.config_path)
            if not config_file.exists():
                self._config = self._get_default_config()
                return

            with open(config_file, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)

        except Exception as e:
            print(f"⚠️ Erreur chargement config parallélisation: {e}")
            self._config = self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Retourne la configuration par défaut."""
        return {
            "max_concurrent_requests": 10,
            "batch_size": 50,
            "max_retries": 3,
            "retry_delay": 0.1,
            "timeout": 30.0,
            "volatility": {
                "max_concurrent": 5,
                "batch_size": 20,
                "timeout": 15.0
            },
            "funding": {
                "max_concurrent": 8,
                "batch_size": 30,
                "timeout": 10.0
            },
            "spread": {
                "max_concurrent": 6,
                "batch_size": 25,
                "timeout": 8.0
            },
            "rate_limiting": {
                "enabled": True,
                "public_max_calls_per_sec": 5,
                "public_window_seconds": 1.0,
                "private_max_calls_per_sec": 10,
                "private_window_seconds": 1.0
            }
        }

    def get_volatility_config(self) -> VolatilityConfig:
        """Retourne la configuration pour le calcul de volatilité."""
        vol_config = self._config.get("volatility", {})
        return VolatilityConfig(
            max_concurrent=vol_config.get("max_concurrent", 5),
            batch_size=vol_config.get("batch_size", 20),
            timeout=vol_config.get("timeout", 15.0)
        )

    def get_funding_config(self) -> FundingConfig:
        """Retourne la configuration pour la récupération de funding."""
        funding_config = self._config.get("funding", {})
        return FundingConfig(
            max_concurrent=funding_config.get("max_concurrent", 8),
            batch_size=funding_config.get("batch_size", 30),
            timeout=funding_config.get("timeout", 10.0)
        )

    def get_spread_config(self) -> SpreadConfig:
        """Retourne la configuration pour la récupération de spread."""
        spread_config = self._config.get("spread", {})
        return SpreadConfig(
            max_concurrent=spread_config.get("max_concurrent", 6),
            batch_size=spread_config.get("batch_size", 25),
            timeout=spread_config.get("timeout", 8.0)
        )

    def get_rate_limiting_config(self) -> RateLimitingConfig:
        """Retourne la configuration du rate limiting."""
        rate_config = self._config.get("rate_limiting", {})
        return RateLimitingConfig(
            enabled=rate_config.get("enabled", True),
            public_max_calls_per_sec=rate_config.get("public_max_calls_per_sec", 5),
            public_window_seconds=rate_config.get("public_window_seconds", 1.0),
            private_max_calls_per_sec=rate_config.get("private_max_calls_per_sec", 10),
            private_window_seconds=rate_config.get("private_window_seconds", 1.0)
        )

    def get_parallel_config(self, operation_type: str = "default") -> ParallelConfig:
        """
        Retourne une configuration ParallelConfig optimisée pour un type d'opération.

        Args:
            operation_type: Type d'opération ("volatility", "funding", "spread", "default")

        Returns:
            Configuration ParallelConfig optimisée
        """
        base_config = {
            "max_concurrent": self._config.get("max_concurrent_requests", 10),
            "batch_size": self._config.get("batch_size", 50),
            "max_retries": self._config.get("max_retries", 3),
            "retry_delay": self._config.get("retry_delay", 0.1),
            "timeout": self._config.get("timeout", 30.0),
            "mode": ExecutionMode.ASYNC,
            "rate_limit_enabled": self._config.get("rate_limiting", {}).get("enabled", True)
        }

        if operation_type == "volatility":
            vol_config = self.get_volatility_config()
            base_config.update({
                "max_concurrent": vol_config.max_concurrent,
                "batch_size": vol_config.batch_size,
                "timeout": vol_config.timeout
            })
        elif operation_type == "funding":
            funding_config = self.get_funding_config()
            base_config.update({
                "max_concurrent": funding_config.max_concurrent,
                "batch_size": funding_config.batch_size,
                "timeout": funding_config.timeout
            })
        elif operation_type == "spread":
            spread_config = self.get_spread_config()
            base_config.update({
                "max_concurrent": spread_config.max_concurrent,
                "batch_size": spread_config.batch_size,
                "timeout": spread_config.timeout
            })

        return ParallelConfig(**base_config)

    def get_timeouts_config(self) -> TimeoutsConfig:
        """Retourne la configuration des timeouts."""
        timeouts_config = self._config.get("timeouts", {})
        return TimeoutsConfig(
            http_request=timeouts_config.get("http_request", 15),
            bybit_api_request=timeouts_config.get("bybit_api_request", 30),
            data_fetch=timeouts_config.get("data_fetch", 30),
            spread_fetch=timeouts_config.get("spread_fetch", 10),
            funding_fetch=timeouts_config.get("funding_fetch", 10),
            volatility_fetch=timeouts_config.get("volatility_fetch", 15),
            websocket_connect=timeouts_config.get("websocket_connect", 20),
            websocket_message=timeouts_config.get("websocket_message", 10)
        )

    def get_concurrency_config(self) -> ConcurrencyConfig:
        """Retourne la configuration de la concurrence."""
        concurrency_config = self._config.get("concurrency", {})
        return ConcurrencyConfig(
            volatility_max_concurrent_requests=concurrency_config.get("volatility_max_concurrent_requests", 5),
            http_max_concurrent_requests=concurrency_config.get("http_max_concurrent_requests", 10),
            max_thread_pool_workers=concurrency_config.get("max_thread_pool_workers", 4)
        )

    def get_scan_intervals_config(self) -> ScanIntervalsConfig:
        """Retourne la configuration des intervalles de scan."""
        intervals_config = self._config.get("scan_intervals", {})
        return ScanIntervalsConfig(
            market_scan=intervals_config.get("market_scan", 60),
            volatility_refresh=intervals_config.get("volatility_refresh", 120),
            health_check=intervals_config.get("health_check", 1),
            memory_monitoring=intervals_config.get("memory_monitoring", 60),
            metrics_display=intervals_config.get("metrics_display", 300)
        )

    def get_sleep_delays_config(self) -> SleepDelaysConfig:
        """Retourne la configuration des délais de sommeil."""
        delays_config = self._config.get("sleep_delays", {})
        return SleepDelaysConfig(
            short=delays_config.get("short", 0.1),
            medium=delays_config.get("medium", 0.2),
            reconnect=delays_config.get("reconnect", 1.0),
            volatility_retry=delays_config.get("volatility_retry", 5.0),
            rate_limit=delays_config.get("rate_limit", 0.05)
        )

    def reload_config(self) -> None:
        """Recharge la configuration depuis le fichier."""
        self._load_config()

    def get_config_summary(self) -> Dict[str, Any]:
        """Retourne un résumé de la configuration actuelle."""
        return {
            "volatility": self.get_volatility_config().__dict__,
            "funding": self.get_funding_config().__dict__,
            "spread": self.get_spread_config().__dict__,
            "rate_limiting": self.get_rate_limiting_config().__dict__,
            "timeouts": self.get_timeouts_config().__dict__,
            "concurrency": self.get_concurrency_config().__dict__,
            "scan_intervals": self.get_scan_intervals_config().__dict__,
            "sleep_delays": self.get_sleep_delays_config().__dict__
        }


# Instance globale pour faciliter l'utilisation
_global_config_manager: Optional[ParallelConfigManager] = None


def get_parallel_config_manager() -> ParallelConfigManager:
    """
    Retourne l'instance globale du gestionnaire de configuration.

    Returns:
        Instance configurée de ParallelConfigManager
    """
    global _global_config_manager
    if _global_config_manager is None:
        _global_config_manager = ParallelConfigManager()
    return _global_config_manager
