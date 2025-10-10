#!/usr/bin/env python3
"""
Gestionnaire de configuration principal pour le bot Bybit.

╔═══════════════════════════════════════════════════════════════════╗
║                    📖 GUIDE DE LECTURE                            ║
╚═══════════════════════════════════════════════════════════════════╝

Ce fichier est le GESTIONNAIRE DE CONFIGURATION central du bot.
Il gère la hiérarchie de configuration et orchestre le chargement.

🔍 COMPRENDRE CE FICHIER EN 3 MINUTES :

1. __init__() (lignes 46-71) : Initialisation
   ├─> Recherche le fichier parameters.yaml
   └─> Initialise le logger et le validateur

2. load_and_validate_config() (lignes 73-100) : Chargement principal
   ├─> ÉTAPE 1 : Charge les valeurs par défaut
   ├─> ÉTAPE 2 : Surcharge avec le fichier YAML
   ├─> ÉTAPE 3 : Surcharge avec les variables ENV
   └─> ÉTAPE 4 : Valide la configuration finale

3. Méthodes privées de chargement (lignes 102-175)
   ├─> _get_default_config() : Valeurs par défaut
   ├─> _load_yaml_config() : Lecture du fichier YAML
   └─> _apply_env_settings() : Application des variables ENV

🎯 HIÉRARCHIE DE PRIORITÉ (du plus fort au plus faible) :
   1️⃣ Variables d'environnement (.env) → ÉCRASE TOUT
   2️⃣ Fichier YAML (parameters.yaml) → ÉCRASE les défauts
   3️⃣ Valeurs par défaut (code) → UTILISE si rien d'autre

📚 EXEMPLE D'UTILISATION :
   ```python
   config_manager = ConfigManager()
   config = config_manager.load_and_validate_config()
   spread_max = config_manager.get_config_value("spread_max")
   ```

⚡ RESPONSABILITÉ UNIQUE : Orchestration du chargement de configuration
   → Délègue la validation à ConfigValidator
   → Délègue la lecture ENV à settings_loader
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
        # Rechercher le fichier de configuration
        self.config_path = self._find_config_file(config_path)
        self.config = {}
        self.logger = self._init_logger(logger)
        self.validator = ConfigValidator()
    
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
        
        Cette méthode est tolérante aux erreurs : si le fichier n'existe pas
        ou est invalide, elle continue avec les valeurs par défaut.
        
        Args:
            config: Configuration à mettre à jour
        """
        import os
        
        try:
            # Vérifier que le fichier existe avant de tenter de le lire
            if not os.path.exists(self.config_path):
                self.logger.warning(
                    f"⚠️ Fichier YAML non trouvé : {self.config_path}\n"
                    f"   → Utilisation des valeurs par défaut uniquement"
                )
                return
            
            # Lire le fichier YAML
            with open(self.config_path, "r", encoding="utf-8") as f:
                file_config = yaml.safe_load(f)
            
            # Vérifier que le fichier n'est pas vide
            if not file_config:
                self.logger.warning(
                    f"⚠️ Fichier YAML vide : {self.config_path}\n"
                    f"   → Utilisation des valeurs par défaut uniquement"
                )
                return
            
            # Vérifier que c'est un dictionnaire
            if not isinstance(file_config, dict):
                self.logger.error(
                    f"❌ Format YAML invalide : {self.config_path}\n"
                    f"   → Le fichier doit contenir un dictionnaire de clés/valeurs"
                )
                return
            
            # Mettre à jour la configuration
            config.update(file_config)
            self.logger.debug(f"✓ Configuration YAML chargée : {len(file_config)} paramètres")
            
        except yaml.YAMLError as e:
            self.logger.error(
                f"❌ Erreur de syntaxe YAML dans {self.config_path} :\n"
                f"   {e}\n"
                f"   → Vérifiez l'indentation et la syntaxe du fichier"
            )
        except PermissionError:
            self.logger.error(
                f"❌ Permission refusée pour lire {self.config_path}\n"
                f"   → Vérifiez les permissions du fichier"
            )
        except Exception as e:
            self.logger.error(
                f"❌ Erreur inattendue lors du chargement YAML : {e}\n"
                f"   → Fichier : {self.config_path}"
            )
    
    def _apply_env_settings(self, config: Dict) -> None:
        """
        Applique les variables d'environnement sur la configuration.
        
        Les variables ENV ont la priorité maximale et écraseront
        toute valeur provenant du fichier YAML ou des défauts.
        
        Args:
            config: Configuration à mettre à jour
        """
        settings = get_settings()
        
        # Mapping entre les clés ENV et les clés de configuration
        # Format: "clé_env" -> "clé_config"
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
        
        # Compter le nombre de surcharges appliquées
        overrides_count = 0
        
        # Appliquer les variables d'environnement si présentes
        for env_key, config_key in env_mappings.items():
            env_value = settings.get(env_key)
            if env_value is not None:
                config[config_key] = env_value
                overrides_count += 1
                self.logger.debug(f"  ENV override: {config_key} = {env_value}")
        
        if overrides_count > 0:
            self.logger.debug(f"✓ {overrides_count} paramètre(s) surchargé(s) par variables ENV")
    
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

    # ===== MÉTHODES PRIVÉES D'INITIALISATION =====

    def _find_config_file(self, config_path: str) -> str:
        """
        Recherche le fichier de configuration YAML.
        
        Essaie plusieurs emplacements possibles dans cet ordre :
        1. Chemin fourni en paramètre
        2. parameters.yaml dans le répertoire courant
        3. src/parameters.yaml depuis la racine
        4. Chemin relatif au module config
        
        Args:
            config_path: Chemin initial à essayer
            
        Returns:
            str: Chemin vers le fichier trouvé (ou chemin initial si aucun trouvé)
        """
        import os
        
        # Si le chemin fourni existe, l'utiliser
        if os.path.exists(config_path):
            return config_path
        
        # Sinon, essayer d'autres emplacements
        possible_paths = [
            "parameters.yaml",  # Même répertoire que le script
            "src/parameters.yaml",  # Depuis la racine du projet
            os.path.join(os.path.dirname(__file__), "..", "parameters.yaml"),  # Relatif au module config
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # Si aucun fichier trouvé, retourner le chemin initial
        # (l'erreur sera gérée lors du chargement)
        return config_path

    def _init_logger(self, logger):
        """
        Initialise le logger de manière robuste.
        
        Essaie plusieurs stratégies d'import :
        1. Utiliser le logger fourni
        2. Importer depuis le package parent (..logging_setup)
        3. Importer depuis le répertoire courant (logging_setup)
        4. Fallback sur le logger standard Python
        
        Args:
            logger: Logger fourni (ou None)
            
        Returns:
            Logger initialisé
        """
        if logger:
            return logger
        
        # Essayer d'importer setup_logging
        try:
            from ..logging_setup import setup_logging
            return setup_logging()
        except ImportError:
            pass
        
        try:
            from logging_setup import setup_logging
            return setup_logging()
        except ImportError:
            pass
        
        # Fallback sur le logger standard
        import logging
        return logging.getLogger(__name__)

    # ===== MÉTHODES DE DIAGNOSTIC ET VALIDATION =====

    def get_config_info(self) -> Dict:
        """
        Retourne des informations détaillées sur la configuration.
        
        Returns:
            Dict contenant :
            - config_path: Chemin du fichier YAML
            - config_loaded: True si la configuration est chargée
            - config_keys: Liste des clés de configuration
            - sources: Informations sur les sources de configuration
        """
        import os
        return {
            "config_path": self.config_path,
            "config_file_exists": os.path.exists(self.config_path),
            "config_loaded": bool(self.config),
            "config_keys": list(self.config.keys()),
            "num_parameters": len(self.config),
        }

    def get_parameter_source(self, key: str) -> str:
        """
        Détermine la source d'un paramètre de configuration.
        
        Args:
            key: Clé du paramètre
            
        Returns:
            str: "env" (variable ENV), "yaml" (fichier), "default" (par défaut), ou "unknown"
        """
        settings = get_settings()
        default_config = self._get_default_config()
        
        # Mapping entre les clés de config et les clés ENV
        env_key_mapping = {
            "categorie": "category",
            "limite": "limit",
            "spread_max": "spread_max",
            "volume_min_millions": "volume_min_millions",
            "volatility_min": "volatility_min",
            "volatility_max": "volatility_max",
            "funding_min": "funding_min",
            "funding_max": "funding_max",
            "volatility_ttl_sec": "volatility_ttl_sec",
            "funding_time_min_minutes": "funding_time_min_minutes",
            "funding_time_max_minutes": "funding_time_max_minutes",
            "display_interval_seconds": "display_interval_seconds",
        }
        
        # Vérifier si le paramètre vient d'une variable ENV
        env_key = env_key_mapping.get(key, key)
        if settings.get(env_key) is not None:
            return "env"
        
        # Vérifier si différent de la valeur par défaut
        if key in self.config:
            if self.config[key] != default_config.get(key):
                return "yaml"
            return "default"
        
        return "unknown"

    def validate_current_config(self) -> bool:
        """
        Valide la configuration actuelle.
        
        Returns:
            bool: True si la configuration est valide
            
        Raises:
            ValueError: Si la configuration est invalide
        """
        if not self.config:
            raise ValueError("Configuration non chargée. Appelez load_and_validate_config() d'abord.")
        
        self.validator.validate(self.config)
        return True

    def print_config_summary(self) -> None:
        """
        Affiche un résumé de la configuration chargée.
        
        Utile pour le débogage et la vérification de la configuration.
        """
        info = self.get_config_info()
        
        self.logger.info("=" * 60)
        self.logger.info("RESUME DE LA CONFIGURATION")
        self.logger.info("=" * 60)
        self.logger.info(f"Fichier YAML: {info['config_path']}")
        self.logger.info(f"Fichier existe: {info['config_file_exists']}")
        self.logger.info(f"Configuration chargee: {info['config_loaded']}")
        self.logger.info(f"Nombre de parametres: {info['num_parameters']}")
        self.logger.info("")
        
        if self.config:
            self.logger.info("Parametres charges:")
            for key, value in sorted(self.config.items()):
                source = self.get_parameter_source(key)
                source_label = {
                    "env": "[ENV]",
                    "yaml": "[YAML]",
                    "default": "[Defaut]"
                }.get(source, "[Inconnu]")
                # Gérer les valeurs None pour le formatage
                value_str = str(value) if value is not None else "None"
                self.logger.info(f"  {key:30} = {value_str:20} {source_label}")
        
        self.logger.info("=" * 60)

