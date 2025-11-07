#!/usr/bin/env python3
"""
Circuit Breaker pour la gestion des erreurs répétées et rate limiting.

╔═══════════════════════════════════════════════════════════════════╗
║                    📖 GUIDE DE LECTURE                            ║
╚═══════════════════════════════════════════════════════════════════╝

Le Circuit Breaker est un pattern de résilience qui protège votre système
contre les appels répétés à un service défaillant.

🎯 POURQUOI C'EST IMPORTANT :

Sans Circuit Breaker :
- Le bot continue à faire des appels API même si l'API est down
- Gaspillage de ressources (CPU, network, rate limits)
- Délais d'attente inutiles (timeouts répétés)
- Risque de ban pour trop de requêtes

Avec Circuit Breaker :
- ✅ Détection rapide des pannes (API down, rate limit)
- ✅ Arrêt temporaire des appels pour laisser le service récupérer
- ✅ Test de récupération automatique (half-open)
- ✅ Protection du rate limit et des ressources

🔍 COMPRENDRE EN 3 MINUTES :

1. États du Circuit Breaker (lignes 85-104)
   - CLOSED : Normal, tout fonctionne
   - OPEN : Trop d'erreurs, on bloque les appels
   - HALF_OPEN : Test de récupération

2. Transition d'états (lignes 106-145)
   - CLOSED → OPEN : Après N échecs consécutifs
   - OPEN → HALF_OPEN : Après timeout
   - HALF_OPEN → CLOSED : Après succès
   - HALF_OPEN → OPEN : Après échec

3. Utilisation (lignes 200-250)
   └─> Wrapper autour des appels API

📚 EXEMPLE D'UTILISATION :

```python
from circuit_breaker import CircuitBreaker

# Créer un circuit breaker
cb = CircuitBreaker(
    failure_threshold=5,      # Ouvrir après 5 échecs
    timeout_seconds=60,       # Réessayer après 60s
    name="BybitAPI"
)

# Wrapper une fonction
def fetch_data():
    response = requests.get("https://api.bybit.com/...")
    return response.json()

# Appeler avec protection
try:
    result = cb.call(fetch_data)
    print(f"Succès: {result}")
except CircuitBreakerOpen as e:
    print(f"Circuit ouvert: {e}")
```

🔄 FLUX DES ÉTATS :

```
    ┌─────────┐
    │ CLOSED  │  ← État initial (tout va bien)
    └────┬────┘
         │
         │ (5 échecs)
         ▼
    ┌─────────┐
    │  OPEN   │  ← Bloque tous les appels
    └────┬────┘
         │
         │ (60s timeout)
         ▼
    ┌──────────┐
    │HALF_OPEN │  ← Test 1 appel
    └─────┬────┘
          │
          ├─ Succès ──> CLOSED
          │
          └─ Échec ───> OPEN
```

⚡ CAS D'USAGE DANS LE BOT :

1. **Rate Limiting API :**
   - 5 erreurs 429 consecutives → OPEN (stop les appels)
   - Attente 60s → HALF_OPEN (test 1 appel)
   - Succès → CLOSED (reprend normal)

2. **API Down :**
   - 5 timeouts consécutifs → OPEN
   - Évite de bombarder une API morte

3. **Erreurs Serveur :**
   - 5 erreurs 5xx → OPEN
   - Laisse le temps au serveur de récupérer

📖 RÉFÉRENCES :
- Pattern Circuit Breaker: https://martinfowler.com/bliki/CircuitBreaker.html
- Netflix Hystrix: https://github.com/Netflix/Hystrix
"""

import time
import threading
from enum import Enum
from typing import Callable, Any, Optional
from logging_setup import setup_logging


class CircuitState(Enum):
    """
    États possibles du Circuit Breaker.

    CLOSED : Circuit fermé, tout fonctionne normalement
             - Les appels passent sans restriction
             - Compte les échecs
             - Passe à OPEN après N échecs

    OPEN : Circuit ouvert, trop d'échecs détectés
           - Tous les appels sont bloqués
           - Retourne immédiatement une erreur
           - Passe à HALF_OPEN après timeout

    HALF_OPEN : Circuit semi-ouvert, test de récupération
                - Autorise UN seul appel de test
                - Si succès → CLOSED
                - Si échec → OPEN
    """
    CLOSED = "closed"       # Normal - appels autorisés
    OPEN = "open"           # Erreurs détectées - appels bloqués
    HALF_OPEN = "half_open" # Test de récupération - 1 appel


class CircuitBreakerOpen(Exception):
    """
    Exception levée quand le circuit breaker est ouvert.

    Cette exception indique que le service est considéré comme indisponible
    et que les appels sont temporairement bloqués.

    Example:
        ```python
        try:
            result = circuit_breaker.call(my_function)
        except CircuitBreakerOpen:
            # Utiliser un fallback ou notifier l'utilisateur
            logger.warning("Service temporairement indisponible")
        ```
    """
    pass


class CircuitBreaker:
    """
    Circuit Breaker pattern pour protéger contre les appels répétés à un service défaillant.

    Le circuit breaker suit les échecs et ouvre le circuit (bloque les appels)
    après un certain nombre d'échecs consécutifs. Après un timeout, il teste
    la récupération du service.

    Attributes:
        failure_threshold (int): Nombre d'échecs avant ouverture
        timeout_seconds (int): Temps d'attente avant test de récupération
        name (str): Nom du circuit pour les logs
        state (CircuitState): État actuel du circuit
        failure_count (int): Nombre d'échecs consécutifs
        last_failure_time (float): Timestamp du dernier échec

    Example:
        ```python
        # Circuit pour l'API Bybit
        api_breaker = CircuitBreaker(
            failure_threshold=5,    # Ouvrir après 5 échecs
            timeout_seconds=60,     # Réessayer après 1 minute
            name="BybitAPI"
        )

        # Utiliser le circuit
        def fetch_tickers():
            response = requests.get("https://api.bybit.com/v5/market/tickers")
            return response.json()

        try:
            data = api_breaker.call(fetch_tickers)
        except CircuitBreakerOpen:
            logger.warning("API temporairement indisponible")
        ```

    Thread Safety:
        - ✅ Thread-safe via threading.Lock
        - ✅ Plusieurs threads peuvent partager le même circuit
        - ✅ Les transitions d'état sont atomiques
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        name: str = "CircuitBreaker",
        logger: Optional[object] = None,
    ):
        """
        Initialise le Circuit Breaker.

        Args:
            failure_threshold (int): Nombre d'échecs consécutifs avant ouverture
                                    Exemple: 5 = ouvre après 5 échecs
            timeout_seconds (int): Secondes avant test de récupération
                                  Exemple: 60 = réessaie après 1 minute
            name (str): Nom du circuit pour identification dans les logs
            logger: Logger optionnel pour les événements du circuit

        Example:
            ```python
            # Circuit conservateur (tolère peu d'erreurs)
            strict_breaker = CircuitBreaker(
                failure_threshold=3,
                timeout_seconds=30,
                name="StrictAPI"
            )

            # Circuit tolérant (pour API instable)
            lenient_breaker = CircuitBreaker(
                failure_threshold=10,
                timeout_seconds=120,
                name="UnstableAPI"
            )
            ```
        """
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.name = name
        self.logger = logger or setup_logging()

        # État du circuit
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None

        # Lock pour thread-safety
        self._lock = threading.Lock()

        self.logger.debug(
            f"🔌 Circuit Breaker '{name}' initialisé "
            f"(seuil={failure_threshold}, timeout={timeout_seconds}s)"
        )

    def call(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """
        Appelle une fonction avec protection du Circuit Breaker.

        Cette méthode wrappe l'appel de fonction avec la logique du circuit :
        - Si OPEN : lève CircuitBreakerOpen
        - Si HALF_OPEN : tente l'appel (test de récupération)
        - Si CLOSED : appelle normalement

        Args:
            func: Fonction à appeler
            *args: Arguments positionnels de la fonction
            **kwargs: Arguments nommés de la fonction

        Returns:
            Résultat de la fonction si succès

        Raises:
            CircuitBreakerOpen: Si le circuit est ouvert
            Exception: Toute exception levée par func

        Example:
            ```python
            circuit = CircuitBreaker(name="API")

            # Appel simple
            result = circuit.call(requests.get, "https://api.com/data")

            # Avec kwargs
            result = circuit.call(
                requests.post,
                "https://api.com/submit",
                json={"key": "value"},
                timeout=10
            )
            ```
        """
        with self._lock:
            # Vérifier l'état avant l'appel
            self._check_state()

            # Si OPEN, bloquer l'appel
            if self.state == CircuitState.OPEN:
                raise CircuitBreakerOpen(
                    f"Circuit Breaker '{self.name}' est ouvert - "
                    f"Service temporairement indisponible"
                )

        # Effectuer l'appel (hors du lock pour ne pas bloquer)
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result

        except Exception as e:
            self._on_failure(e)
            raise

    def _check_state(self):
        """
        Vérifie et met à jour l'état du circuit si nécessaire.

        Transitions possibles :
        - OPEN → HALF_OPEN : Si timeout écoulé

        Note:
            - Doit être appelé dans un contexte avec _lock
            - Les autres transitions sont gérées par on_success/on_failure
        """
        if self.state == CircuitState.OPEN:
            # Vérifier si on peut tenter une récupération
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self.logger.info(
                    f"🔄 Circuit '{self.name}' passe en HALF_OPEN "
                    f"(test de récupération)"
                )

    def _should_attempt_reset(self) -> bool:
        """
        Détermine si on peut tenter de réinitialiser le circuit.

        Returns:
            True si le timeout est écoulé depuis le dernier échec
        """
        if self.last_failure_time is None:
            return True

        elapsed = time.time() - self.last_failure_time
        return elapsed >= self.timeout_seconds

    def _on_success(self):
        """
        Gère un appel réussi.

        Actions selon l'état :
        - CLOSED : Réinitialise le compteur d'échecs
        - HALF_OPEN : Ferme le circuit (récupération confirmée)
        - OPEN : N/A (ne devrait pas arriver ici)
        """
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                # Récupération réussie !
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.logger.info(
                    f"✅ Circuit '{self.name}' fermé - "
                    f"Service récupéré"
                )
            elif self.state == CircuitState.CLOSED:
                # Reset du compteur en cas de succès
                self.failure_count = 0

    def _on_failure(self, error: Exception):
        """
        Gère un échec d'appel.

        Actions selon l'état :
        - CLOSED : Incrémente compteur, ouvre si seuil atteint
        - HALF_OPEN : Ouvre immédiatement (récupération échouée)
        - OPEN : N/A (ne devrait pas arriver ici)

        Args:
            error: Exception qui a causé l'échec
        """
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == CircuitState.HALF_OPEN:
                # Test de récupération échoué
                self.state = CircuitState.OPEN
                self.logger.warning(
                    f"⚠️ Circuit '{self.name}' réouvert - "
                    f"Test de récupération échoué: {error}"
                )

            elif self.state == CircuitState.CLOSED:
                # Vérifier si seuil atteint
                if self.failure_count >= self.failure_threshold:
                    self.state = CircuitState.OPEN
                    self.logger.error(
                        f"🔴 Circuit '{self.name}' ouvert - "
                        f"Seuil d'échecs atteint ({self.failure_count}/{self.failure_threshold}) - "
                        f"Dernière erreur: {error}"
                    )

    def reset(self):
        """
        Réinitialise manuellement le circuit breaker.

        Force la fermeture du circuit et remet tous les compteurs à zéro.
        Utile pour les tests ou la récupération manuelle.

        Example:
            ```python
            # Après maintenance de l'API
            api_breaker.reset()
            logger.info("Circuit breaker réinitialisé manuellement")
            ```
        """
        with self._lock:
            old_state = self.state
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.last_failure_time = None

            if old_state != CircuitState.CLOSED:
                self.logger.info(
                    f"🔧 Circuit '{self.name}' réinitialisé manuellement "
                    f"({old_state.value} → {CircuitState.CLOSED.value})"
                )

    def get_state(self) -> CircuitState:
        """
        Retourne l'état actuel du circuit.

        Returns:
            CircuitState: État actuel (CLOSED, OPEN, ou HALF_OPEN)

        Example:
            ```python
            if breaker.get_state() == CircuitState.OPEN:
                logger.warning("Circuit ouvert, utiliser fallback")
            ```
        """
        with self._lock:
            return self.state

    def get_stats(self) -> dict:
        """
        Retourne les statistiques du circuit breaker.

        Returns:
            dict: Statistiques contenant :
                - state: État actuel
                - failure_count: Nombre d'échecs consécutifs
                - failure_threshold: Seuil d'ouverture
                - last_failure_time: Timestamp du dernier échec
                - time_until_retry: Secondes avant prochain test (si OPEN)

        Example:
            ```python
            stats = breaker.get_stats()
            print(f"État: {stats['state']}")
            print(f"Échecs: {stats['failure_count']}/{stats['failure_threshold']}")
            ```
        """
        with self._lock:
            stats = {
                "state": self.state.value,
                "failure_count": self.failure_count,
                "failure_threshold": self.failure_threshold,
                "last_failure_time": self.last_failure_time,
            }

            # Calculer temps avant retry si OPEN
            if self.state == CircuitState.OPEN and self.last_failure_time:
                elapsed = time.time() - self.last_failure_time
                time_until_retry = max(0, self.timeout_seconds - elapsed)
                stats["time_until_retry"] = round(time_until_retry, 1)

            return stats

