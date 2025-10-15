#!/usr/bin/env python3
"""
Implémentation concrète du filtre de symboles pour le bot Bybit.

Cette classe implémente l'interface BaseFilter pour le filtrage par funding,
volume et temps avant funding.
"""

import time
from typing import List, Tuple, Dict, Optional, Any
from .base_filter import BaseFilter


class SymbolFilter(BaseFilter):
    """
    Filtre de symboles pour le bot Bybit.

    Responsabilités :
    - Filtrage par funding, volume et fenêtre temporelle
    - Filtrage par spread
    - Calculs de temps de funding
    - Tri et sélection des symboles
    """

    def __init__(self, logger=None):
        """
        Initialise le filtre de symboles.

        Args:
            logger: Logger pour les messages (optionnel)
        """
        super().__init__(logger)

    def get_name(self) -> str:
        """Retourne le nom du filtre."""
        return "symbol_filter"


    def apply(
        self, symbols_data: List[Any], config: Dict[str, Any]
    ) -> List[Any]:
        """
        Applique le filtre de funding aux données de symboles.

        Args:
            symbols_data: Liste contenant (perp_data, funding_map,
            config_params)
            config: Configuration du filtre (non utilisée ici, les paramètres
            sont dans symbols_data)

        Returns:
            Liste des symboles filtrés
        """
        if len(symbols_data) < 3:
            raise ValueError(
                "symbols_data doit contenir (perp_data, funding_map, "
                "config_params)"
            )

        perp_data, funding_map, config_params = symbols_data

        # Extraire les paramètres de configuration
        funding_min = config_params.get("funding_min")
        funding_max = config_params.get("funding_max")
        volume_min_millions = config_params.get("volume_min_millions")
        limite = config_params.get("limite")
        funding_time_min_minutes = config_params.get(
            "funding_time_min_minutes"
        )
        funding_time_max_minutes = config_params.get(
            "funding_time_max_minutes"
        )

        # Appliquer le filtre de funding
        filtered_symbols = self.filter_by_funding(
            perp_data,
            funding_map,
            funding_min,
            funding_max,
            volume_min_millions,
            limite,
            funding_time_min_minutes=funding_time_min_minutes,
            funding_time_max_minutes=funding_time_max_minutes,
        )

        return filtered_symbols

    def filter_by_funding(
        self,
        perp_data: Dict,
        funding_map: Dict,
        funding_min: Optional[float],
        funding_max: Optional[float],
        volume_min_millions: Optional[float],
        limite: Optional[int],
        funding_time_min_minutes: Optional[int] = None,
        funding_time_max_minutes: Optional[int] = None,
    ) -> List[Tuple[str, float, float, str]]:
        """
        Filtre les symboles par funding, volume et fenêtre temporelle
        avant funding.

        Args:
            perp_data: Données des perpétuels (linear, inverse, total)
            funding_map: Dictionnaire des funding rates, volumes et temps
            de funding
            funding_min: Funding minimum en valeur absolue
            funding_max: Funding maximum en valeur absolue
            volume_min_millions: Volume minimum en millions
            limite: Limite du nombre d'éléments
            funding_time_min_minutes: Temps minimum en minutes avant
            prochain funding
            funding_time_max_minutes: Temps maximum en minutes avant
            prochain funding

        Returns:
            Liste des (symbol, funding, volume, funding_time_remaining) triés
        """
        # Récupérer tous les symboles perpétuels
        all_symbols = list(set(perp_data["linear"] + perp_data["inverse"]))

        # Déterminer le volume minimum à utiliser
        effective_volume_min = None
        if volume_min_millions is not None:
            effective_volume_min = (
                volume_min_millions * 1_000_000
            )  # Convertir en valeur brute

        # Filtrer par funding, volume et fenêtre temporelle
        filtered_symbols = []
        for symbol in all_symbols:
            if symbol in funding_map:
                data = funding_map[symbol]
                funding = data["funding"]
                volume = data["volume"]
                next_funding_time = data.get("next_funding_time")

                # Appliquer les bornes funding/volume (utiliser valeur absolue
                # pour funding)
                if funding_min is not None and abs(funding) < funding_min:
                    continue
                if funding_max is not None and abs(funding) > funding_max:
                    continue
                if (
                    effective_volume_min is not None
                    and volume < effective_volume_min
                ):
                    continue

                # Appliquer le filtre temporel si demandé
                if (
                    funding_time_min_minutes is not None
                    or funding_time_max_minutes is not None
                ):
                    # Utiliser la fonction centralisée pour calculer
                    # les minutes restantes
                    minutes_remaining = (
                        self.calculate_funding_minutes_remaining(
                            next_funding_time
                        )
                    )

                    # Si pas de temps valide alors qu'on filtre, rejeter
                    if minutes_remaining is None:
                        continue
                    if (
                        funding_time_min_minutes is not None
                        and minutes_remaining < float(funding_time_min_minutes)
                    ):
                        continue
                    if (
                        funding_time_max_minutes is not None
                        and minutes_remaining > float(funding_time_max_minutes)
                    ):
                        continue

                # Calculer le temps restant avant le prochain funding (formaté)
                funding_time_remaining = self.calculate_funding_time_remaining(
                    next_funding_time
                )

                filtered_symbols.append(
                    (symbol, funding, volume, funding_time_remaining)
                )

        # Trier par |funding| décroissant
        filtered_symbols.sort(key=lambda x: abs(x[1]), reverse=True)

        # Appliquer la limite
        if limite is not None:
            filtered_symbols = filtered_symbols[:limite]

        return filtered_symbols

    def filter_by_spread(
        self,
        symbols_data: List[Tuple],
        spread_data: Dict[str, float],
        spread_max: Optional[float],
    ) -> List[Tuple[str, float, float, str, float]]:
        """
        Filtre les symboles par spread maximum.

        Args:
            symbols_data: Liste des (symbol, funding, volume,
            funding_time_remaining)
            spread_data: Dictionnaire des spreads {symbol: spread_pct}
            spread_max: Spread maximum autorisé

        Returns:
            Liste des (symbol, funding, volume, funding_time_remaining,
            spread_pct) filtrés
        """
        if spread_max is None:
            # Pas de filtre de spread, ajouter 0.0 comme spread par défaut
            return [
                (symbol, funding, volume, funding_time_remaining, 0.0)
                for symbol, funding, volume, funding_time_remaining in (
                    symbols_data
                )
            ]

        filtered_symbols = []
        for symbol, funding, volume, funding_time_remaining in symbols_data:
            if symbol in spread_data:
                spread_pct = spread_data[symbol]
                if spread_pct <= spread_max:
                    filtered_symbols.append(
                        (
                            symbol,
                            funding,
                            volume,
                            funding_time_remaining,
                            spread_pct,
                        )
                    )

        return filtered_symbols

    def calculate_funding_time_remaining(self, next_funding_time) -> str:
        """
        Retourne "Xh Ym Zs" à partir d'un timestamp Bybit (ms) ou ISO.

        Args:
            next_funding_time: Timestamp du prochain funding (ms ou ISO string)

        Returns:
            str: Temps restant formaté ou "-" si invalide
        """
        if not next_funding_time:
            return "-"

        try:
            # Gérer les deux formats : timestamp ms ou ISO string
            if isinstance(next_funding_time, str):
                if next_funding_time.isdigit():
                    # Timestamp en ms
                    target_timestamp = int(next_funding_time) / 1000
                else:
                    # ISO string
                    from datetime import datetime

                    dt = datetime.fromisoformat(
                        next_funding_time.replace("Z", "+00:00")
                    )
                    target_timestamp = dt.timestamp()
            else:
                # Déjà un timestamp
                target_timestamp = (
                    float(next_funding_time) / 1000
                    if next_funding_time > 1e10
                    else float(next_funding_time)
                )

            current_timestamp = time.time()
            remaining_seconds = target_timestamp - current_timestamp

            if remaining_seconds <= 0:
                return "0s"

            hours = int(remaining_seconds // 3600)
            minutes = int((remaining_seconds % 3600) // 60)
            seconds = int(remaining_seconds % 60)

            if hours > 0:
                return f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"

        except (ValueError, TypeError, OverflowError) as e:
            self.logger.warning(f"⚠️ Erreur calcul temps funding: {e}")
            return "-"

    def calculate_funding_minutes_remaining(
        self, next_funding_time
    ) -> Optional[float]:
        """
        Calcule les minutes restantes avant le prochain funding.

        Args:
            next_funding_time: Timestamp du prochain funding

        Returns:
            float: Minutes restantes ou None si erreur
        """
        if not next_funding_time:
            return None

        try:
            # Gérer les deux formats : timestamp ms ou ISO string
            if isinstance(next_funding_time, str):
                if next_funding_time.isdigit():
                    # Timestamp en ms
                    target_timestamp = int(next_funding_time) / 1000
                else:
                    # ISO string
                    from datetime import datetime

                    dt = datetime.fromisoformat(
                        next_funding_time.replace("Z", "+00:00")
                    )
                    target_timestamp = dt.timestamp()
            else:
                # Déjà un timestamp
                target_timestamp = (
                    float(next_funding_time) / 1000
                    if next_funding_time > 1e10
                    else float(next_funding_time)
                )

            current_timestamp = time.time()
            remaining_seconds = target_timestamp - current_timestamp
            remaining_minutes = remaining_seconds / 60

            return remaining_minutes if remaining_minutes > 0 else 0

        except (ValueError, TypeError, OverflowError):
            return None

    def separate_symbols_by_category(
        self, symbols_data: List[Tuple], symbol_categories: Dict[str, str]
    ) -> Tuple[List[str], List[str]]:
        """
        Sépare les symboles par catégorie (linear/inverse).

        Args:
            symbols_data: Liste des données de symboles
            symbol_categories: Mapping des catégories de symboles

        Returns:
            Tuple[linear_symbols, inverse_symbols]
        """
        from instruments import category_of_symbol

        linear_symbols = []
        inverse_symbols = []

        # Déterminer la structure des données selon la longueur des tuples
        if symbols_data and len(symbols_data[0]) >= 4:
            # Format: (symbol, funding, volume, funding_time_remaining, ...)
            symbols = [item[0] for item in symbols_data]
        else:
            # Format simple: [symbol, ...]
            symbols = (
                symbols_data
                if isinstance(symbols_data[0], str)
                else [item[0] for item in symbols_data]
            )

        for symbol in symbols:
            category = category_of_symbol(symbol, symbol_categories)
            if category == "linear":
                linear_symbols.append(symbol)
            elif category == "inverse":
                inverse_symbols.append(symbol)

        return linear_symbols, inverse_symbols

    def check_candidate_filters(
        self,
        symbol: str,
        funding_map: Dict,
        funding_min: Optional[float],
        funding_max: Optional[float],
        volume_min_millions: Optional[float],
        funding_time_max_minutes: Optional[int],
    ) -> bool:
        """
        Vérifie si un symbole candidat passe les filtres de base.

        Args:
            symbol: Symbole à vérifier
            funding_map: Dictionnaire des données de funding
            funding_min: Funding minimum
            funding_max: Funding maximum
            volume_min_millions: Volume minimum en millions
            funding_time_max_minutes: Temps maximum avant funding en minutes

        Returns:
            True si le symbole passe les filtres
        """
        try:
            data = funding_map.get(symbol)
            if not data or len(data) < 3:
                return False

            funding = data[0]
            volume = data[1]
            funding_time_remaining = data[2]

            # Vérifier que les données sont valides
            if funding is None or volume is None:
                return False

            # Vérifier le funding
            if funding_min is not None and abs(funding) < funding_min:
                return False
            if funding_max is not None and abs(funding) > funding_max:
                return False

            # Vérifier le volume
            if (
                volume_min_millions is not None
                and volume < volume_min_millions
            ):
                return False

            # Vérifier le temps avant funding
            if funding_time_max_minutes is not None:
                try:
                    # Convertir le temps restant en minutes
                    if (
                        isinstance(funding_time_remaining, str)
                        and funding_time_remaining != "-"
                    ):
                        # Format "Xh Ym Zs" -> minutes
                        time_parts = funding_time_remaining.split()
                        total_minutes = 0
                        for part in time_parts:
                            if part.endswith("h"):
                                total_minutes += int(part[:-1]) * 60
                            elif part.endswith("m"):
                                total_minutes += int(part[:-1])
                            elif part.endswith("s"):
                                total_minutes += int(part[:-1]) / 60

                        if total_minutes > funding_time_max_minutes:
                            return False
                except (ValueError, AttributeError):
                    pass

            return True

        except Exception:
            # Ignorer silencieusement les erreurs de vérification des candidats
            # (cela se produit normalement pour les symboles sans données
            # complètes)
            return False

    def check_realtime_filters(
        self,
        symbol: str,
        ticker_data: dict,
        funding_min: Optional[float],
        funding_max: Optional[float],
        volume_min_millions: Optional[float],
    ) -> bool:
        """
        Vérifie si un symbole passe les filtres en temps réel.

        Args:
            symbol: Symbole à vérifier
            ticker_data: Données du ticker reçues via WebSocket
            funding_min: Funding minimum
            funding_max: Funding maximum
            volume_min_millions: Volume minimum en millions

        Returns:
            True si le symbole passe les filtres
        """
        try:
            # Extraire les données du ticker
            funding_rate = ticker_data.get("fundingRate")
            volume24h = ticker_data.get("volume24h")

            if funding_rate is None or volume24h is None:
                return False

            funding = float(funding_rate)
            volume = float(volume24h)

            # Vérifier le funding
            if funding_min is not None and abs(funding) < funding_min:
                return False
            if funding_max is not None and abs(funding) > funding_max:
                return False

            # Vérifier le volume
            if (
                volume_min_millions is not None
                and volume < volume_min_millions
            ):
                return False

            return True

        except (ValueError, TypeError) as e:
            self.logger.warning(f"⚠️ Erreur données ticker {symbol}: {e}")
            return False

    def build_funding_data_dict(
        self, symbols_data: List[Tuple]
    ) -> Dict[str, Dict]:
        """
        Construit un dictionnaire de données de funding à partir des
        symboles filtrés.

        Args:
            symbols_data: Liste des tuples (symbol, funding, volume,
            funding_time_remaining, ...)

        Returns:
            Dictionnaire {symbol: {funding, volume, funding_time_remaining,
            spread_pct, volatility_pct}}
        """
        funding_data = {}

        for symbol_data in symbols_data:
            if len(symbol_data) >= 4:
                symbol = symbol_data[0]
                funding = symbol_data[1]
                volume = symbol_data[2]
                funding_time_remaining = symbol_data[3]

                # Ajouter les données optionnelles selon la longueur du tuple
                spread_pct = symbol_data[4] if len(symbol_data) > 4 else 0.0
                volatility_pct = (
                    symbol_data[5] if len(symbol_data) > 5 else None
                )

                funding_data[symbol] = {
                    "funding": funding,
                    "volume": volume,
                    "funding_time_remaining": funding_time_remaining,
                    "spread_pct": spread_pct,
                    "volatility_pct": volatility_pct,
                }

        return funding_data
