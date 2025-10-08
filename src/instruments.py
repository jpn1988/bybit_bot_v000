"""Module pour récupérer et filtrer les instruments perpétuels Bybit."""

import httpx
from http_client_manager import get_http_client
from http_utils import get_rate_limiter
from typing import Dict, List

_rate_limiter = get_rate_limiter()


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

    # Vérifier le type de contrat (perpétuel)
    is_perpetual = contract_type in {"linearperpetual", "inverseperpetual"}

    # Vérifier le statut (actif)
    is_active = status in {"trading", "listed"}

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


def category_of_symbol(
    symbol: str, categories: Dict[str, str] | None = None
) -> str:
    """
    Retourne la catégorie officielle d'un symbole si connue, sinon une
    heuristique sûre.

    Args:
        symbol (str): Symbole Bybit
        categories (Dict[str, str] | None): Mapping officiel symbole->catégorie
        ('linear'|'inverse')

    Returns:
        str: 'linear' ou 'inverse'
    """
    try:
        if (
            categories
            and symbol in categories
            and categories[symbol] in ("linear", "inverse")
        ):
            return categories[symbol]
        # Heuristique conservatrice: USDT => linear, sinon inverse
        return "linear" if "USDT" in symbol else "inverse"
    except Exception:
        return "linear" if "USDT" in symbol else "inverse"
