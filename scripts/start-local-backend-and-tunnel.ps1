# Starts the local FastAPI backend and a Cloudflare quick tunnel, then prints the public URL.
param(
  [int]$Port = 8001
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Start-BackendSafe {
  $py = Join-Path $root '.venv\Scripts\python.exe'
  if (-not (Test-Path $py)) {
    Write-Error "Python venv not found at $py. Create it and install deps first."
  }
  $listening = Test-NetConnection -ComputerName 127.0.0.1 -Port $Port | Select-Object -ExpandProperty TcpTestSucceeded
  if (-not $listening) {
    Write-Host "Starting Uvicorn on 127.0.0.1:$Port ..."
    Start-Process -FilePath $py -ArgumentList @('-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port',"$Port") -WorkingDirectory $root -WindowStyle Hidden | Out-Null
    Start-Sleep -Seconds 2
  }
}

function Get-CloudflaredPathSafe {
  $candidates = @(
    'C:\\Program Files (x86)\\cloudflared\\cloudflared.exe',
    'C:\\Program Files\\Cloudflare\\cloudflared\\cloudflared.exe'
  )
  foreach ($c in $candidates) { if (Test-Path $c) { return $c } }
  try {
    Write-Host 'Installing Cloudflare Tunnel via winget...'
    winget install --id Cloudflare.cloudflared -e --source winget | Out-Null
  } catch { }
  foreach ($c in $candidates) { if (Test-Path $c) { return $c } }
  throw 'cloudflared.exe not found.'
}

function Start-TunnelSafe {
  param([string]$Cloudflared, [int]$Port)
  $out = Join-Path $root 'cloudflared.out.txt'
  $err = Join-Path $root 'cloudflared.err.txt'
  Remove-Item $out,$err -ErrorAction SilentlyContinue
  Write-Host "Starting Cloudflare quick tunnel to http://127.0.0.1:$Port ..."
  Start-Process -FilePath $Cloudflared -ArgumentList @('tunnel','--no-autoupdate','--url',"http://127.0.0.1:$Port") -RedirectStandardOutput $out -RedirectStandardError $err -WindowStyle Hidden | Out-Null

  $public = $null
  1..120 | ForEach-Object {
    Start-Sleep -Milliseconds 500
    if (Test-Path $out) {
      $m = Select-String -Path $out -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -AllMatches | ForEach-Object { $_.Matches } | Select-Object -First 1
      if ($m) { $public = $m.Value; break }
    }
    if (Test-Path $err -and -not $public) {
      $m2 = Select-String -Path $err -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -AllMatches | ForEach-Object { $_.Matches } | Select-Object -First 1
      if ($m2) { $public = $m2.Value; break }
    }
  }
  if ($public) {
    $file = Join-Path $root 'tunnel_url.txt'
    Set-Content -Path $file -Value $public
    Write-Host ("PUBLIC_URL=" + $public)
    return $public
  } else {
    Write-Warning 'No public URL detected yet. Check cloudflared.out.txt / cloudflared.err.txt for details.'
    return $null
  }
}

Start-BackendSafe
$cf = Get-CloudflaredPathSafe
$url = Start-TunnelSafe -Cloudflared $cf -Port $Port
if ($url) { Write-Host "Use this for VITE_API_BASE: $url" } else { exit 1 }
