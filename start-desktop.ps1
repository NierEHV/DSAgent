Set-Location $PSScriptRoot
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  DS Agent Desktop Launcher" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "[1/2] Starting Docker..." -ForegroundColor Yellow
try { docker compose up -d } catch { docker-compose up -d }
Start-Sleep 3

Write-Host "[2/2] Launching desktop..." -ForegroundColor Yellow
python desktop.py
