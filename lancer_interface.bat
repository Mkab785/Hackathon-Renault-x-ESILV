@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Python : commande "python", sinon le lanceur "py" (installe par defaut avec Python pour Windows)
set "PY=python"
python --version >nul 2>&1 || set "PY=py -3"
%PY% --version >nul 2>&1 || (
  echo Python est introuvable. L'installer depuis https://www.python.org/downloads/
  echo en cochant "Add python.exe to PATH", puis relancer ce fichier.
  pause
  exit /b 1
)
%PY% interface\serveur.py
if errorlevel 1 (
  echo.
  echo Le serveur s'est arrete avec une erreur. Si "openpyxl" manque : lancer installer.bat
  pause
)
