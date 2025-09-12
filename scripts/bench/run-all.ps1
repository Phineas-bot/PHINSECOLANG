param(
  [int]$N = 5000000,
  [int]$Warmup = 1,
  [int]$Runs = 5
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
# Repo root is two levels up from this script (scripts/bench -> scripts -> repo)
$repo = Split-Path -Parent (Split-Path -Parent $root)
$py = Join-Path $repo ".venv/Scripts/python.exe"
$wrap = Join-Path $repo "scripts/greenwrap.py"
$benchDir = $root

function Invoke-WrappedRun {
  param([string]$Cmd, [string]$Name)
  Write-Host "--> $Name" -ForegroundColor Cyan
  $env:ECO_BENCH_N = $N
  try {
    $json = & $py $wrap --cmd $Cmd --warmup $Warmup --runs $Runs 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $json) {
      Write-Warning "Wrapper failed for $Name (exit $LASTEXITCODE). Skipping."
      return $null
    }
    $obj = $json | ConvertFrom-Json
  } catch {
    Write-Warning ("Error running {0}: {1}" -f $Name, $_)
    return $null
  }
  [pscustomobject]@{
    name      = $Name
    elapsed_s = [math]::Round($obj.elapsed_s, 6)
    ops       = $obj.ops
    energy_J  = [math]::Round($obj.energy_J, 9)
    co2_g     = [math]::Round($obj.co2_g, 9)
  }
}

$rows = @()

# Python
if (Test-Path (Join-Path $benchDir "bench.py")) {
  $r = Invoke-WrappedRun -Cmd "$py `"$benchDir/bench.py`"" -Name "Python"
  if ($r) { $rows += $r }
}

# Node.js
if (Get-Command node -ErrorAction SilentlyContinue) {
  if (Test-Path (Join-Path $benchDir "bench.js")) {
    $r = Invoke-WrappedRun -Cmd "node `"$benchDir/bench.js`"" -Name "Node"
    if ($r) { $rows += $r }
  }
}

# Java
if (Get-Command javac -ErrorAction SilentlyContinue) {
  $javaSrc = Join-Path $benchDir "Bench.java"
  if (Test-Path $javaSrc) {
  Push-Location $benchDir
  javac Bench.java
  Pop-Location
  $r = Invoke-WrappedRun -Cmd "java -cp `"$benchDir`" Bench" -Name "Java"
  if ($r) { $rows += $r }
  }
}

# C (cl or gcc/clang)
$cSrc = Join-Path $benchDir "bench.c"
if (Test-Path $cSrc) {
  $exe = Join-Path $benchDir "bench_c.exe"
  if (Get-Command cl -ErrorAction SilentlyContinue) {
    Push-Location $benchDir
    cl /O2 /Fe:bench_c.exe bench.c | Out-Null
    Pop-Location
  } elseif (Get-Command gcc -ErrorAction SilentlyContinue) {
    & gcc -O3 -o $exe $cSrc
  } elseif (Get-Command clang -ErrorAction SilentlyContinue) {
    & clang -O3 -o $exe $cSrc
  }
  if (Test-Path $exe) {
    $r = Invoke-WrappedRun -Cmd "`"$exe`"" -Name "C"
    if ($r) { $rows += $r }
  }
}

# C++ (cl or g++/clang++)
$cppSrc = Join-Path $benchDir "bench.cpp"
if (Test-Path $cppSrc) {
  $exe = Join-Path $benchDir "bench_cpp.exe"
  if (Get-Command cl -ErrorAction SilentlyContinue) {
    Push-Location $benchDir
    cl /O2 /Fe:bench_cpp.exe bench.cpp | Out-Null
    Pop-Location
  } elseif (Get-Command g++ -ErrorAction SilentlyContinue) {
    & g++ -O3 -o $exe $cppSrc
  } elseif (Get-Command clang++ -ErrorAction SilentlyContinue) {
    & clang++ -O3 -o $exe $cppSrc
  }
  if (Test-Path $exe) {
    $r = Invoke-WrappedRun -Cmd "`"$exe`"" -Name "C++"
    if ($r) { $rows += $r }
  }
}

if ($rows.Count -eq 0) {
  Write-Warning "No benchmarks ran. Ensure interpreters/compilers are installed."
  exit 1
}

$rows | Sort-Object elapsed_s | Format-Table -AutoSize
