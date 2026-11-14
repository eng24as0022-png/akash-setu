# Akash Setu - PowerShell Launcher
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "   AKASH SETU (आकाश सेतु) - TACTICAL DISASTER RESPONSE PLATFORM" -ForegroundColor White
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host ""

$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Python 3 was not detected in PATH. Please install Python 3.10+" -ForegroundColor Red
    exit 1
}

Write-Host "Python runtime: $pythonVersion" -ForegroundColor Green
Write-Host "Starting Mission Control Server on http://localhost:8080 ..." -ForegroundColor Yellow
Write-Host "Press Ctrl+C to terminate the server." -ForegroundColor Gray
Write-Host ""

python server.py 8080
