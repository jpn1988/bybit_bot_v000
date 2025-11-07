#!/usr/bin/env python3
"""
Filtre de symboles basé sur la volatilité.

Cette classe est responsable du filtrage des symboles selon
leurs critères de volatilité.
"""

from typing import Optional, Dict, List, Tuple
from logging_setup import setup_logging


class VolatilityFilter:
    """
    Filtre de symboles basé sur la volatilité.

    Responsabilité unique : Filtrer les symboles selon des critères de volatilité.
    """

    def __init__(self, logger=None):
        """
        Initialise le filtre de volatilité.

        Args:
            logger: Logger pour les messages (optionnel)
        """
        self.logger = logger or setup_logging()

    def filter_symbols(
        self,
        symbols_data: List[Tuple[str, float, float, str, float]],
        volatilities: Dict[str, Optional[float]],
        volatility_min: Optional[float],
        volatility_max: Optional[float],
    ) -> List[Tuple[str, float, float, str, float, Optional[float]]]:
        """
        Filtre les symboles selon leurs critères de volatilité.

        Args:
            symbols_data: Liste des (symbol, funding, volume,
                funding_time_remaining, spread_pct)
            volatilities: Dictionnaire {symbol: volatility_pct}
            volatility_min: Seuil minimum de volatilité ou None
            volatility_max: Seuil maximum de volatilité ou None

        Returns:
            Liste filtrée des (symbol, funding, volume, funding_time_remaining,
                spread_pct, volatility_pct)
        """
        filtered_symbols = []
        rejected_count = 0

        for (
            symbol,
            funding,
            volume,
            funding_time_remaining,
            spread_pct,
        ) in symbols_data:
            vol_pct = volatilities.get(symbol)

            # Vérifier si le symbole passe les filtres
            if self._should_reject_symbol(
                symbol, vol_pct, volatility_min, volatility_max
            ):
                rejected_count += 1
                continue

            # Ajouter le symbole avec sa volatilité
            filtered_symbols.append(
                (
                    symbol,
                    funding,
                    volume,
                    funding_time_remaining,
                    spread_pct,
                    vol_pct,
                )
            )

        # Logger les résultats du filtrage
        if volatility_min is not None or volatility_max is not None:
            self.logger.info(
                f"📊 Filtrage volatilité: {len(filtered_symbols)} symboles passent, "
                f"{rejected_count} rejetés"
            )

        return filtered_symbols

    def _should_reject_symbol(
        self,
        symbol: str,
        vol_pct: Optional[float],
        volatility_min: Optional[float],
        volatility_max: Optional[float],
    ) -> bool:
        """
        Détermine si un symbole doit être rejeté selon les critères de volatilité.

        Args:
            symbol: Nom du symbole
            vol_pct: Volatilité du symbole
            volatility_min: Seuil minimum
            volatility_max: Seuil maximum

        Returns:
            True si le symbole doit être rejeté
        """
        # Pas de filtres actifs - accepter tous les symboles
        if volatility_min is None and volatility_max is None:
            return False

        # Symbole sans volatilité calculée - le rejeter si des filtres sont actifs
        if vol_pct is None:
            self.logger.debug(
                f"Rejet {symbol}: volatilité non calculée (filtres actifs)"
            )
            return True

        # Vérifier le seuil minimum
        if volatility_min is not None and vol_pct < volatility_min:
            self.logger.debug(
                f"Rejet {symbol}: volatilité {vol_pct:.4f} < min {volatility_min}"
            )
            return True

        # Vérifier le seuil maximum
        if volatility_max is not None and vol_pct > volatility_max:
            self.logger.debug(
                f"Rejet {symbol}: volatilité {vol_pct:.4f} > max {volatility_max}"
            )
            return True

        return False

    def get_statistics(
        self,
        volatilities: Dict[str, Optional[float]],
    ) -> Dict[str, float]:
        """
        Calcule des statistiques sur les volatilités.

        Args:
            volatilities: Dictionnaire {symbol: volatility_pct}

        Returns:
            Dictionnaire avec min, max, moyenne des volatilités
        """
        # Filtrer les valeurs non None
        valid_vols = [v for v in volatilities.values() if v is not None]

        if not valid_vols:
            return {
                "count": 0,
                "min": 0.0,
                "max": 0.0,
                "average": 0.0,
            }

        return {
            "count": len(valid_vols),
            "min": min(valid_vols),
            "max": max(valid_vols),
            "average": sum(valid_vols) / len(valid_vols),
        }

