#!/usr/bin/env python3
"""
Validateur de configuration pour le bot Bybit.

Ce module contient toute la logique de validation de la configuration
pour s'assurer que les paramètres sont cohérents et dans les limites acceptables.
"""

from typing import Dict, List
from .constants import (
    MAX_LIMIT_RECOMMENDED,
    MAX_SPREAD_PERCENTAGE,
    MAX_FUNDING_TIME_MINUTES,
    MIN_VOLATILITY_TTL_SECONDS,
    MAX_VOLATILITY_TTL_SECONDS,
    MIN_DISPLAY_INTERVAL_SECONDS,
    MAX_DISPLAY_INTERVAL_SECONDS,
    DEFAULT_WEIGHT_FUNDING,
    DEFAULT_WEIGHT_VOLUME,
    DEFAULT_WEIGHT_SPREAD,
    DEFAULT_WEIGHT_VOLATILITY,
    DEFAULT_TOP_SYMBOLS,
    DEFAULT_ORDER_SIZE_USDT,
    DEFAULT_MAX_POSITIONS,
    DEFAULT_ORDER_OFFSET_PERCENT,
    CATEGORY_LINEAR,
    CATEGORY_INVERSE,
    CATEGORY_BOTH,
)


class ConfigValidator:
    """
    Validateur de configuration pour le bot Bybit.

    Cette classe contient toutes les règles de validation pour s'assurer
    que la configuration est cohérente et valide.
    """

    # Catégories valides
    VALID_CATEGORIES = {CATEGORY_LINEAR, CATEGORY_INVERSE, CATEGORY_BOTH}

    # Limites pour les poids
    MIN_WEIGHT_VALUE = 0
    MAX_WEIGHT_VALUE = 10000

    # Limites pour le trading
    MIN_ORDER_SIZE_USDT = 1
    MAX_ORDER_SIZE_USDT = 100000
    MIN_MAX_POSITIONS = 1
    MAX_MAX_POSITIONS = 10
    MIN_ORDER_OFFSET_PERCENT = 0.01
    MAX_ORDER_OFFSET_PERCENT = 10.0

    # Limites pour les symboles
    MIN_TOP_SYMBOLS = 1
    MAX_TOP_SYMBOLS = 100

    # Limites pour maker config
    MIN_RETRIES = 1
    MIN_REFRESH_INTERVAL_SECONDS = 0.1

    # Limites pour spot_hedge (en ratio, comme dans parameters.yaml)
    MIN_SPOT_HEDGE_OFFSET_PERCENT = 0.0
    MAX_SPOT_HEDGE_OFFSET_PERCENT = 1.0  # 1.0 = 100%
    MIN_SPOT_HEDGE_TIMEOUT_MINUTES = 1

    # Limites pour close orders (en ratio)
    MIN_CLOSE_ORDER_OFFSET_PERCENT = 0.0
    MAX_CLOSE_ORDER_OFFSET_PERCENT = 1.0  # 1.0 = 100%
    MIN_ORDER_TIMEOUT_MINUTES = 1

    def __init__(self):
        """Initialise le validateur."""
        pass

    def validate(self, config: Dict) -> None:
        """
        Valide la cohérence des paramètres de configuration.

        Args:
            config: Configuration à valider

        Raises:
            ValueError: Si des paramètres sont incohérents ou invalides
        """
        errors = []

        # Valider toutes les règles
        errors.extend(self._validate_funding_bounds(config))
        errors.extend(self._validate_volatility_bounds(config))
        errors.extend(self._validate_negative_values(config))
        errors.extend(self._validate_spread(config))
        errors.extend(self._validate_volume(config))
        errors.extend(self._validate_funding_time(config))
        errors.extend(self._validate_category(config))
        errors.extend(self._validate_limit(config))
        errors.extend(self._validate_volatility_ttl(config))
        errors.extend(self._validate_display_interval(config))
        errors.extend(self._validate_weights(config))
        errors.extend(self._validate_top_symbols(config))
        errors.extend(self._validate_auto_trading(config))
        errors.extend(self._validate_funding_threshold(config))

        # Valider les sous-configurations de auto_trading
        auto_trading = config.get("auto_trading", {})
        if isinstance(auto_trading, dict):
            errors.extend(self._validate_maker_config(auto_trading))
            errors.extend(self._validate_spot_hedge_config(auto_trading))

        # Lever une erreur si des problèmes ont été détectés
        if errors:
            error_msg = "⚠️ Configuration invalide détectée:\n" + "\n".join(
                f"  ❌ {error}" for error in errors
            )
            raise ValueError(error_msg)

    def _validate_funding_bounds(self, config: Dict) -> List[str]:
        """Valide les bornes de funding."""
        errors = []
        funding_min = config.get("funding_min")
        funding_max = config.get("funding_max")

        if funding_min is not None and funding_max is not None:
            if funding_min > funding_max:
                errors.append(
                    f"funding_min ({funding_min}) ne peut pas être "
                    f"supérieur à funding_max ({funding_max})"
                )

        return errors

    def _validate_volatility_bounds(self, config: Dict) -> List[str]:
        """Valide les bornes de volatilité."""
        errors = []
        volatility_min = config.get("volatility_min")
        volatility_max = config.get("volatility_max")

        if volatility_min is not None and volatility_max is not None:
            if volatility_min > volatility_max:
                errors.append(
                    f"volatility_min ({volatility_min}) ne peut pas être "
                    f"supérieur à volatility_max ({volatility_max})"
                )

        return errors

    def _validate_negative_values(self, config: Dict) -> List[str]:
        """Valide que certaines valeurs ne sont pas négatives."""
        errors = []

        for param in ["funding_min", "funding_max", "volatility_min", "volatility_max"]:
            value = config.get(param)
            if value is not None and value < 0:
                errors.append(f"{param} ne peut pas être négatif ({value})")

        return errors

    def _validate_spread(self, config: Dict) -> List[str]:
        """Valide le spread maximum."""
        errors = []
        spread_max = config.get("spread_max")

        if spread_max is not None:
            if spread_max < 0:
                errors.append(
                    f"spread_max ne peut pas être négatif ({spread_max})"
                )
            if spread_max > MAX_SPREAD_PERCENTAGE:
                errors.append(
                    f"spread_max trop élevé ({spread_max}), "
                    f"maximum recommandé: {MAX_SPREAD_PERCENTAGE} (100%)"
                )

        return errors

    def _validate_volume(self, config: Dict) -> List[str]:
        """Valide le volume minimum."""
        errors = []
        volume_min_millions = config.get("volume_min_millions")

        if volume_min_millions is not None and volume_min_millions < 0:
            errors.append(
                f"volume_min_millions ne peut pas être négatif "
                f"({volume_min_millions})"
            )

        return errors

    def _validate_funding_time(self, config: Dict) -> List[str]:
        """Valide les paramètres temporels de funding."""
        errors = []
        ft_min = config.get("funding_time_min_minutes")
        ft_max = config.get("funding_time_max_minutes")

        # Valider chaque paramètre individuellement
        for param, value in [
            ("funding_time_min_minutes", ft_min),
            ("funding_time_max_minutes", ft_max),
        ]:
            if value is not None:
                if value < 0:
                    errors.append(
                        f"{param} ne peut pas être négatif ({value})"
                    )
                if value > MAX_FUNDING_TIME_MINUTES:
                    errors.append(
                        f"{param} trop élevé ({value}), "
                        f"maximum: {MAX_FUNDING_TIME_MINUTES} (24h)"
                    )

        # Valider la cohérence entre min et max
        if ft_min is not None and ft_max is not None:
            if ft_min > ft_max:
                errors.append(
                    f"funding_time_min_minutes ({ft_min}) ne peut pas être "
                    f"supérieur à funding_time_max_minutes ({ft_max})"
                )

        return errors

    def _validate_category(self, config: Dict) -> List[str]:
        """Valide la catégorie."""
        errors = []
        categorie = config.get("categorie")

        if categorie not in self.VALID_CATEGORIES:
            errors.append(
                f"categorie invalide ({categorie}), valeurs autorisées: "
                f"{', '.join(sorted(self.VALID_CATEGORIES))}"
            )

        return errors

    def _validate_limit(self, config: Dict) -> List[str]:
        """Valide la limite de symboles."""
        errors = []
        limite = config.get("limite")

        if limite is not None:
            if limite < 1:
                errors.append(f"limite doit être positive ({limite})")
            if limite > MAX_LIMIT_RECOMMENDED:
                errors.append(
                    f"limite trop élevée ({limite}), "
                    f"maximum recommandé: {MAX_LIMIT_RECOMMENDED}"
                )

        return errors

    def _validate_volatility_ttl(self, config: Dict) -> List[str]:
        """Valide le TTL du cache de volatilité."""
        errors = []
        vol_ttl = config.get("volatility_ttl_sec")

        if vol_ttl is not None:
            if vol_ttl < MIN_VOLATILITY_TTL_SECONDS:
                errors.append(
                    f"volatility_ttl_sec trop faible ({vol_ttl}), "
                    f"minimum: {MIN_VOLATILITY_TTL_SECONDS} secondes"
                )
            if vol_ttl > MAX_VOLATILITY_TTL_SECONDS:
                errors.append(
                    f"volatility_ttl_sec trop élevé ({vol_ttl}), "
                    f"maximum: {MAX_VOLATILITY_TTL_SECONDS} secondes (1h)"
                )

        return errors

    def _validate_display_interval(self, config: Dict) -> List[str]:
        """Valide l'intervalle d'affichage."""
        errors = []
        display_interval = config.get("display_interval_seconds")

        if display_interval is not None:
            if display_interval < MIN_DISPLAY_INTERVAL_SECONDS:
                errors.append(
                    f"display_interval_seconds trop faible "
                    f"({display_interval}), "
                    f"minimum: {MIN_DISPLAY_INTERVAL_SECONDS} seconde"
                )
            if display_interval > MAX_DISPLAY_INTERVAL_SECONDS:
                errors.append(
                    f"display_interval_seconds trop élevé "
                    f"({display_interval}), "
                    f"maximum: {MAX_DISPLAY_INTERVAL_SECONDS} secondes (5min)"
                )

        return errors

    def _validate_weights(self, config: Dict) -> List[str]:
        """Valide les poids du système de scoring."""
        errors = []
        weights = config.get("weights", {})

        if not isinstance(weights, dict):
            errors.append("weights doit être un dictionnaire")
            return errors

        # Valider chaque poids
        weight_validations = [
            ("funding", DEFAULT_WEIGHT_FUNDING),
            ("volume", DEFAULT_WEIGHT_VOLUME),
            ("spread", DEFAULT_WEIGHT_SPREAD),
            ("volatility", DEFAULT_WEIGHT_VOLATILITY),
        ]

        for weight_name, default_value in weight_validations:
            weight_value = weights.get(weight_name)
            if weight_value is not None:
                if not isinstance(weight_value, (int, float)):
                    errors.append(
                        f"weights.{weight_name} doit être un nombre "
                        f"(reçu: {type(weight_value).__name__})"
                    )
                elif weight_value < self.MIN_WEIGHT_VALUE:
                    errors.append(
                        f"weights.{weight_name} trop faible ({weight_value}), "
                        f"minimum: {self.MIN_WEIGHT_VALUE}"
                    )
                elif weight_value > self.MAX_WEIGHT_VALUE:
                    errors.append(
                        f"weights.{weight_name} trop élevé ({weight_value}), "
                        f"maximum: {self.MAX_WEIGHT_VALUE}"
                    )

        return errors

    def _validate_top_symbols(self, config: Dict) -> List[str]:
        """Valide le nombre maximum de symboles après tri."""
        errors = []
        weights = config.get("weights", {})
        top_symbols = weights.get("top_symbols")

        if top_symbols is not None:
            if not isinstance(top_symbols, int):
                errors.append(
                    f"weights.top_symbols doit être un entier "
                    f"(reçu: {type(top_symbols).__name__})"
                )
            elif top_symbols < self.MIN_TOP_SYMBOLS:
                errors.append(
                    f"weights.top_symbols trop faible ({top_symbols}), "
                    f"minimum: {self.MIN_TOP_SYMBOLS}"
                )
            elif top_symbols > self.MAX_TOP_SYMBOLS:
                errors.append(
                    f"weights.top_symbols trop élevé ({top_symbols}), "
                    f"maximum: {self.MAX_TOP_SYMBOLS}"
                )

        return errors

    def _validate_auto_trading(self, config: Dict) -> List[str]:
        """Valide les paramètres de trading automatique."""
        errors = []
        auto_trading = config.get("auto_trading", {})

        if not isinstance(auto_trading, dict):
            errors.append("auto_trading doit être un dictionnaire")
            return errors

        # Valider enabled
        enabled = auto_trading.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            errors.append(
                f"auto_trading.enabled doit être un booléen "
                f"(reçu: {type(enabled).__name__})"
            )

        # Valider order_size_usdt
        order_size = auto_trading.get("order_size_usdt")
        if order_size is not None:
            if not isinstance(order_size, (int, float)):
                errors.append(
                    f"auto_trading.order_size_usdt doit être un nombre "
                    f"(reçu: {type(order_size).__name__})"
                )
            elif order_size < self.MIN_ORDER_SIZE_USDT:
                errors.append(
                    f"auto_trading.order_size_usdt trop faible ({order_size}), "
                    f"minimum: {self.MIN_ORDER_SIZE_USDT} USDT"
                )
            elif order_size > self.MAX_ORDER_SIZE_USDT:
                errors.append(
                    f"auto_trading.order_size_usdt trop élevé ({order_size}), "
                    f"maximum: {self.MAX_ORDER_SIZE_USDT} USDT"
                )

        # Valider max_positions
        max_positions = auto_trading.get("max_positions")
        if max_positions is not None:
            if not isinstance(max_positions, int):
                errors.append(
                    f"auto_trading.max_positions doit être un entier "
                    f"(reçu: {type(max_positions).__name__})"
                )
            elif max_positions < self.MIN_MAX_POSITIONS:
                errors.append(
                    f"auto_trading.max_positions trop faible ({max_positions}), "
                    f"minimum: {self.MIN_MAX_POSITIONS}"
                )
            elif max_positions > self.MAX_MAX_POSITIONS:
                errors.append(
                    f"auto_trading.max_positions trop élevé ({max_positions}), "
                    f"maximum: {self.MAX_MAX_POSITIONS}"
                )

        # Valider order_offset_percent
        # NOTE: Dans parameters.yaml, cette valeur est en pourcentage (0.01 = 0.01%)
        # ConfigValidator attend un pourcentage (0.01% à 10.0%)
        order_offset = auto_trading.get("order_offset_percent")
        if order_offset is not None:
            if not isinstance(order_offset, (int, float)):
                errors.append(
                    f"auto_trading.order_offset_percent doit être un nombre "
                    f"(reçu: {type(order_offset).__name__})"
                )
            elif order_offset < self.MIN_ORDER_OFFSET_PERCENT:
                errors.append(
                    f"auto_trading.order_offset_percent trop faible "
                    f"({order_offset}), "
                    f"minimum: {self.MIN_ORDER_OFFSET_PERCENT}%"
                )
            elif order_offset > self.MAX_ORDER_OFFSET_PERCENT:
                errors.append(
                    f"auto_trading.order_offset_percent trop élevé "
                    f"({order_offset}), "
                    f"maximum: {self.MAX_ORDER_OFFSET_PERCENT}%"
                )

        # Valider dry_run
        dry_run = auto_trading.get("dry_run")
        if dry_run is not None and not isinstance(dry_run, bool):
            errors.append(
                f"auto_trading.dry_run doit être un booléen "
                f"(reçu: {type(dry_run).__name__})"
            )

        # Valider shadow_mode
        shadow_mode = auto_trading.get("shadow_mode")
        if shadow_mode is not None and not isinstance(shadow_mode, bool):
            errors.append(
                f"auto_trading.shadow_mode doit être un booléen "
                f"(reçu: {type(shadow_mode).__name__})"
            )

        # Valider auto_close_after_funding
        auto_close = auto_trading.get("auto_close_after_funding")
        if auto_close is not None and not isinstance(auto_close, bool):
            errors.append(
                f"auto_trading.auto_close_after_funding doit être un booléen "
                f"(reçu: {type(auto_close).__name__})"
            )

        # Valider order_timeout_minutes
        order_timeout = auto_trading.get("order_timeout_minutes")
        if order_timeout is not None:
            if not isinstance(order_timeout, (int, float)):
                errors.append(
                    f"auto_trading.order_timeout_minutes doit être un nombre "
                    f"(reçu: {type(order_timeout).__name__})"
                )
            elif order_timeout < self.MIN_ORDER_TIMEOUT_MINUTES:
                errors.append(
                    f"auto_trading.order_timeout_minutes trop faible ({order_timeout}), "
                    f"minimum: {self.MIN_ORDER_TIMEOUT_MINUTES} minute(s)"
                )

        # Valider close_order_offset_percent (en ratio, comme dans parameters.yaml)
        # NOTE: Dans parameters.yaml, cette valeur est en pourcentage en ratio (0.05 = 0.05% = 0.0005)
        # On valide en ratio (0.0 à 1.0 = 0% à 100%)
        close_order_offset = auto_trading.get("close_order_offset_percent")
        if close_order_offset is not None:
            if not isinstance(close_order_offset, (int, float)):
                errors.append(
                    f"auto_trading.close_order_offset_percent doit être un nombre "
                    f"(reçu: {type(close_order_offset).__name__})"
                )
            elif close_order_offset < self.MIN_CLOSE_ORDER_OFFSET_PERCENT:
                errors.append(
                    f"auto_trading.close_order_offset_percent trop faible "
                    f"({close_order_offset}), minimum: {self.MIN_CLOSE_ORDER_OFFSET_PERCENT}"
                )
            elif close_order_offset > self.MAX_CLOSE_ORDER_OFFSET_PERCENT:
                errors.append(
                    f"auto_trading.close_order_offset_percent trop élevé "
                    f"({close_order_offset}), maximum: {self.MAX_CLOSE_ORDER_OFFSET_PERCENT} (100%)"
                )

        # Valider close_order_timeout_minutes
        close_order_timeout = auto_trading.get("close_order_timeout_minutes")
        if close_order_timeout is not None:
            if not isinstance(close_order_timeout, (int, float)):
                errors.append(
                    f"auto_trading.close_order_timeout_minutes doit être un nombre "
                    f"(reçu: {type(close_order_timeout).__name__})"
                )
            elif close_order_timeout < self.MIN_ORDER_TIMEOUT_MINUTES:
                errors.append(
                    f"auto_trading.close_order_timeout_minutes trop faible "
                    f"({close_order_timeout}), minimum: {self.MIN_ORDER_TIMEOUT_MINUTES} minute(s)"
                )

        return errors

    def _validate_maker_config(self, auto_trading: Dict) -> List[str]:
        """Valide la configuration maker."""
        errors = []
        maker = auto_trading.get('maker', {})

        if not isinstance(maker, dict):
            errors.append("auto_trading.maker doit être un dictionnaire")
            return errors

        # Valider max_retries_perp
        perp_retries = maker.get('max_retries_perp')
        if perp_retries is not None:
            if not isinstance(perp_retries, int):
                errors.append(
                    f"auto_trading.maker.max_retries_perp doit être un entier "
                    f"(reçu: {type(perp_retries).__name__})"
                )
            elif perp_retries < self.MIN_RETRIES:
                errors.append(
                    f"auto_trading.maker.max_retries_perp trop faible ({perp_retries}), "
                    f"minimum: {self.MIN_RETRIES}"
                )

        # Valider max_retries_spot
        spot_retries = maker.get('max_retries_spot')
        if spot_retries is not None:
            if not isinstance(spot_retries, int):
                errors.append(
                    f"auto_trading.maker.max_retries_spot doit être un entier "
                    f"(reçu: {type(spot_retries).__name__})"
                )
            elif spot_retries < self.MIN_RETRIES:
                errors.append(
                    f"auto_trading.maker.max_retries_spot trop faible ({spot_retries}), "
                    f"minimum: {self.MIN_RETRIES}"
                )

        # Valider refresh_interval_perp_seconds
        refresh_perp = maker.get('refresh_interval_perp_seconds')
        if refresh_perp is not None:
            if not isinstance(refresh_perp, (int, float)):
                errors.append(
                    f"auto_trading.maker.refresh_interval_perp_seconds doit être un nombre "
                    f"(reçu: {type(refresh_perp).__name__})"
                )
            elif refresh_perp < self.MIN_REFRESH_INTERVAL_SECONDS:
                errors.append(
                    f"auto_trading.maker.refresh_interval_perp_seconds trop faible "
                    f"({refresh_perp}), minimum: {self.MIN_REFRESH_INTERVAL_SECONDS} secondes"
                )

        # Valider refresh_interval_spot_seconds
        refresh_spot = maker.get('refresh_interval_spot_seconds')
        if refresh_spot is not None:
            if not isinstance(refresh_spot, (int, float)):
                errors.append(
                    f"auto_trading.maker.refresh_interval_spot_seconds doit être un nombre "
                    f"(reçu: {type(refresh_spot).__name__})"
                )
            elif refresh_spot < self.MIN_REFRESH_INTERVAL_SECONDS:
                errors.append(
                    f"auto_trading.maker.refresh_interval_spot_seconds trop faible "
                    f"({refresh_spot}), minimum: {self.MIN_REFRESH_INTERVAL_SECONDS} secondes"
                )

        return errors

    def _validate_spot_hedge_config(self, auto_trading: Dict) -> List[str]:
        """Valide la configuration spot_hedge."""
        errors = []
        spot_hedge = auto_trading.get('spot_hedge', {})

        if not isinstance(spot_hedge, dict):
            errors.append("auto_trading.spot_hedge doit être un dictionnaire")
            return errors

        # Valider enabled
        enabled = spot_hedge.get('enabled')
        if enabled is not None and not isinstance(enabled, bool):
            errors.append(
                f"auto_trading.spot_hedge.enabled doit être un booléen "
                f"(reçu: {type(enabled).__name__})"
            )

        # Valider offset_percent (en ratio, comme dans parameters.yaml)
        # NOTE: Dans parameters.yaml, cette valeur est en pourcentage en ratio (0.01 = 0.01% = 0.0001)
        # On valide en ratio (0.0 à 1.0 = 0% à 100%)
        offset = spot_hedge.get('offset_percent')
        if offset is not None:
            if not isinstance(offset, (int, float)):
                errors.append(
                    f"auto_trading.spot_hedge.offset_percent doit être un nombre "
                    f"(reçu: {type(offset).__name__})"
                )
            elif offset < self.MIN_SPOT_HEDGE_OFFSET_PERCENT:
                errors.append(
                    f"auto_trading.spot_hedge.offset_percent trop faible ({offset}), "
                    f"minimum: {self.MIN_SPOT_HEDGE_OFFSET_PERCENT}"
                )
            elif offset > self.MAX_SPOT_HEDGE_OFFSET_PERCENT:
                errors.append(
                    f"auto_trading.spot_hedge.offset_percent trop élevé ({offset}), "
                    f"maximum: {self.MAX_SPOT_HEDGE_OFFSET_PERCENT} (100%)"
                )

        # Valider timeout_minutes
        timeout = spot_hedge.get('timeout_minutes')
        if timeout is not None:
            if not isinstance(timeout, (int, float)):
                errors.append(
                    f"auto_trading.spot_hedge.timeout_minutes doit être un nombre "
                    f"(reçu: {type(timeout).__name__})"
                )
            elif timeout < self.MIN_SPOT_HEDGE_TIMEOUT_MINUTES:
                errors.append(
                    f"auto_trading.spot_hedge.timeout_minutes trop faible ({timeout}), "
                    f"minimum: {self.MIN_SPOT_HEDGE_TIMEOUT_MINUTES} minute(s)"
                )

        # Valider retry_on_reject
        retry_on_reject = spot_hedge.get('retry_on_reject')
        if retry_on_reject is not None and not isinstance(retry_on_reject, bool):
            errors.append(
                f"auto_trading.spot_hedge.retry_on_reject doit être un booléen "
                f"(reçu: {type(retry_on_reject).__name__})"
            )

        # Valider max_retry_offset_percent (en ratio)
        # NOTE: Dans parameters.yaml, cette valeur est en pourcentage en ratio (0.1 = 0.1% = 0.001)
        # On valide en ratio (0.0 à 1.0 = 0% à 100%)
        max_retry_offset = spot_hedge.get('max_retry_offset_percent')
        if max_retry_offset is not None:
            if not isinstance(max_retry_offset, (int, float)):
                errors.append(
                    f"auto_trading.spot_hedge.max_retry_offset_percent doit être un nombre "
                    f"(reçu: {type(max_retry_offset).__name__})"
                )
            elif max_retry_offset < self.MIN_SPOT_HEDGE_OFFSET_PERCENT:
                errors.append(
                    f"auto_trading.spot_hedge.max_retry_offset_percent trop faible "
                    f"({max_retry_offset}), minimum: {self.MIN_SPOT_HEDGE_OFFSET_PERCENT}"
                )
            elif max_retry_offset > self.MAX_SPOT_HEDGE_OFFSET_PERCENT:
                errors.append(
                    f"auto_trading.spot_hedge.max_retry_offset_percent trop élevé "
                    f"({max_retry_offset}), maximum: {self.MAX_SPOT_HEDGE_OFFSET_PERCENT} (100%)"
                )

        return errors

    def _validate_funding_threshold(self, config: Dict) -> List[str]:
        """Valide le seuil de détection du funding imminent."""
        errors = []
        threshold = config.get("funding_threshold_minutes")

        if threshold is not None:
            if not isinstance(threshold, (int, float)):
                errors.append(
                    f"funding_threshold_minutes doit être un nombre "
                    f"(reçu: {type(threshold).__name__})"
                )
            elif threshold < 0:
                errors.append(
                    f"funding_threshold_minutes ne peut pas être négatif "
                    f"({threshold})"
                )
            elif threshold > MAX_FUNDING_TIME_MINUTES:
                errors.append(
                    f"funding_threshold_minutes trop élevé ({threshold}), "
                    f"maximum: {MAX_FUNDING_TIME_MINUTES} minutes (24h)"
                )

        return errors

