#!/usr/bin/env python3
"""
Utilitaires HTTP pour le bot Bybit : Rate Limiter avec fenêtre glissante.

Ce module fournit un rate limiter thread-safe qui limite le nombre d'appels
API dans une fenêtre de temps donnée pour respecter les limites de Bybit.

╔═══════════════════════════════════════════════════════════════════╗
║                    📖 GUIDE DE LECTURE                            ║
╚═══════════════════════════════════════════════════════════════════╝

🔍 ALGORITHME DE FENÊTRE GLISSANTE :

Au lieu de compter les requêtes par seconde fixe (00:00-00:59, 00:01-01:59...),
la fenêtre glissante compte les requêtes dans les N dernières secondes à tout moment.

Exemple avec max_calls=5, window_seconds=1.0 :
    
    Temps   Action          Timestamps          État
    --------------------------------------------------------
    00.0s   Requête 1       [00.0]              OK (1/5)
    00.2s   Requête 2       [00.0, 00.2]        OK (2/5)
    00.4s   Requête 3       [00.0, 00.2, 00.4]  OK (3/5)
    00.6s   Requête 4       [..., 00.6]         OK (4/5)
    00.8s   Requête 5       [..., 00.8]         OK (5/5) - LIMITE ATTEINTE
    00.9s   Requête 6       [..., 00.8]         BLOQUÉ (attendre 0.1s)
    01.0s   Requête 6       [00.2, ..., 00.8]   OK (4/5) - 00.0 retiré
    
Avantages :
- ✅ Plus équitable : pas de "reset" brutal à chaque seconde
- ✅ Lissage du trafic : distribution uniforme des requêtes
- ✅ Respect strict des limites API

📚 EXEMPLE D'UTILISATION :

```python
from http_utils import get_rate_limiter

# Créer un rate limiter (5 appels par seconde max)
limiter = get_rate_limiter()  # Lit depuis les variables d'environnement

# Avant chaque requête API
limiter.acquire()  # Bloque si nécessaire
response = requests.get("https://api.bybit.com/v5/market/tickers")

# Ou avec un rate limiter personnalisé
custom_limiter = RateLimiter(max_calls=10, window_seconds=2.0)
custom_limiter.acquire()  # Max 10 appels toutes les 2 secondes
```

⚡ LIMITES API BYBIT :

Endpoints publics :
- Tickers : 50 requêtes / seconde
- Klines : 10 requêtes / seconde
- Orderbook : 50 requêtes / seconde

Endpoints privés (authentifiés) :
- Account : 10 requêtes / seconde
- Trading : 10 requêtes / seconde

🛡️ THREAD-SAFETY :

Le rate limiter utilise un verrou (threading.Lock) pour garantir
la sécurité dans un environnement multi-thread :
- ✅ Plusieurs threads peuvent partager la même instance
- ✅ Les timestamps sont protégés contre les race conditions
- ✅ Les opérations sont atomiques
"""

import os
import time
import threading
from collections import deque


class RateLimiter:
    """
    Rate limiter thread-safe avec algorithme de fenêtre glissante.
    
    Cette classe limite le nombre d'appels dans une fenêtre de temps glissante.
    Contrairement à une fenêtre fixe, la fenêtre glissante compte les appels
    dans les N dernières secondes à partir du moment actuel.
    
    Algorithme :
    1. Avant chaque appel, nettoyer les timestamps hors fenêtre
    2. Si count < max_calls, autoriser l'appel et ajouter le timestamp
    3. Sinon, calculer le temps d'attente et bloquer
    
    Attributes:
        max_calls (int): Nombre maximum d'appels dans la fenêtre
        window_seconds (float): Durée de la fenêtre en secondes
        
    Example:
        ```python
        # Limiter à 5 appels par seconde
        limiter = RateLimiter(max_calls=5, window_seconds=1.0)
        
        # Effectuer 10 requêtes (les 5 dernières seront ralenties)
        for i in range(10):
            limiter.acquire()  # Bloque si nécessaire
            print(f"Requête {i+1}")
            # ... faire la requête API ...
        ```
        
    Thread Safety:
        ```python
        # Partager un rate limiter entre threads
        limiter = RateLimiter(max_calls=5, window_seconds=1.0)
        
        def worker():
            for _ in range(100):
                limiter.acquire()  # Thread-safe
                # ... requête API ...
        
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker) for _ in range(10)]
        ```
    """

    def __init__(self, max_calls: int = 5, window_seconds: float = 1.0):
        """
        Initialise le rate limiter.
        
        Args:
            max_calls (int): Nombre maximum d'appels autorisés dans la fenêtre
                           Exemple: 5 = max 5 appels
            window_seconds (float): Durée de la fenêtre en secondes
                                  Exemple: 1.0 = par seconde, 2.0 = toutes les 2 secondes
                                  
        Example:
            ```python
            # Max 10 appels toutes les 2 secondes
            limiter = RateLimiter(max_calls=10, window_seconds=2.0)
            
            # Max 50 appels par seconde (endpoints publics Bybit)
            limiter = RateLimiter(max_calls=50, window_seconds=1.0)
            ```
            
        Note:
            - max_calls=0 bloque tous les appels (cas limite)
            - window_seconds doit être > 0
        """
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        
        # File de timestamps des appels récents
        # Utilise deque pour des insertions/suppressions O(1) en bout de file
        self._timestamps = deque()
        
        # Verrou pour garantir la thread-safety
        # Protège l'accès concurrent à self._timestamps
        self._lock = threading.Lock()

    def acquire(self):
        """
        Acquiert le droit de faire un appel API, en bloquant si nécessaire.
        
        Cette méthode DOIT être appelée avant chaque requête API pour respecter
        les limites de taux. Elle bloque l'exécution jusqu'à ce qu'un slot
        soit disponible dans la fenêtre glissante.
        
        Algorithme :
        1. Nettoyer les timestamps expirés (hors fenêtre)
        2. Si slots disponibles (count < max_calls) :
           - Enregistrer le timestamp actuel
           - Retourner immédiatement
        3. Sinon :
           - Calculer le temps d'attente jusqu'à expiration du plus ancien
           - Attendre par petits incréments (0.05s) pour rester réactif
           - Recommencer à l'étape 1
        
        Example:
            ```python
            limiter = RateLimiter(max_calls=5, window_seconds=1.0)
            
            # Exemple 1 : Appel simple
            limiter.acquire()  # Bloque si nécessaire
            response = requests.get("https://api.bybit.com/...")
            
            # Exemple 2 : Boucle de requêtes
            for symbol in symbols:
                limiter.acquire()  # Respecte automatiquement la limite
                data = fetch_data(symbol)
            
            # Exemple 3 : Avec timeout personnalisé
            start = time.time()
            limiter.acquire()
            print(f"Attendu {time.time() - start:.2f}s")
            ```
            
        Note:
            - Cette méthode bloque le thread appelant
            - L'attente est active (sleep par petits incréments)
            - Pour un comportement non-bloquant, utilisez AsyncRateLimiter
            - Le verrou est relâché pendant les sleep pour permettre d'autres threads
            
        Thread Safety:
            - ✅ Plusieurs threads peuvent appeler acquire() simultanément
            - ✅ Les timestamps sont protégés contre les race conditions
            - ✅ Le verrou garantit la cohérence des compteurs
        """
        while True:
            # Obtenir le timestamp actuel (epoch time en secondes)
            now = time.time()
            
            # Section critique : manipulation de la liste de timestamps
            with self._lock:
                # Nettoyer les timestamps expirés (hors de la fenêtre glissante)
                # Un timestamp est expiré si : now - timestamp > window_seconds
                # Exemple : fenêtre 1.0s, now=10.5s → retirer timestamps < 9.5s
                while (
                    self._timestamps
                    and now - self._timestamps[0] > self.window_seconds
                ):
                    self._timestamps.popleft()  # Retirer le plus ancien
                
                # Vérifier si un slot est disponible
                if len(self._timestamps) < self.max_calls:
                    # ✅ Slot disponible : enregistrer le timestamp et autoriser
                    self._timestamps.append(now)
                    return  # Retourner immédiatement
                
                # ❌ Limite atteinte : calculer le temps d'attente
                # Le plus ancien timestamp expirera dans :
                # wait_time = window_seconds - (now - oldest_timestamp)
                wait_time = self.window_seconds - (now - self._timestamps[0])
            
            # Attendre hors du verrou pour ne pas bloquer d'autres threads
            # Utiliser min(wait_time, 0.05) pour rester réactif :
            # - Si wait_time < 0.05s, attendre exactement wait_time
            # - Sinon, attendre 0.05s et recalculer (au cas où d'autres threads libèrent des slots)
            if wait_time > 0:
                from config.timeouts import TimeoutConfig
                time.sleep(min(wait_time, TimeoutConfig.RATE_LIMIT_SLEEP))


def get_rate_limiter() -> RateLimiter:
    """
    Construit un rate limiter à partir des variables d'environnement.
    
    Cette fonction factory lit la configuration depuis les variables d'environnement
    et crée une instance de RateLimiter avec les paramètres appropriés.
    
    Variables d'environnement utilisées :
    - PUBLIC_HTTP_MAX_CALLS_PER_SEC : Nombre max d'appels (défaut: 5)
    - PUBLIC_HTTP_WINDOW_SECONDS : Durée de la fenêtre (défaut: 1.0)
    
    Exemple de configuration (.env) :
        ```
        PUBLIC_HTTP_MAX_CALLS_PER_SEC=10
        PUBLIC_HTTP_WINDOW_SECONDS=1.0
        ```
    
    Returns:
        RateLimiter: Instance configurée avec les paramètres d'environnement
                    ou les valeurs par défaut si les variables ne sont pas définies
                    
    Example:
        ```python
        # Utilisation simple
        from http_utils import get_rate_limiter
        
        limiter = get_rate_limiter()  # Lit depuis ENV ou utilise défauts
        
        for symbol in symbols:
            limiter.acquire()
            data = fetch_data(symbol)
        ```
        
    Note:
        - Les valeurs par défaut (5 requêtes/seconde) sont conservatrices
        - Pour les endpoints publics Bybit, vous pouvez augmenter à 50/s
        - En cas d'erreur de parsing, utilise les valeurs par défaut
    """
    try:
        # Lire la variable d'environnement PUBLIC_HTTP_MAX_CALLS_PER_SEC
        # Défaut : 5 appels par seconde (conservateur)
        max_calls = int(os.getenv("PUBLIC_HTTP_MAX_CALLS_PER_SEC", "5"))
        
        # Lire la variable d'environnement PUBLIC_HTTP_WINDOW_SECONDS
        # Défaut : 1.0 seconde (fenêtre d'une seconde)
        window = float(os.getenv("PUBLIC_HTTP_WINDOW_SECONDS", "1"))
    except Exception:
        # En cas d'erreur de parsing (valeur invalide dans ENV),
        # utiliser les valeurs par défaut conservatrices
        max_calls = 5
        window = 1.0
    
    return RateLimiter(max_calls=max_calls, window_seconds=window)
