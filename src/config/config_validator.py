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
)


class ConfigValidator:
    """
    Validateur de configuration pour le bot Bybit.
    
    Cette classe contient toutes les règles de validation pour s'assurer
    que la configuration est cohérente et valide.
    """
    
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
        
        # Lever une erreur si des problèmes ont été détectés
        if errors:
            error_msg = "Configuration invalide détectée:\n" + "\n".join(
                f"  - {error}" for error in errors
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
        
        if categorie not in ["linear", "inverse", "both"]:
            errors.append(
                f"categorie invalide ({categorie}), valeurs autorisées: "
                f"linear, inverse, both"
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

