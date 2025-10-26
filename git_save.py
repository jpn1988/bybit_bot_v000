#!/usr/bin/env python3
"""
Script de sauvegarde automatique vers GitHub.

Ce script permet de sauvegarder automatiquement les modifications
du bot Bybit vers GitHub avec un message de commit personnalisable.

Usage:
    python git_save.py
    python git_save.py "message de commit"
"""

import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd, description=""):
    """Exécute une commande et retourne le résultat."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def check_git_installed():
    """Vérifie que Git est installé."""
    success, _, _ = run_command("git --version")
    return success


def check_git_repo():
    """Vérifie qu'on est dans un dépôt Git."""
    success, _, _ = run_command("git rev-parse --git-dir")
    return success


def get_status():
    """Récupère le statut des modifications."""
    success, output, _ = run_command("git status --short")
    return output if success else ""


def print_header():
    """Affiche l'en-tête."""
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "SAUVEGARDE GIT - BOT BYBIT" + " " * 28 + "║")
    print("╚" + "═" * 78 + "╝")
    print()


def main():
    """Fonction principale."""
    print_header()

    # Vérifier que Git est installé
    if not check_git_installed():
        print("❌ Erreur : Git n'est pas installé ou pas dans le PATH")
        print("   Installez Git depuis https://git-scm.com/")
        sys.exit(1)

    # Vérifier qu'on est dans un dépôt Git
    if not check_git_repo():
        print("❌ Erreur : Ce répertoire n'est pas un dépôt Git")
        print("   Initialisez un dépôt avec : git init")
        sys.exit(1)

    # Récupérer le message de commit
    commit_message = sys.argv[1] if len(sys.argv) > 1 else ""

    if not commit_message:
        print("📝 Entrez un message de commit (ou Ctrl+C pour annuler) :")
        commit_message = input(">>> ").strip()
        
        if not commit_message:
            print("\n⚠️  Aucun message fourni. Opération annulée.")
            sys.exit(0)

    print(f"\n📋 Message de commit : {commit_message}")
    print()

    # Étape 1 : Ajouter les fichiers
    print("📦 Étape 1/3 : Ajout des modifications...")
    success, stdout, stderr = run_command("git add .")
    
    if not success:
        print(f"❌ Erreur lors de l'ajout des fichiers : {stderr}")
        sys.exit(1)
    
    if stdout:
        print(f"   {stdout.strip()}")
    
    # Vérifier s'il y a des changements
    status = get_status()
    if not status:
        print("\n✅ Aucune modification détectée. Rien à commiter.")
        sys.exit(0)
    
    print("✅ Fichiers ajoutés")
    print()

    # Étape 2 : Commit
    print("📝 Étape 2/3 : Création du commit...")
    commit_cmd = f'git commit -m "{commit_message}"'
    success, stdout, stderr = run_command(commit_cmd)
    
    if not success:
        print(f"❌ Erreur lors du commit : {stderr}")
        sys.exit(1)
    
    print("✅ Commit créé")
    print()

    # Étape 3 : Push vers GitHub
    print("🚀 Étape 3/3 : Envoi vers GitHub...")
    success, stdout, stderr = run_command("git push")
    
    if not success:
        print(f"⚠️  Attention : Le push a échoué")
        print(f"   Erreur : {stderr}")
        print("\n💡 Suggestions :")
        print("   1. Vérifiez votre connexion internet")
        print("   2. Vérifiez que le dépôt distant est configuré : git remote -v")
        print("   3. Configurez le dépôt distant : git remote add origin <url>")
        print("   4. Vérifiez vos credentials Git")
        sys.exit(1)
    
    print("✅ Push réussi")
    print()

    # Résumé
    print("═" * 80)
    print("✅ SAUVEGARDE TERMINÉE AVEC SUCCÈS")
    print("═" * 80)
    print(f"\n📌 Commit : {commit_message}")
    print(f"🔗 Dépôt : GitHub")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Opération annulée par l'utilisateur")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Erreur inattendue : {e}")
        sys.exit(1)
