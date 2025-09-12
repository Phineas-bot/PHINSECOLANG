param(
  [object[]]$Ns = @(100000, 200000, 500000, 1000000),
  [int]$Warmup = 1,
  [int]$Runs = 5,
  [string]$OutCsv = "scripts/bench/results.csv",
  [string]$OutMd = "scripts/bench/results.md"
)

$ErrorActionPreference = "Stop"

# Resolve repo root based on this script location
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$py = Join-Path $repo ".venv/Scripts/python.exe"
if (-not (Test-Path $py)) { $py = "python" } # fallback to system python
$wrap = Join-Path $repo "scripts/greenwrap.py"
$benchDir = Join-Path $repo "scripts/bench"

# Coerce Ns into an int array supporting comma-separated strings
$Ns = @($Ns | ForEach-Object {
  if ($_ -is [string]) {
    ($_ -split '[,\s]+' | Where-Object { $_ -match '^\d+$' } | ForEach-Object { [int]$_ })
  } elseif ($_ -is [int]) { $_ } else { [int]$_ }
}) | Where-Object { $_ -gt 0 }

function Invoke-WrappedRun {
  param([string]$Cmd, [int]$N, [string]$Name)
  $env:ECO_BENCH_N = $N
  try {
    $json = & $py $wrap --cmd $Cmd --warmup $Warmup --runs $Runs 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $json) { return $null }
    return ($json | ConvertFrom-Json)
  } catch { return $null }
}

function Initialize-Compilation {
  # Compile Java/C/C++ once if toolchains are present
  if (Get-Command javac -ErrorAction SilentlyContinue) {
    if (Test-Path (Join-Path $benchDir "Bench.java")) {
      Push-Location $benchDir
      try { javac Bench.java | Out-Null } catch {}
      Pop-Location
    }
  }
  if ($null -ne (Get-Command cl -ErrorAction SilentlyContinue)) {
    Push-Location $benchDir
    try { cl /nologo /O2 /Fe:bench_c.exe bench.c | Out-Null } catch {}
    try { cl /nologo /O2 /Fe:bench_cpp.exe bench.cpp | Out-Null } catch {}
    Pop-Location
  } elseif (Get-Command gcc -ErrorAction SilentlyContinue) {
    if (Test-Path (Join-Path $benchDir "bench.c")) { & gcc -O3 -o (Join-Path $benchDir "bench_c.exe") (Join-Path $benchDir "bench.c") }
    if (Test-Path (Join-Path $benchDir "bench.cpp")) { & g++ -O3 -o (Join-Path $benchDir "bench_cpp.exe") (Join-Path $benchDir "bench.cpp") }
  } elseif (Get-Command clang -ErrorAction SilentlyContinue) {
    if (Test-Path (Join-Path $benchDir "bench.c")) { & clang -O3 -o (Join-Path $benchDir "bench_c.exe") (Join-Path $benchDir "bench.c") }
    if (Test-Path (Join-Path $benchDir "bench.cpp")) { & clang++ -O3 -o (Join-Path $benchDir "bench_cpp.exe") (Join-Path $benchDir "bench.cpp") }
  }
}

Initialize-Compilation

$rows = @()

# Build command map for languages available
$langCmds = @{}
if (Test-Path (Join-Path $benchDir "bench.py")) { $langCmds["Python"] = "$py `"$benchDir/bench.py`"" }
if ($null -ne (Get-Command node -ErrorAction SilentlyContinue) -and (Test-Path (Join-Path $benchDir "bench.js"))) { $langCmds["Node"] = "node `"$benchDir/bench.js`"" }
if ($null -ne (Get-Command java -ErrorAction SilentlyContinue) -and (Test-Path (Join-Path $benchDir "Bench.java"))) { $langCmds["Java"] = "java -cp `"$benchDir`" Bench" }
if (Test-Path (Join-Path $benchDir "bench_c.exe")) { $langCmds["C"] = "`"$benchDir/bench_c.exe`"" }
if (Test-Path (Join-Path $benchDir "bench_cpp.exe")) { $langCmds["C++"] = "`"$benchDir/bench_cpp.exe`"" }

if ($langCmds.Count -eq 0) {
  Write-Warning "No languages available. Ensure at least one benchmark exists (Python/Node/Java/C/C++)."
  exit 1
}

foreach ($N in $Ns) {
  foreach ($kv in $langCmds.GetEnumerator()) {
    $name = $kv.Key; $cmd = $kv.Value
    Write-Host ("Running {0} with N={1}" -f $name, $N) -ForegroundColor Cyan
    $obj = Invoke-WrappedRun -Cmd $cmd -N $N -Name $name
  if ($null -ne $obj) {
      $elapsed = [double]$obj.elapsed_s
      $ops = [int64]$obj.ops
      $opsPerS = if ($elapsed -gt 0) { [double]$ops / $elapsed } else { 0 }
      $energyPerOp = if ($ops -gt 0) { [double]$obj.energy_J / [double]$ops } else { 0 }
      $rows += [pscustomobject]@{
        language    = $name
        N           = $N
        elapsed_s   = $elapsed
        ops         = $ops
        ops_per_s   = $opsPerS
        energy_J    = [double]$obj.energy_J
        energy_per_op_J = $energyPerOp
        co2_g       = [double]$obj.co2_g
      }
    } else {
      Write-Warning ("Skipping {0} for N={1} due to error" -f $name, $N)
    }
  }
}

if ($rows.Count -eq 0) {
  Write-Warning "No results collected."
  exit 1
}

# Write CSV
$csvPath = Join-Path $repo $OutCsv
$rows | Sort-Object language, N | Export-Csv -NoTypeInformation -Encoding UTF8 -Path $csvPath
Write-Host ("Wrote CSV: {0}" -f $csvPath) -ForegroundColor Green

# Write Markdown
$mdPath = Join-Path $repo $OutMd
$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine("# Cross-language report")
[void]$sb.AppendLine("")
[void]$sb.AppendLine(("Problem sizes (N): {0}" -f ($Ns -join ", ")))
[void]$sb.AppendLine("")

function Add-Table {
  param([string]$title, [object[]]$data)
  [void]$sb.AppendLine(("## {0}" -f $title))
  [void]$sb.AppendLine("")
  [void]$sb.AppendLine("| Language | N | Elapsed (s) | Ops | Ops/s | Energy (J) | CO2 (g) |")
  [void]$sb.AppendLine("|---|---:|---:|---:|---:|---:|---:|")
  foreach ($r in $data) {
    $line = ("| {0} | {1} | {2:N6} | {3} | {4:N0} | {5:N9} | {6:N9} |" -f $r.language, $r.N, $r.elapsed_s, $r.ops, $r.ops_per_s, $r.energy_J, $r.co2_g)
    [void]$sb.AppendLine($line)
  }
  [void]$sb.AppendLine("")
}

foreach ($N in $Ns) {
  $slice = $rows | Where-Object { $_.N -eq $N } | Sort-Object elapsed_s
  Add-Table -title ("Results for N={0}" -f $N) -data $slice
}

# Overall summary by language (median over Ns)
$byLang = @()
foreach ($lang in ($rows.language | Sort-Object -Unique)) {
  $subset = $rows | Where-Object { $_.language -eq $lang }
  if ($subset.Count -gt 0) {
    $medElapsed = ($subset.elapsed_s | Sort-Object)[[int][math]::Floor(($subset.Count-1)/2)]
    $medOpsPerS = ($subset.ops_per_s | Sort-Object)[[int][math]::Floor(($subset.Count-1)/2)]
    $medEnergy = ($subset.energy_J | Sort-Object)[[int][math]::Floor(($subset.Count-1)/2)]
    $medCO2 = ($subset.co2_g | Sort-Object)[[int][math]::Floor(($subset.Count-1)/2)]
    $byLang += [pscustomobject]@{
      language = $lang
      median_elapsed_s = $medElapsed
      median_ops_per_s = $medOpsPerS
      median_energy_J = $medEnergy
      median_co2_g = $medCO2
    }
  }
}

Add-Table -title "Overall (median across N)" -data ($byLang | Sort-Object median_elapsed_s)

[System.IO.File]::WriteAllText($mdPath, $sb.ToString(), [System.Text.Encoding]::UTF8)
Write-Host ("Wrote Markdown: {0}" -f $mdPath) -ForegroundColor Green
