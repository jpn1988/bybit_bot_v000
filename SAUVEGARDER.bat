@echo off
REM Script de sauvegarde Git - Double-clic pour lancer
chcp 65001 >nul

echo.
echo ╔══════════════════════════════════════════════════════════════════════╗
echo ║         SAUVEGARDE GIT - BOT BYBIT                                  ║
echo ╚══════════════════════════════════════════════════════════════════════╝
echo.
echo 💾 Voulez-vous sauvegarder vos modifications sur GitHub ?
echo.
echo Pour annuler, appuyez sur Ctrl+C ou fermez cette fenêtre.
echo.
echo ═══════════════════════════════════════════════════════════════════════
echo.

REM Lancer le script Python
python git_save.py

echo.
echo ═══════════════════════════════════════════════════════════════════════
echo.
echo Appuyez sur une touche pour fermer...
pause >nul
