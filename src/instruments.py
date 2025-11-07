#!/usr/bin/env python3
"""
Module pour récupérer et filtrer les instruments perpétuels Bybit.

╔═══════════════════════════════════════════════════════════════════╗
║                    📖 GUIDE DE LECTURE                            ║
╚═══════════════════════════════════════════════════════════════════╝

Ce module récupère la liste des contrats perpétuels actifs depuis l'API Bybit
et détermine leur catégorie (linear vs inverse) via un mapping officiel ou
une heuristique basée sur le nom du symbole.

🔍 FONCTIONS PRINCIPALES :

1. get_perp_symbols() - Récupère tous les perpétuels actifs
2. category_of_symbol() - Détermine la catégorie d'un symbole
3. is_perpetual_active() - Filtre les perpétuels actifs uniquement

🏷️ CATÉGORIES DE CONTRATS :

Linear (USDT perpetual) :
- Exemples : BTCUSDT, ETHUSDT, SOLUSDT
- Margé en USDT (stablecoin)
- Plus courants et liquides
- Heuristique : Contient "USDT" dans le nom

Inverse (Coin-margined) :
- Exemples : BTCUSD, ETHUSD
- Margé en crypto (BTC, ETH, etc.)
- Moins courants
- Heuristique : PAS de "USDT" dans le nom

🎯 HEURISTIQUE DE CATÉGORISATION :

La fonction category_of_symbol() utilise une stratégie à 2 niveaux :

Priorité 1 : Mapping officiel (si disponible)
    ├─> Utilise le mapping symbol→category fourni par l'API
    └─> Garantit 100% de précision

Priorité 2 : Heuristique (fallback)
    ├─> Si "USDT" dans symbole → "linear"
    └─> Sinon → "inverse"

Exemple :
    symbol = "BTCUSDT"
    → Contient "USDT" → Catégorie : "linear" ✅

    symbol = "BTCUSD"
    → Ne contient pas "USDT" → Catégorie : "inverse" ✅

    symbol = "ETHPERP"
    → Ne contient pas "USDT" → Catégorie : "inverse"
    (Note : Rare, mais l'heuristique gère ce cas)

⚠️ LIMITES DE L'HEURISTIQUE :

L'heuristique est fiable à ~99% mais peut échouer dans ces cas rares :
- Symboles non-standard (ex: "USDTPERP" serait classé "linear")
- Futurs formats de Bybit non anticipés
- Nouveaux types de contrats

Solution : Toujours utiliser le mapping officiel quand disponible !

📚 EXEMPLE D'UTILISATION :

```python
from instruments import get_perp_symbols, category_of_symbol

# Récupérer tous les perpétuels
perp_data = get_perp_symbols(base_url="https://api.bybit.com")
print(f"Total: {perp_data['total']} perpétuels")
print(f"Linear: {len(perp_data['linear'])}")
print(f"Inverse: {len(perp_data['inverse'])}")

# Déterminer la catégorie d'un symbole
categories = perp_data['categories']
cat = category_of_symbol("BTCUSDT", categories)
print(f"BTCUSDT est {cat}")  # "linear"
```

📖 RÉFÉRENCES :
- API Bybit instruments-info: https://bybit-exchange.github.io/docs/v5/market/instrument
"""

import httpx
import logging
from http_client_manager import get_http_client
from http_utils import get_rate_limiter
from typing import Dict, List, Set

# Rate limiter global pour toutes les requêtes
_rate_limiter = get_rate_limiter()

# Logger pour les exclusions de symboles (utilisé uniquement si nécessaire)
_logger = logging.getLogger(__name__)


def fetch_instruments_info(
    base_url: str, category: str, timeout: int = 10
) -> List[Dict]:
    """
    Récupère la liste des instruments via l'API Bybit.

    Args:
        base_url (str): URL de base de l'API Bybit
        category (str): Catégorie des instruments (linear, inverse)
        timeout (int): Timeout pour les requêtes HTTP en secondes

    Returns:
        List[Dict]: Liste des instruments récupérés

    Raises:
        RuntimeError: En cas d'erreur HTTP ou API
    """
    all_instruments = []
    cursor = ""

    while True:
        # Construire l'URL avec pagination
        url = f"{base_url}/v5/market/instruments-info"
        params = {"category": category, "limit": 1000}
        if cursor:
            params["cursor"] = cursor

        try:
            _rate_limiter.acquire()
            client = get_http_client(timeout=timeout)
            response = client.get(url, params=params)

            # Vérifier le statut HTTP
            if response.status_code >= 400:
                raise RuntimeError(
                    f'Erreur HTTP Bybit: status={response.status_code} '
                    f'detail="{response.text[:100]}"'
                )

            data = response.json()

            # Vérifier le retCode
            if data.get("retCode") != 0:
                ret_code = data.get("retCode")
                ret_msg = data.get("retMsg", "")
                raise RuntimeError(
                    f'Erreur API Bybit: retCode={ret_code} retMsg="{ret_msg}"'
                )

            result = data.get("result", {})
            instruments = result.get("list", [])
            all_instruments.extend(instruments)

            # Vérifier s'il y a une page suivante
            next_page_cursor = result.get("nextPageCursor")
            if not next_page_cursor:
                break
            cursor = next_page_cursor

        except httpx.RequestError as e:
            raise RuntimeError(f"Erreur réseau/HTTP Bybit: {e}")
        except Exception as e:
            if "Erreur" in str(e):
                raise
            else:
                raise RuntimeError(f"Erreur réseau/HTTP Bybit: {e}")

    return all_instruments


def is_perpetual_active(item: Dict) -> bool:
    """
    Vérifie si un instrument est un perpétuel actif.

    Args:
        item (Dict): Données de l'instrument

    Returns:
        bool: True si c'est un perpétuel actif
    """
    contract_type = item.get("contractType", "").lower()
    status = item.get("status", "").lower()
    symbol = item.get("symbol", "")

    # Liste noire des symboles en cours de délisting ou problématiques
    delisted_symbols = {
        "LAUNCHCOINUSDT",  # En cours de délisting (erreur 30228)
        "AI16ZUSDT",       # En cours de délisting (erreur 30228)
        # Ajouter d'autres symboles problématiques ici si nécessaire
    }

    # Exclure les symboles en cours de délisting
    if symbol in delisted_symbols:
        _logger.debug(f"🚫 Symbole {symbol} exclu (liste noire - délisting)")
        return False

    # Vérifier le type de contrat (perpétuel)
    is_perpetual = contract_type in {"linearperpetual", "inverseperpetual"}

    # Vérifier le statut (actif) - exclure les statuts de délisting
    # Bybit peut retourner des statuts comme "delisting", "suspending", etc.
    is_delisting = "delisting" in status or "suspending" in status
    if is_delisting and is_perpetual:
        _logger.info(f"🚫 Symbole {symbol} exclu (statut délisting détecté: '{status}')")
    
    is_active = status in {"trading", "listed"} and not is_delisting

    return is_perpetual and is_active


def extract_symbol(item: Dict) -> str:
    """
    Extrait le symbole d'un instrument.

    Args:
        item (Dict): Données de l'instrument

    Returns:
        str: Symbole de l'instrument
    """
    return item.get("symbol", "")


def get_perp_symbols(base_url: str, timeout: int = 10) -> Dict:
    """
    Récupère et filtre les symboles de perpétuels actifs.

    Args:
        base_url (str): URL de base de l'API Bybit
        timeout (int): Timeout pour les requêtes HTTP en secondes

    Returns:
        Dict: Dictionnaire avec les symboles linear, inverse et le total
    """
    linear_symbols = []
    inverse_symbols = []
    categories: Dict[str, str] = {}

    # Récupérer les instruments linear
    linear_instruments = fetch_instruments_info(base_url, "linear", timeout)
    for item in linear_instruments:
        if is_perpetual_active(item):
            symbol = extract_symbol(item)
            if symbol:
                linear_symbols.append(symbol)
                categories[symbol] = "linear"

    # Récupérer les instruments inverse
    inverse_instruments = fetch_instruments_info(base_url, "inverse", timeout)
    for item in inverse_instruments:
        if is_perpetual_active(item):
            symbol = extract_symbol(item)
            if symbol:
                inverse_symbols.append(symbol)
                categories[symbol] = "inverse"

    return {
        "linear": linear_symbols,
        "inverse": inverse_symbols,
        "total": len(linear_symbols) + len(inverse_symbols),
        "categories": categories,  # mapping officiel symbole -> catégorie
        # ('linear'|'inverse')
    }


def get_spot_symbols(base_url: str, timeout: int = 10) -> Set[str]:
    """
    Fetch all active spot symbols from Bybit.

    Args:
        base_url: Base URL for Bybit API
        timeout: HTTP timeout in seconds

    Returns:
        Set of spot symbol names
    """
    try:
        spot_instruments = fetch_instruments_info(base_url, "spot", timeout)
        spot_symbols = set()

        for item in spot_instruments:
            status = item.get("status", "").lower()
            if status in {"trading", "listed"}:
                symbol = item.get("symbol", "")
                if symbol:
                    spot_symbols.add(symbol)

        return spot_symbols

    except Exception as e:
        # Return empty set on error
        return set()


def category_of_symbol(
    symbol: str, categories: Dict[str, str] | None = None
) -> str:
    """
    Détermine la catégorie d'un symbole avec mapping officiel + heuristique fallback.

    Cette fonction utilise une stratégie à 2 niveaux pour garantir la précision :
    1. PRIORITÉ : Mapping officiel de l'API Bybit (100% précis)
    2. FALLBACK : Heuristique basée sur le nom (fiable à ~99%)

    Heuristique :
    - Si "USDT" dans le symbole → "linear" (USDT perpetual)
    - Sinon → "inverse" (Coin-margined)

    Exemples :
        category_of_symbol("BTCUSDT", categories)  # "linear" (USDT)
        category_of_symbol("BTCUSD", categories)   # "inverse" (coin)
        category_of_symbol("ETHUSDT", {})          # "linear" (heuristique)
        category_of_symbol("ETHUSD", None)         # "inverse" (heuristique)

    Args:
        symbol (str): Symbole Bybit à catégoriser
                     Exemples: "BTCUSDT", "ETHUSDT", "BTCUSD"
        categories (Dict[str, str] | None): Mapping officiel {symbol: category}
                                          Fourni par get_perp_symbols()['categories']
                                          Si None ou vide, utilise l'heuristique

    Returns:
        str: Catégorie du symbole
            - "linear" : Contrat USDT perpetual (ex: BTCUSDT)
            - "inverse" : Contrat coin-margined (ex: BTCUSD)

    Note:
        - Toujours préférer le mapping officiel quand disponible
        - L'heuristique est fiable à ~99% mais peut échouer sur symboles non-standard
        - En cas d'erreur, retourne le résultat de l'heuristique (safe)

    Example:
        ```python
        # Avec mapping officiel
        perp_data = get_perp_symbols(base_url)
        cat = category_of_symbol("BTCUSDT", perp_data['categories'])
        print(cat)  # "linear" (depuis l'API)

        # Sans mapping (fallback heuristique)
        cat = category_of_symbol("ETHUSDT", None)
        print(cat)  # "linear" (heuristique : contient "USDT")
        ```
    """
    try:
        # PRIORITÉ 1 : Utiliser le mapping officiel si disponible et valide
        if (
            categories  # Mapping fourni
            and symbol in categories  # Symbole présent dans le mapping
            and categories[symbol] in ("linear", "inverse")  # Valeur valide
        ):
            # ✅ Utiliser la catégorie officielle (100% précis)
            return categories[symbol]

        # PRIORITÉ 2 : Fallback sur l'heuristique basée sur le nom
        # Heuristique : Si "USDT" dans le symbole → linear, sinon → inverse
        # Fiabilité : ~99% (échoue sur symboles non-standard rares)
        #
        # Exemples :
        # - "BTCUSDT" contient "USDT" → "linear" ✅
        # - "ETHUSDT" contient "USDT" → "linear" ✅
        # - "BTCUSD" ne contient pas "USDT" → "inverse" ✅
        # - "ETHUSD" ne contient pas "USDT" → "inverse" ✅
        return "linear" if "USDT" in symbol else "inverse"
    except Exception:
        # En cas d'erreur inattendue, utiliser l'heuristique (safe)
        return "linear" if "USDT" in symbol else "inverse"
