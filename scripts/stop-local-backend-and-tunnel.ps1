# Stops the local FastAPI backend and Cloudflare quick tunnel.
$ErrorActionPreference = 'SilentlyContinue'

# Stop cloudflared
Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force

# Stop backend (the venv python running uvicorn in this repo)
$root = Split-Path -Parent $PSScriptRoot
$venvPy = Join-Path $root '.venv\Scripts\python.exe'
Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $venvPy } | Stop-Process -Force

Write-Host 'Stopped backend and tunnel.'
