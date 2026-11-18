@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv 2>nul || python -m venv .venv
)
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt pyinstaller
".venv\Scripts\pyinstaller.exe" --noconfirm --onefile --noconsole --name FortniteChestCounter run.py
echo.
echo Fertig: dist\FortniteChestCounter.exe
pause
