#!/usr/bin/env python3
"""
Gestionnaire de configuration principal pour le bot Bybit.

Ce module orchestre le chargement et la validation de la configuration
en utilisant les modules spécialisés du package config.
"""

import yaml
from typing import Dict
from .settings_loader import get_settings
from .config_validator import ConfigValidator


class ConfigManager:
    """
    Gestionnaire de configuration pour le bot Bybit.
    
    Cette classe orchestre :
    - Le chargement de la configuration depuis YAML et ENV
    - La validation des paramètres
    - La fourniture des valeurs par défaut
    
    Hiérarchie de priorité :
    1. Variables d'environnement (.env) - PRIORITÉ MAXIMALE
    2. Fichier YAML (parameters.yaml) - PRIORITÉ MOYENNE
    3. Valeurs par défaut dans le code - PRIORITÉ MINIMALE
    """
    
    def __init__(self, config_path: str = "src/parameters.yaml", logger=None):
        """
        Initialise le gestionnaire de configuration.
        
        Args:
            config_path: Chemin vers le fichier de configuration YAML
            logger: Logger pour les messages (optionnel)
        """
        # Supporter plusieurs chemins possibles pour parameters.yaml
        import os
        if not os.path.exists(config_path):
            # Si le chemin par défaut n'existe pas, essayer d'autres chemins
            possible_paths = [
                "parameters.yaml",  # Même répertoire que le script
                "src/parameters.yaml",  # Depuis la racine du projet
                os.path.join(os.path.dirname(__file__), "..", "parameters.yaml"),  # Relatif au module config
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    config_path = path
                    break
        
        self.config_path = config_path
        self.config = {}
        self.logger = logger
        self.validator = ConfigValidator()
        
        # Initialiser le logger si non fourni
        if not self.logger:
            try:
                from ..logging_setup import setup_logging
            except ImportError:
                try:
                    from logging_setup import setup_logging
                except ImportError:
                    import logging
                    self.logger = logging.getLogger(__name__)
                else:
                    self.logger = setup_logging()
            else:
                self.logger = setup_logging()
    
    def load_and_validate_config(self) -> Dict:
        """
        Charge et valide la configuration avec hiérarchie claire.
        
        PRIORITÉ 1 (MAXIMALE) : Variables d'environnement (.env)
        PRIORITÉ 2 (MOYENNE) : Fichier YAML (parameters.yaml)
        PRIORITÉ 3 (MINIMALE) : Valeurs par défaut dans le code
        
        Returns:
            Dict: Configuration validée
            
        Raises:
            ValueError: Si la configuration est invalide
        """
        # ÉTAPE 1: Valeurs par défaut (priorité minimale)
        config = self._get_default_config()
        
        # ÉTAPE 2: Charger depuis le fichier YAML (priorité moyenne)
        self._load_yaml_config(config)
        
        # ÉTAPE 3: Appliquer les variables d'environnement (priorité maximale)
        self._apply_env_settings(config)
        
        # ÉTAPE 4: Valider la configuration finale
        self.validator.validate(config)
        
        self.config = config
        return config
    
    def _get_default_config(self) -> Dict:
        """
        Retourne la configuration par défaut.
        
        Returns:
            Dict: Configuration avec valeurs par défaut
        """
        return {
            "categorie": "linear",
            "funding_min": None,
            "funding_max": None,
            "volume_min_millions": None,
            "spread_max": None,
            "volatility_min": None,
            "volatility_max": None,
            "limite": 10,
            "volatility_ttl_sec": 120,
            "funding_time_min_minutes": None,
            "funding_time_max_minutes": None,
            "display_interval_seconds": 10,
        }
    
    def _load_yaml_config(self, config: Dict) -> None:
        """
        Charge la configuration depuis le fichier YAML.
        
        Args:
            config: Configuration à mettre à jour
        """
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                file_config = yaml.safe_load(f)
            if file_config:
                config.update(file_config)
        except FileNotFoundError:
            if self.logger:
                self.logger.warning(
                    f"⚠️ Fichier YAML non trouvé : {self.config_path} "
                    f"(utilisation des valeurs par défaut)"
                )
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ Erreur lors du chargement YAML : {e}")
    
    def _apply_env_settings(self, config: Dict) -> None:
        """
        Applique les variables d'environnement sur la configuration.
        
        Args:
            config: Configuration à mettre à jour
        """
        settings = get_settings()
        
        # Mapping entre les clés ENV et les clés de configuration
        env_mappings = {
            "spread_max": "spread_max",
            "volume_min_millions": "volume_min_millions",
            "volatility_min": "volatility_min",
            "volatility_max": "volatility_max",
            "funding_min": "funding_min",
            "funding_max": "funding_max",
            "category": "categorie",
            "limit": "limite",
            "volatility_ttl_sec": "volatility_ttl_sec",
            "funding_time_min_minutes": "funding_time_min_minutes",
            "funding_time_max_minutes": "funding_time_max_minutes",
            "display_interval_seconds": "display_interval_seconds",
        }
        
        # Appliquer les variables d'environnement si présentes
        for env_key, config_key in env_mappings.items():
            env_value = settings.get(env_key)
            if env_value is not None:
                config[config_key] = env_value
    
    def get_config(self) -> Dict:
        """
        Retourne la configuration actuelle.
        
        Returns:
            Dict: Configuration actuelle
        """
        return self.config.copy()
    
    def get_config_value(self, key: str, default=None):
        """
        Récupère une valeur de configuration spécifique.
        
        Args:
            key: Clé de configuration
            default: Valeur par défaut si la clé n'existe pas
            
        Returns:
            Valeur de configuration ou valeur par défaut
        """
        return self.config.get(key, default)

