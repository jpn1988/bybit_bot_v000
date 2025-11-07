# 🧩 Compatibilités Legacy Temporaires

Ce document recense les points d'API maintenus pour assurer la transition entre
le code legacy et l’architecture refactorisée. Ils sont destinés à disparaître
une fois les nouvelles suites de tests et usages adaptés.

## Synthèse

| Emplacement | Compatibilité | Usage actuel | Condition de retrait |
|-------------|---------------|--------------|-----------------------|
| `data_manager.py` | Méthodes `update_funding_data`, `get_funding_data`, `update_realtime_data`, `get_realtime_data`, `set_symbol_lists`, `remove_symbol_from_category`, `get_all_symbols`, `get_data_stats`, `clear_all_data` | Tests legacy (tuple-based) et scripts éventuels | Migration des tests DataManager/DataStorage vers `FundingData` et API publiques |
| `data_storage.py` | Attribut `funding_data`, API tuple (`update_funding_data`, `get_funding_data`, `get_all_funding_data`), helper `_to_legacy_tuple` | Tests hérités (`tests/test_data_storage.py`, `tests/test_data_fetcher.py` et dépendances) | Dès que tous les consommateurs utilisent `FundingData` |
| `opportunity_manager.py` | Alias `BybitPublicClient = _BybitPublicClient` | Patchs / mocks existants (`tests/test_data_fetcher.py`, etc.) | Migration des tests pour importer directement depuis `bybit_client` |

## Détails

### DataManager
- La couche d’accès legacy permet de continuer à manipuler des tuples
  `(funding_rate, volume, next_funding_time, …)` alors que la logique interne
  repose désormais sur `FundingData` immutables.
- Ces méthodes sont annotées `LEGACY COMPAT` dans le code. Une fois la suite de
  tests mise à jour, elles pourront être supprimées pour éviter les doubles
  chemins d’accès.

### DataStorage
- `funding_data` conserve l’ancien dictionnaire pour ne pas casser les tests
  existants. Chaque écriture via `set_funding_data_object` synchronise aussi ce
  cache.
- `_to_legacy_tuple` tronque les `FundingData` afin de respecter exactement le
  format attendu par l’ancien code.

### OpportunityManager
- Le ré-export de `BybitPublicClient` maintient les patchs du legacy (ex. tests
  qui ciblent `opportunity_manager.BybitPublicClient`).
- À supprimer dès que les tests/mocks pointeront directement vers
  `bybit_client.public_client.BybitPublicClient`.

## Prochaines étapes
1. Réécrire progressivement les tests (`tests/test_data_fetcher.py`,
   `tests/test_monitoring_components.py`, …) pour consommer l’API moderne.
2. Mettre à jour les scripts/outils internes si nécessaire.
3. Supprimer ces compatibilités et simplifier les modules.

> 💡 Chaque bloc de compatibilité comporte un commentaire `LEGACY COMPAT` dans
> le code : s’y référer pour savoir quand retirer la fonctionnalité.


