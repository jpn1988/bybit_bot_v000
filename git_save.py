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
from dataclasses import dataclass


# Constantes
BORDER_WIDTH = 78
SUMMARY_WIDTH = 80
HEADER_TITLE = "SAUVEGARDE GIT - BOT BYBIT"

# Emojis et messages
EMOJI_ERROR = "❌"
EMOJI_WARNING = "⚠️"
EMOJI_SUCCESS = "✅"
EMOJI_PACKAGE = "📦"
EMOJI_COMMIT = "📝"
EMOJI_ROCKET = "🚀"
EMOJI_NOTE = "📝"
EMOJI_LINK = "🔗"
EMOJI_PIN = "📌"
EMOJI_LIGHTBULB = "💡"

ERROR_GIT_NOT_INSTALLED = "Git n'est pas installé ou pas dans le PATH"
ERROR_NOT_GIT_REPO = "Ce répertoire n'est pas un dépôt Git"
ERROR_ADD_FILES = "Erreur lors de l'ajout des fichiers"
ERROR_COMMIT = "Erreur lors du commit"
WARNING_PUSH_FAILED = "Attention : Le push a échoué"
WARNING_NO_MESSAGE = "Aucun message fourni. Opération annulée."
WARNING_CANCELLED = "Opération annulée par l'utilisateur"

SUCCESS_NO_CHANGES = "Aucune modification détectée. Rien à commiter."
SUCCESS_SAVE_COMPLETE = "SAUVEGARDE TERMINÉE AVEC SUCCÈS"

PROMPT_COMMIT_MESSAGE = "Entrez un message de commit (ou Ctrl+C pour annuler) :"
PROMPT_INPUT = ">>> "


@dataclass
class CommandResult:
    """Résultat d'une commande exécutée."""
    success: bool
    output: str
    error: str


def run_command(cmd: str) -> CommandResult:
    """Exécute une commande et retourne le résultat."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            check=False
        )
        return CommandResult(
            success=result.returncode == 0,
            output=result.stdout,
            error=result.stderr
        )
    except Exception as e:
        return CommandResult(
            success=False,
            output="",
            error=str(e)
        )


def check_git_installed() -> bool:
    """Vérifie que Git est installé."""
    result = run_command("git --version")
    return result.success


def check_git_repo() -> bool:
    """Vérifie qu'on est dans un dépôt Git."""
    result = run_command("git rev-parse --git-dir")
    return result.success


def get_status() -> str:
    """Récupère le statut des modifications."""
    result = run_command("git status --short")
    return result.output if result.success else ""


def print_header() -> None:
    """Affiche l'en-tête."""
    print("╔" + "═" * BORDER_WIDTH + "╗")
    print("║" + " " * 20 + HEADER_TITLE + " " * 28 + "║")
    print("╚" + "═" * BORDER_WIDTH + "╝")
    print()


def get_commit_message() -> str:
    """Récupère le message de commit depuis les arguments ou l'utilisateur."""
    commit_message = sys.argv[1] if len(sys.argv) > 1 else ""

    if not commit_message:
        print(f"{EMOJI_NOTE} {PROMPT_COMMIT_MESSAGE}")
        commit_message = input(PROMPT_INPUT).strip()
        
        if not commit_message:
            print(f"\n{EMOJI_WARNING}  {WARNING_NO_MESSAGE}")
            sys.exit(0)

    print(f"\n📋 Message de commit : {commit_message}")
    print()
    return commit_message


def execute_git_add() -> None:
    """Exécute l'ajout des fichiers modifiés."""
    print(f"{EMOJI_PACKAGE} Étape 1/3 : Ajout des modifications...")
    result = run_command("git add .")
    
    if not result.success:
        print(f"{EMOJI_ERROR} {ERROR_ADD_FILES} : {result.error}")
        sys.exit(1)
    
    if result.output:
        print(f"   {result.output.strip()}")
    
    # Vérifier s'il y a des changements
    status = get_status()
    if not status:
        print(f"\n{EMOJI_SUCCESS} {SUCCESS_NO_CHANGES}")
        sys.exit(0)
    
    print(f"{EMOJI_SUCCESS} Fichiers ajoutés")
    print()


def execute_git_commit(commit_message: str) -> None:
    """Exécute la création du commit."""
    print(f"{EMOJI_COMMIT} Étape 2/3 : Création du commit...")
    commit_cmd = f'git commit -m "{commit_message}"'
    result = run_command(commit_cmd)
    
    if not result.success:
        print(f"{EMOJI_ERROR} {ERROR_COMMIT} : {result.error}")
        sys.exit(1)
    
    print(f"{EMOJI_SUCCESS} Commit créé")
    print()


def execute_git_push() -> None:
    """Exécute le push vers GitHub."""
    print(f"{EMOJI_ROCKET} Étape 3/3 : Envoi vers GitHub...")
    result = run_command("git push")
    
    if not result.success:
        print(f"{EMOJI_WARNING}  {WARNING_PUSH_FAILED}")
        print(f"   Erreur : {result.error}")
        print(f"\n{EMOJI_LIGHTBULB} Suggestions :")
        print("   1. Vérifiez votre connexion internet")
        print("   2. Vérifiez que le dépôt distant est configuré : git remote -v")
        print("   3. Configurez le dépôt distant : git remote add origin <url>")
        print("   4. Vérifiez vos credentials Git")
        sys.exit(1)
    
    print(f"{EMOJI_SUCCESS} Push réussi")
    print()


def print_success_summary(commit_message: str) -> None:
    """Affiche le résumé de la sauvegarde réussie."""
    print("═" * SUMMARY_WIDTH)
    print(f"{EMOJI_SUCCESS} {SUCCESS_SAVE_COMPLETE}")
    print("═" * SUMMARY_WIDTH)
    print(f"\n{EMOJI_PIN} Commit : {commit_message}")
    print(f"{EMOJI_LINK} Dépôt : GitHub")
    print()


def validate_environment() -> None:
    """Valide que l'environnement Git est correctement configuré."""
    if not check_git_installed():
        print(f"{EMOJI_ERROR} Erreur : {ERROR_GIT_NOT_INSTALLED}")
        print("   Installez Git depuis https://git-scm.com/")
        sys.exit(1)

    if not check_git_repo():
        print(f"{EMOJI_ERROR} Erreur : {ERROR_NOT_GIT_REPO}")
        print("   Initialisez un dépôt avec : git init")
        sys.exit(1)


def main() -> None:
    """Fonction principale."""
    print_header()
    validate_environment()
    
    commit_message = get_commit_message()
    execute_git_add()
    execute_git_commit(commit_message)
    execute_git_push()
    print_success_summary(commit_message)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{EMOJI_WARNING}  {WARNING_CANCELLED}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{EMOJI_ERROR} Erreur inattendue : {e}")
        sys.exit(1)
