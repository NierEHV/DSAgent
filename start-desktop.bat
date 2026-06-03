@echo off
cd /d "%~dp0"
echo ========================================
echo   DS Agent Desktop Launcher
echo ========================================
echo.

echo [1/2] Starting Docker backend...
docker compose up -d 2>nul || docker-compose up -d
echo.

echo [2/2] Launching desktop app...
python desktop.py
pause
