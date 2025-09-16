@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

cd /d "C:\Users\johan\Desktop\bybit_bot_v0"
if errorlevel 1 (
  echo [ERREUR] Impossible d'acceder au dossier du projet.
  pause
  exit /b 1
)

echo ===============================================
echo  Sauvegarde Git - bybit-trading-bot
echo ===============================================
echo.
set /p message=Message de commit ^>: 
echo.

echo Ajout des modifications...
git add .
if errorlevel 1 (
  echo [ERREUR] Echec de 'git add .'.
  pause
  exit /b 1
)

echo Verification des changements indexes...
git diff --cached --quiet
if errorlevel 2 (
  echo [ERREUR] Echec de verification des changements indexes.
  pause
  exit /b 1
)
if not errorlevel 1 (
  echo Aucun changement detecte. Aucun commit ne sera cree.
  goto push_step
)

echo Creation du commit...
git commit -m "%message%"
if errorlevel 1 (
  echo [ERREUR] Echec du commit. Verifiez le message ou l'etat du repo.
  pause
  exit /b 1
)

:push_step
echo.
echo Envoi vers le depot distant...
git push
if errorlevel 1 (
  echo [ERREUR] Echec du push. Verifiez votre connexion et vos droits.
  pause
  exit /b 1
)

echo.
echo [SUCCES] Sauvegarde terminee avec succes.
pause
exit /b 0


