#!/usr/bin/env python3
"""
Helper pour le calcul des poids et le tri intelligent de la watchlist.

Cette classe extrait la logique de calcul des poids et de tri
du WatchlistManager pour améliorer la lisibilité et la maintenabilité.
"""

import math
from typing import List, Tuple, Dict, Optional
from logging_setup import setup_logging


class WeightCalculator:
    """
    Helper pour calculer les poids et trier les opportunités.

    Responsabilités :
    - Calcul du score pondéré pour chaque opportunité
    - Tri des opportunités par poids décroissant
    - Limitation au top N symboles
    - Logging du classement final
    """

    def __init__(self, logger=None):
        """
        Initialise le calculateur de poids.

        Args:
            logger: Logger pour les messages (optionnel)
        """
        self.logger = logger or setup_logging()

    def calculate_weight(self, opportunity: Dict, weights_config: Dict) -> float:
        """
        Calcule le score pondéré pour une opportunité.

        Args:
            opportunity: Dictionnaire contenant les données de l'opportunité
            weights_config: Configuration des poids depuis parameters.yaml

        Returns:
            float: Score pondéré calculé
        """
        try:
            # Extraire les données de l'opportunité
            funding_rate = opportunity.get('funding', 0.0)
            volume = opportunity.get('volume', 0.0)
            spread = opportunity.get('spread', 0.0)
            volatility = opportunity.get('volatility', 0.0)

            # Extraire les poids de configuration
            funding_weight = weights_config.get('funding', 10.0)
            volume_weight = weights_config.get('volume', 0.5)
            spread_weight = weights_config.get('spread', 5.0)
            volatility_weight = weights_config.get('volatility', 2.0)

            # Calculer le score selon la formule pondérée
            score = (
                abs(funding_rate) * funding_weight
                + math.log(volume + 1) * volume_weight
                - spread * spread_weight
                - volatility * volatility_weight
            )

            return round(score, 2)

        except Exception as e:
            self.logger.warning(f"⚠️ Erreur calcul poids pour {opportunity.get('symbol', 'inconnu')}: {e}")
            return 0.0

    def apply_weighting_to_opportunities(
        self, 
        opportunities: List[Tuple], 
        weights_config: Dict,
        symbol_categories: Dict
    ) -> List[Dict]:
        """
        Applique le calcul de poids à toutes les opportunités.

        Args:
            opportunities: Liste des opportunités (tuples)
            weights_config: Configuration des poids
            symbol_categories: Mapping des catégories de symboles

        Returns:
            List[Dict]: Liste des opportunités avec poids calculé
        """
        weighted_opportunities = []

        for opportunity_tuple in opportunities:
            # Convertir le tuple en dictionnaire
            if len(opportunity_tuple) >= 5:
                symbol, funding, volume, funding_time, spread = opportunity_tuple[:5]
                volatility = opportunity_tuple[5] if len(opportunity_tuple) > 5 else 0.0
            else:
                # Format par défaut si données incomplètes
                symbol = opportunity_tuple[0] if len(opportunity_tuple) > 0 else "UNKNOWN"
                funding = opportunity_tuple[1] if len(opportunity_tuple) > 1 else 0.0
                volume = opportunity_tuple[2] if len(opportunity_tuple) > 2 else 0.0
                funding_time = opportunity_tuple[3] if len(opportunity_tuple) > 3 else 0
                spread = opportunity_tuple[4] if len(opportunity_tuple) > 4 else 0.0
                volatility = 0.0

            # Créer le dictionnaire d'opportunité
            opportunity_dict = {
                'symbol': symbol,
                'funding': funding,
                'volume': volume,
                'funding_time': funding_time,
                'spread': spread,
                'volatility': volatility,
                'category': symbol_categories.get(symbol, 'unknown')
            }

            # Calculer le poids
            weight = self.calculate_weight(opportunity_dict, weights_config)
            opportunity_dict['weight'] = weight

            weighted_opportunities.append(opportunity_dict)

        return weighted_opportunities

    def sort_by_weight(self, weighted_opportunities: List[Dict]) -> List[Dict]:
        """
        Trie les opportunités par poids décroissant.

        Args:
            weighted_opportunities: Liste des opportunités avec poids

        Returns:
            List[Dict]: Opportunités triées par poids décroissant
        """
        return sorted(weighted_opportunities, key=lambda x: x['weight'], reverse=True)

    def limit_to_top_symbols(
        self, 
        sorted_opportunities: List[Dict], 
        top_symbols: int
    ) -> List[Dict]:
        """
        Limite la liste aux top N symboles.

        Args:
            sorted_opportunities: Opportunités triées par poids
            top_symbols: Nombre maximum de symboles à conserver

        Returns:
            List[Dict]: Liste limitée aux top N symboles
        """
        if top_symbols is None or top_symbols <= 0:
            return sorted_opportunities

        return sorted_opportunities[:top_symbols]

    def log_ranking(self, final_opportunities: List[Dict]):
        """
        Affiche le classement final dans les logs.

        Args:
            final_opportunities: Opportunités finales triées
        """
        # Logs supprimés pour réduire l'encombrement du terminal
        pass

    def process_weighted_ranking(
        self, 
        opportunities: List[Tuple], 
        weights_config: Dict,
        symbol_categories: Dict
    ) -> List[Dict]:
        """
        Traite complètement le système de poids : calcul, tri et limitation.

        Args:
            opportunities: Liste des opportunités (tuples)
            weights_config: Configuration des poids
            symbol_categories: Mapping des catégories de symboles

        Returns:
            List[Dict]: Opportunités finales triées et limitées
        """
        if not opportunities:
            return []

        # 1. Calculer les poids
        weighted_opportunities = self.apply_weighting_to_opportunities(
            opportunities, weights_config, symbol_categories
        )

        # 2. Trier par poids décroissant
        sorted_opportunities = self.sort_by_weight(weighted_opportunities)

        # 3. Limiter aux top N symboles
        top_symbols = weights_config.get('top_symbols', 3)
        final_opportunities = self.limit_to_top_symbols(
            sorted_opportunities, top_symbols
        )

        # 4. Logger le classement
        self.log_ranking(final_opportunities)

        return final_opportunities
