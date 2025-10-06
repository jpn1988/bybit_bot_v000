#!/usr/bin/env python3
"""
Module de configuration unifié pour le bot Bybit.

Ce module consolide :
- Le chargement des variables d'environnement (.env)
- Le chargement de la configuration YAML
- La validation des paramètres
- Les constantes et limites du système

HIÉRARCHIE DE PRIORITÉ :
1. Variables d'environnement (.env) - PRIORITÉ MAXIMALE
2. Fichier YAML (parameters.yaml) - PRIORITÉ MOYENNE  
3. Valeurs par défaut - PRIORITÉ MINIMALE
"""

import os
import yaml
from typing import Dict, Optional
from dotenv import load_dotenv

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

# Constantes pour les limites et seuils
MAX_LIMIT_RECOMMENDED = 1000
MAX_SPREAD_PERCENTAGE = 1.0  # 100%
MAX_FUNDING_TIME_MINUTES = 1440  # 24 heures
MIN_VOLATILITY_TTL_SECONDS = 10
MAX_VOLATILITY_TTL_SECONDS = 3600  # 1 heure
MIN_DISPLAY_INTERVAL_SECONDS = 1
MAX_DISPLAY_INTERVAL_SECONDS = 300  # 5 minutes
MAX_WORKERS_THREADPOOL = 2


def get_settings() -> Dict:
    """
    Retourne un dictionnaire avec les paramètres de configuration.
    Valide également les variables d'environnement pour détecter 
    les fautes de frappe.
    
    Returns:
        dict: Dictionnaire contenant les paramètres de configuration
    """
    # Liste des variables d'environnement valides pour la configuration
    valid_env_vars = {
        "BYBIT_API_KEY", "BYBIT_API_SECRET", "TESTNET", "TIMEOUT", "LOG_LEVEL",
        "SPREAD_MAX", "VOLUME_MIN_MILLIONS", "VOLATILITY_MIN", "VOLATILITY_MAX",
        "FUNDING_MIN", "FUNDING_MAX", "CATEGORY", "LIMIT", "VOLATILITY_TTL_SEC",
        "FUNDING_TIME_MIN_MINUTES", "FUNDING_TIME_MAX_MINUTES", "WS_PRIV_CHANNELS",
        "DISPLAY_INTERVAL_SECONDS",
        # Variables de rate limiting public 
        # (utilisées par volatility.get_async_rate_limiter)
        "PUBLIC_HTTP_MAX_CALLS_PER_SEC", "PUBLIC_HTTP_WINDOW_SECONDS",
    }
    
    # Variables d'environnement à ignorer complètement (faux positifs)
    ignored_vars = {
        "FPS_BROWSER_APP_PROFILE_STRING",  # Variable système Windows
        "FPS_BROWSER_APP_PROFILE_STRING_OLD",  # Autres variantes possibles
    }
    
    # Détecter les variables d'environnement inconnues
    all_env_vars = set(os.environ.keys())
    unknown_vars = all_env_vars - valid_env_vars - ignored_vars
    
    # Filtrer les variables système et les variables non liées au bot
    bot_related_unknown = []
    for var in unknown_vars:
        # Ignorer les variables système Windows/Python et les variables 
        # non liées au bot
        if not any(prefix in var.upper() for prefix in [
            "PATH", "PYTHON", "WINDOWS", "USER", "HOME", "TEMP", "TMP",
            "PROGRAM", "SYSTEM", "ALLUSER", "APPDATA", "LOCALAPPDATA",
            "COMPUTERNAME", "USERNAME", "USERPROFILE", "WINDIR", "COMSPEC",
            "PATHEXT", "PROCESSOR", "NUMBER_OF_PROCESSORS", "OS", "DRIVE",
            "VIRTUAL_ENV", "CONDA", "PIP", "NODE", "NPM", "GIT", "SSH",
            "DOCKER", "KUBERNETES", "AWS", "AZURE", "GOOGLE", "JAVA",
            "MAVEN", "GRADLE", "NODEJS", "NPM", "YARN", "BOWER", "FPS",
            "BROWSER", "APP", "PROFILE", "STRING"
        ]):
            # Vérifier si la variable semble liée au bot 
            # (contient des mots-clés)
            if any(keyword in var.upper() for keyword in [
                "BYBIT", "FUNDING", "VOLATILITY", "SPREAD", "VOLUME", "CATEGORY",
                "LIMIT", "TTL", "TIME", "MIN", "MAX", "CHANNELS", "WS", "PRIV"
            ]):
                bot_related_unknown.append(var)
    
    # Logger les variables inconnues liées au bot
    if bot_related_unknown:
        # Afficher directement sur stderr pour être sûr que le message 
        # soit visible
        import sys
        for var in bot_related_unknown:
            print(
                f"⚠️ Variable d'environnement inconnue ignorée: {var}", 
                file=sys.stderr
            )
            valid_vars_str = ', '.join(sorted(valid_env_vars))
            print(f"💡 Variables valides: {valid_vars_str}", file=sys.stderr)
        
        # Essayer aussi avec le logger si disponible
        try:
            import logging
            logger = logging.getLogger(__name__)
            for var in bot_related_unknown:
                logger.warning(
                    f"⚠️ Variable d'environnement inconnue ignorée: {var}"
                )
                valid_vars_str = ', '.join(sorted(valid_env_vars))
                logger.warning(f"💡 Variables valides: {valid_vars_str}")
        except Exception:
            pass  # Le message a déjà été affiché sur stderr
    
    # Récupérer les clés API et convertir les chaînes vides en None
    api_key = os.getenv("BYBIT_API_KEY") or None
    api_secret = os.getenv("BYBIT_API_SECRET") or None
    
    # Récupérer les nouvelles variables d'environnement pour les filtres
    spread_max = os.getenv("SPREAD_MAX")
    volume_min_millions = os.getenv("VOLUME_MIN_MILLIONS")
    volatility_min = os.getenv("VOLATILITY_MIN")
    volatility_max = os.getenv("VOLATILITY_MAX")
    # Variables supplémentaires alignées avec le README
    funding_min = os.getenv("FUNDING_MIN")
    funding_max = os.getenv("FUNDING_MAX")
    category = os.getenv("CATEGORY")  # linear | inverse | both
    limit = os.getenv("LIMIT")
    volatility_ttl_sec = os.getenv("VOLATILITY_TTL_SEC")
    # Nouveaux paramètres de filtre temporel funding
    funding_time_min_minutes = os.getenv("FUNDING_TIME_MIN_MINUTES")
    funding_time_max_minutes = os.getenv("FUNDING_TIME_MAX_MINUTES")
    # Configuration d'affichage
    display_interval_seconds = os.getenv("DISPLAY_INTERVAL_SECONDS")
    
    # Convertir en float/int si présentes, sinon None (avec gestion d'erreur)
    def safe_float(value):
        try:
            return float(value) if value else None
        except (ValueError, TypeError):
            return None
    
    def safe_int(value):
        try:
            return int(value) if value else None
        except (ValueError, TypeError):
            return None
    
    spread_max = safe_float(spread_max)
    volume_min_millions = safe_float(volume_min_millions)
    volatility_min = safe_float(volatility_min)
    volatility_max = safe_float(volatility_max)
    funding_min = safe_float(funding_min)
    funding_max = safe_float(funding_max)
    limit = safe_int(limit)
    volatility_ttl_sec = safe_int(volatility_ttl_sec)
    # Conversions minutes → int
    funding_time_min_minutes = safe_int(funding_time_min_minutes)
    funding_time_max_minutes = safe_int(funding_time_max_minutes)
    display_interval_seconds = safe_int(display_interval_seconds)
    
    return {
        "testnet": os.getenv("TESTNET", "true").lower() == "true",
        "timeout": safe_int(os.getenv("TIMEOUT", "10")) or 10,
        "log_level": os.getenv("LOG_LEVEL", "INFO").upper(),
        "api_key": api_key,
        "api_secret": api_secret,
        "spread_max": spread_max,
        "volume_min_millions": volume_min_millions,
        "volatility_min": volatility_min,
        "volatility_max": volatility_max,
        # Ajouts alignés README
        "funding_min": funding_min,
        "funding_max": funding_max,
        "category": category,
        "limit": limit,
        "volatility_ttl_sec": volatility_ttl_sec,
        # Nouveaux paramètres temporels
        "funding_time_min_minutes": funding_time_min_minutes,
        "funding_time_max_minutes": funding_time_max_minutes,
        # Configuration d'affichage
        "display_interval_seconds": display_interval_seconds,
    }


class UnifiedConfigManager:
    """
    Gestionnaire de configuration unifié pour le bot Bybit.
    
    Responsabilités :
    - Chargement de la configuration depuis fichier YAML et variables d'environnement
    - Validation des paramètres de configuration
    - Fourniture des valeurs par défaut
    """
    
    def __init__(self, config_path: str = "src/parameters.yaml", logger=None):
        """
        Initialise le gestionnaire de configuration unifié.
        
        Args:
            config_path (str): Chemin vers le fichier de configuration YAML
            logger: Logger pour les messages (optionnel)
        """
        self.config_path = config_path
        self.config = {}
        self.logger = logger
        
        # Initialiser le logger si non fourni
        if not self.logger:
            try:
                from .logging_setup import setup_logging
            except ImportError:
                from logging_setup import setup_logging
            self.logger = setup_logging()
    
    def load_and_validate_config(self) -> Dict:
        """
        Charge et valide la configuration avec hiérarchie claire :
        
        PRIORITÉ 1 (MAXIMALE) : Variables d'environnement (.env)
        PRIORITÉ 2 (MOYENNE) : Fichier YAML (parameters.yaml)  
        PRIORITÉ 3 (MINIMALE) : Valeurs par défaut dans le code
        
        Returns:
            Dict: Configuration validée
            
        Raises:
            ValueError: Si la configuration est invalide
        """
        # ÉTAPE 1: Valeurs par défaut (priorité minimale)
        default_config = {
            "categorie": "linear",
            "funding_min": None,
            "funding_max": None,
            "volume_min_millions": None,
            "spread_max": None,
            "volatility_min": None,
            "volatility_max": None,
            "limite": 10,
            "volatility_ttl_sec": 120,
            # Nouveaux paramètres temporels
            "funding_time_min_minutes": None,
            "funding_time_max_minutes": None,
            # Configuration d'affichage
            "display_interval_seconds": 10,
        }
        
        # ÉTAPE 2: Charger depuis le fichier YAML (priorité moyenne)
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                file_config = yaml.safe_load(f)
            if file_config:
                default_config.update(file_config)
        except FileNotFoundError:
            self.logger.warning(f"⚠️ Fichier YAML non trouvé : {self.config_path} (utilisation des valeurs par défaut)")
        except Exception as e:
            self.logger.error(f"❌ Erreur lors du chargement YAML : {e}")
        
        # ÉTAPE 3: Récupérer les variables d'environnement (priorité maximale)
        settings = get_settings()
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
                default_config[config_key] = env_value
        
        # Valider la configuration finale
        self._validate_config(default_config)
        
        self.config = default_config
        return default_config
    
    def _validate_config(self, config: Dict) -> None:
        """
        Valide la cohérence des paramètres de configuration.
        
        Args:
            config: Configuration à valider
            
        Raises:
            ValueError: Si des paramètres sont incohérents ou invalides
        """
        errors = []
        
        # Validation des bornes de funding
        funding_min = config.get("funding_min")
        funding_max = config.get("funding_max")
        
        if funding_min is not None and funding_max is not None:
            if funding_min > funding_max:
                errors.append(f"funding_min ({funding_min}) ne peut pas être supérieur à funding_max ({funding_max})")
        
        # Validation des bornes de volatilité
        volatility_min = config.get("volatility_min")
        volatility_max = config.get("volatility_max")
        
        if volatility_min is not None and volatility_max is not None:
            if volatility_min > volatility_max:
                errors.append(f"volatility_min ({volatility_min}) ne peut pas être supérieur à volatility_max ({volatility_max})")
        
        # Validation des valeurs négatives
        for param in ["funding_min", "funding_max", "volatility_min", "volatility_max"]:
            value = config.get(param)
            if value is not None and value < 0:
                errors.append(f"{param} ne peut pas être négatif ({value})")
        
        # Validation du spread
        spread_max = config.get("spread_max")
        if spread_max is not None:
            if spread_max < 0:
                errors.append(f"spread_max ne peut pas être négatif ({spread_max})")
            if spread_max > MAX_SPREAD_PERCENTAGE:
                errors.append(
                    f"spread_max trop élevé ({spread_max}), "
                    f"maximum recommandé: {MAX_SPREAD_PERCENTAGE} (100%)"
                )
        
        # Validation du volume
        volume_min_millions = config.get("volume_min_millions")
        if volume_min_millions is not None and volume_min_millions < 0:
            errors.append(f"volume_min_millions ne peut pas être négatif ({volume_min_millions})")
        
        # Validation des paramètres temporels de funding
        ft_min = config.get("funding_time_min_minutes")
        ft_max = config.get("funding_time_max_minutes")
        
        for param, value in [("funding_time_min_minutes", ft_min), ("funding_time_max_minutes", ft_max)]:
            if value is not None:
                if value < 0:
                    errors.append(f"{param} ne peut pas être négatif ({value})")
                if value > MAX_FUNDING_TIME_MINUTES:
                    errors.append(
                        f"{param} trop élevé ({value}), "
                        f"maximum: {MAX_FUNDING_TIME_MINUTES} (24h)"
                    )
        
        if ft_min is not None and ft_max is not None:
            if ft_min > ft_max:
                errors.append(f"funding_time_min_minutes ({ft_min}) ne peut pas être supérieur à funding_time_max_minutes ({ft_max})")
        
        # Validation de la catégorie
        categorie = config.get("categorie")
        if categorie not in ["linear", "inverse", "both"]:
            errors.append(f"categorie invalide ({categorie}), valeurs autorisées: linear, inverse, both")
        
        # Validation de la limite
        limite = config.get("limite")
        if limite is not None:
            if limite < 1:
                errors.append(f"limite doit être positive ({limite})")
            if limite > MAX_LIMIT_RECOMMENDED:
                errors.append(
                    f"limite trop élevée ({limite}), "
                    f"maximum recommandé: {MAX_LIMIT_RECOMMENDED}"
                )
        
        # Validation du TTL de volatilité
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
        
        # Validation de l'intervalle d'affichage
        display_interval = config.get("display_interval_seconds")
        if display_interval is not None:
            if display_interval < MIN_DISPLAY_INTERVAL_SECONDS:
                errors.append(
                    f"display_interval_seconds trop faible ({display_interval}), "
                    f"minimum: {MIN_DISPLAY_INTERVAL_SECONDS} seconde"
                )
            if display_interval > MAX_DISPLAY_INTERVAL_SECONDS:
                errors.append(
                    f"display_interval_seconds trop élevé ({display_interval}), "
                    f"maximum: {MAX_DISPLAY_INTERVAL_SECONDS} secondes (5min)"
                )
        
        # Lever une erreur si des problèmes ont été détectés
        if errors:
            error_msg = "Configuration invalide détectée:\n" + "\n".join(f"  - {error}" for error in errors)
            raise ValueError(error_msg)
    
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
            key (str): Clé de configuration
            default: Valeur par défaut si la clé n'existe pas
            
        Returns:
            Valeur de configuration ou valeur par défaut
        """
        return self.config.get(key, default)


# Alias pour la compatibilité avec l'ancien code
ConfigManager = UnifiedConfigManager
