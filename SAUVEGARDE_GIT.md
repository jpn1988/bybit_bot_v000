# 💾 Sauvegarde automatique vers GitHub

Ce guide explique comment utiliser le script de sauvegarde automatique pour push vos modifications vers GitHub.

## 📋 Prérequis

- Git installé sur votre système
- Dépôt Git initialisé (déjà fait pour ce projet)
- Repository GitHub configuré (remote origin)

## 🚀 Utilisation

### Méthode 1 : Avec message interactif

Lancez simplement le script et entrez votre message quand on vous le demande :

```bash
python git_save.py
```

Le script vous demandera :
```
📝 Entrez un message de commit (ou Ctrl+C pour annuler) :
>>> 
```

### Méthode 2 : Avec message en ligne de commande

Passez le message de commit directement en argument :

```bash
python git_save.py "Ajout de nouvelles fonctionnalités"
```

Ou sur Windows avec le script batch :

```cmd
save.bat "Message de commit"
```

## 📝 Exemples de messages de commit

### Messages descriptifs recommandés :
- `"Nettoyage des fichiers inutiles"`
- `"Ajout de nouvelles fonctionnalités de trading"`
- `"Correction des bugs de connexion WebSocket"`
- `"Amélioration de la gestion des erreurs"`
- `"Mise à jour de la documentation"`

### Messages courts (si urgent) :
- `"Fix bug"`
- `"Update config"`
- `"WIP"` (Work In Progress)

## 🔄 Ce que fait le script

Le script exécute automatiquement ces étapes :

1. **Vérification** : Vérifie que Git est installé et qu'on est dans un dépôt Git
2. **Ajout** : Ajoute tous les fichiers modifiés (`git add .`)
3. **Commit** : Crée un commit avec votre message
4. **Push** : Envoie les modifications vers GitHub (`git push`)

## ✅ Exemple d'utilisation complète

```bash
# 1. Lancez le script
$ python git_save.py

# 2. Le script affiche :
╔══════════════════════════════════════════════════════════════════════════════╗
║                    SAUVEGARDE GIT - BOT BYBIT                               ║
╚══════════════════════════════════════════════════════════════════════════════╝

📝 Entrez un message de commit (ou Ctrl+C pour annuler) :
>>> Nettoyage des fichiers inutiles

📋 Message de commit : Nettoyage des fichiers inutiles

📦 Étape 1/3 : Ajout des modifications...
✅ Fichiers ajoutés

📝 Étape 2/3 : Création du commit...
✅ Commit créé

🚀 Étape 3/3 : Envoi vers GitHub...
✅ Push réussi

═══════════════════════════════════════════════════════════════════════════════
✅ SAUVEGARDE TERMINÉE AVEC SUCCÈS
═══════════════════════════════════════════════════════════════════════════════

📌 Commit : Nettoyage des fichiers inutiles
🔗 Dépôt : GitHub
```

## ⚠️ Gestion des erreurs

### Git non installé
```
❌ Erreur : Git n'est pas installé ou pas dans le PATH
   Installez Git depuis https://git-scm.com/
```

### Pas dans un dépôt Git
```
❌ Erreur : Ce répertoire n'est pas un dépôt Git
   Initialisez un dépôt avec : git init
```

### Push échoué
Le script vous donnera des suggestions :
```
⚠️  Attention : Le push a échoué
💡 Suggestions :
   1. Vérifiez votre connexion internet
   2. Vérifiez que le dépôt distant est configuré : git remote -v
   3. Configurez le dépôt distant : git remote add origin <url>
   4. Vérifiez vos credentials Git
```

## 🔧 Configuration du remote GitHub

Si le dépôt distant n'est pas configuré, exécutez :

```bash
git remote add origin https://github.com/VOTRE_USERNAME/VOTRE_REPO.git
```

Pour vérifier la configuration :
```bash
git remote -v
```

## 💡 Astuces

### Sauvegarde rapide
Créez un alias dans votre terminal pour sauvegarder plus vite :

**Windows (PowerShell)** :
```powershell
function Save-Bot { python git_save.py $args }
```

**Linux/Mac** :
```bash
alias save='python git_save.py'
```

### Message court
```bash
python git_save.py "Update"
```

### Annuler
Appuyez sur `Ctrl+C` pour annuler à tout moment.

## 📚 Ressources

- [Documentation Git](https://git-scm.com/doc)
- [Guide GitHub](https://docs.github.com/)
- [Bonnes pratiques de commit](https://www.conventionalcommits.org/)

## 🆘 Support

Si vous rencontrez des problèmes :
1. Vérifiez que Git est bien installé : `git --version`
2. Vérifiez votre connexion internet
3. Vérifiez que le dépôt distant est configuré : `git remote -v`
4. Consultez les logs d'erreur du script
