# CONTRIBUTING — Règles simples

## 1) Documenter les changements importants
- Utiliser des messages de commit clairs et descriptifs.
- But, fichiers touchés, décisions, tests, prochaines étapes.

## 2) Garder un code **propre**
- Supprimer code/commentaires **morts** dès qu'ils ne servent plus.
- Renommer les fichiers ambigus (ex: `tmp_*.py`) → noms clairs.
- Ne jamais logger de secrets (API key/secret).

## 3) Petites checklists à chaque livraison
- [ ] Messages de commit clairs et descriptifs
- [ ] README à jour si comportement utilisateur changé
- [ ] Logs lisibles (FR simple, emojis OK)
- [ ] Pas de code inutile / fichiers orphelins
- [ ] `python src/bot.py` démarre et s'arrête proprement

## 4) Style des commits (optionnel mais utile)
- `chore:` maintenance / docs
- `feat:` nouvelle fonctionnalité
- `fix:` correction bug
- `refactor:` amélioration code sans changer le comportement
- `docs:` doc uniquement
