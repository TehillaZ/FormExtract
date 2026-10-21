<#
  Starts the whole app with one server: the database, the built interface, and the API.
  Then open http://localhost:8000

    .\start.ps1            start (builds the interface the first time)
    .\start.ps1 -Seed      also fill the database with the sample forms from saved model answers (no model needed)
    .\start.ps1 -Rebuild   rebuild the interface first (after changing the frontend)

  Needs: Docker Desktop running, Node.js, and the Python environment from the README (backend\.venv).
#>
param([switch]$Seed, [switch]$Rebuild)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Database..." -ForegroundColor Cyan
docker compose up -d --wait db

if ($Rebuild -or -not (Test-Path "frontend\dist\index.html")) {
    Write-Host "Building the interface..." -ForegroundColor Cyan
    Push-Location frontend
    npm install --no-audit --no-fund
    npm run build
    Pop-Location
}

$python = "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Python environment not found. See the README, section Setup." }

if ($Seed) {
    Write-Host "Seeding the sample forms from saved answers..." -ForegroundColor Cyan
    Push-Location backend
    & ".venv\Scripts\python.exe" scripts\seed_demo.py
    Pop-Location
}

Write-Host "Open http://localhost:8000  (Ctrl+C to stop)" -ForegroundColor Green
Push-Location backend
& ".venv\Scripts\python.exe" -m uvicorn app.web:root --port 8000
Pop-Location
