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
echo Installation du seul module necessaire : openpyxl (lecture des fichiers .xlsx).
echo Claude Code, Codex et la cle API sont facultatifs et ne sont pas installes ici (voir README.md).
echo.
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Echec de l'installation. Verifier la connexion Internet, puis relancer installer.bat.
) else (
  echo.
  echo Termine. Lancer maintenant lancer_interface.bat
)
pause
