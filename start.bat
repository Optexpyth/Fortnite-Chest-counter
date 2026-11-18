@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Erstelle virtuelle Umgebung ...
    py -3 -m venv .venv 2>nul || python -m venv .venv
    if errorlevel 1 (
        echo Python 3.10+ wurde nicht gefunden. Bitte von https://www.python.org installieren
        echo und beim Setup "Add python.exe to PATH" anhaken.
        pause
        exit /b 1
    )
)

echo Installiere/aktualisiere Abhaengigkeiten ...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 (
    echo Installation fehlgeschlagen.
    pause
    exit /b 1
)

echo Starte Fortnite Chest Counter ...
start "" ".venv\Scripts\pythonw.exe" run.py %*
