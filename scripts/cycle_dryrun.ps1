Param()

# --- repo roots & folders --------------------------------------
$scriptDir = $PSScriptRoot
if (-not $scriptDir) { $scriptDir = (Resolve-Path ".").Path }
$repo = (Resolve-Path (Join-Path $scriptDir "..")).Path

Set-Location $repo
if (-not (Test-Path ".\logs")) { New-Item -ItemType Directory -Force -Path ".\logs" | Out-Null }
if (-not (Test-Path ".\data")) { New-Item -ItemType Directory -Force -Path ".\data" | Out-Null }

# --- .env loader (tolerant; strips trailing comments) ----------
function Load-DotEnv {
  if (-not (Test-Path ".\.env")) { return }
  Get-Content .\.env | ForEach-Object {
    $line = $_.Trim()
    if ($line -eq "" -or $line.StartsWith("#")) { return }
    $pair = $line -split "=", 2
    if ($pair.Count -ne 2) { return }
    $k = $pair[0].Trim(); $v = $pair[1].Trim()
    # strip surrounding quotes
    if (($v.StartsWith('"') -and $v.EndsWith('"')) -or ($v.StartsWith("'") -and $v.EndsWith("'"))) {
      if ($v.Length -ge 2) { $v = $v.Substring(1, $v.Length-2) }
    }
    # strip trailing inline comment
    $v = ($v -replace '\s+#.*$', '').Trim()
    [Environment]::SetEnvironmentVariable($k, $v, "Process") | Out-Null
  }
}
Load-DotEnv

function EnvOr([string]$name, [string]$def) {
  $v = [Environment]::GetEnvironmentVariable($name)
  if ([string]::IsNullOrWhiteSpace($v)) { return $def } else { return $v }
}
function ToIntSafe([string]$s, [int]$def) {
  if ([string]::IsNullOrWhiteSpace($s)) { return $def }
  $m = [regex]::Match($s, '^-?\d+')
  if ($m.Success) { return [int]$m.Value } else { return $def }
}
function ToDoubleSafe([string]$s, [double]$def) {
  if ([string]::IsNullOrWhiteSpace($s)) { return $def }
  $m = [regex]::Match($s, '^-?\d+(\.\d+)?')
  if ($m.Success) { return [double]$m.Value } else { return $def }
}

# --- Ops knobs --------------------------------------------------
$execLive  = EnvOr "EXECUTE_LIVE" "false"
$rpc       = EnvOr "RPC_URI_ETH" "<unset>"

$KILL      = ToIntSafe    (EnvOr "OPS_KILL_SWITCH" "0")            0
$MAXFAIL   = ToIntSafe    (EnvOr "OPS_MAX_FAILS_PER_HOUR" "3")     3
$COOLDOWN  = ToIntSafe    (EnvOr "OPS_COOLDOWN_SECONDS" "900")     900
$BUDGETUSD = ToDoubleSafe (EnvOr "OPS_DAILY_GAS_USD_BUDGET" "0")   0.0  # 0 = unlimited

# --- header -----------------------------------------------------
$stamp = Get-Date -Format o
$hdr = "[cycle v13] {0} EXECUTE_LIVE={1} RPC={2}" -f $stamp, $execLive, $rpc
Write-Host $hdr
Add-Content -Path .\logs\cycle.out -Value $hdr

# --- state file -------------------------------------------------
$statePath = ".\data\runtime_guard.json"
if (-not (Test-Path $statePath)) { "{}" | Out-File -Encoding utf8 $statePath }
try { $state = Get-Content $statePath -Raw | ConvertFrom-Json } catch { $state = @{} }
if (-not $state.fails)          { $state | Add-Member -NotePropertyName fails -NotePropertyValue @() }
if (-not $state.gas_day)        { $state | Add-Member -NotePropertyName gas_day -NotePropertyValue "" }
if (-not $state.gas_usd_today)  { $state | Add-Member -NotePropertyName gas_usd_today -NotePropertyValue 0.0 }

# --- pre-checks: kill / cooldown / daily gas budget ------------
if ($KILL -eq 1) {
  $line = "[guard] kill switch active  skipping run"
  Write-Host $line; Add-Content .\logs\cycle.out $line
  exit 0
}

$now = Get-Date
if ($state.cooldown_until) {
  try {
    $cu = [DateTime]::Parse($state.cooldown_until)
    if ($cu -gt $now) {
      $line = "[guard] cooldown active until {0}  skipping run" -f $cu.ToString("o")
      Write-Host $line; Add-Content .\logs\cycle.out $line
      exit 0
    }
  } catch { }
}

$today = (Get-Date -Format "yyyy-MM-dd")
$gasToday = [double]$state.gas_usd_today
if ($state.gas_day -ne $today) { $state.gas_day = $today; $gasToday = 0.0 }
if ($BUDGETUSD -gt 0 -and $gasToday -ge $BUDGETUSD) {
  $line = "[guard] daily gas budget reached ({0} >= {1} USD)  skipping run" -f $gasToday, $BUDGETUSD
  Write-Host $line; Add-Content .\logs\cycle.out $line
  $state.gas_usd_today = $gasToday
  $state | ConvertTo-Json -Depth 8 | Out-File -Encoding utf8 $statePath
  exit 0
}

# --- run inline cycle (non-terminating stderr) ------------------
$py = Join-Path $repo ".venv\Scripts\python.exe"; if (-not (Test-Path $py)) { $py = "python" }
$inline = Join-Path $repo "scripts\cycle_inline_runner.py"

$cmdLine = "[cycle] cmd: `"{0}`" `"{1}`"" -f $py, $inline
Write-Host $cmdLine
Add-Content -Path .\logs\cycle.out -Value $cmdLine

$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
  $out = & $py $inline 2>&1
  $ec  = $LASTEXITCODE
} finally {
  $ErrorActionPreference = $prevEAP
}
if ($null -eq $out) { $out = @() }
$out | Tee-Object -FilePath .\logs\cycle.out -Append | Out-Null

# --- parse results ----------------------------------------------
$ran=0;$ok=0;$errs=0
foreach ($line in $out) {
  if ($line -match 'summary:\s*ran=(\d+)\s+ok=(\d+)\s+errs=(\d+)') {
    $ran  = [int]$matches[1]; $ok = [int]$matches[2]; $errs = [int]$matches[3]
    break
  }
}
$gasAdd = 0.0
foreach ($line in $out) {
  if ($line -match 'gas_usd=([0-9]*\.?[0-9]+)') {
    $gasAdd += [double]$matches[1]
  }
}

# update error window (last hour)
for ($i=0; $i -lt $errs; $i++) { $state.fails += (Get-Date).ToString("o") }
$cut = (Get-Date).AddHours(-1)
$state.fails = @($state.fails | Where-Object { try { [DateTime]::Parse($_) -gt $cut } catch { $false } })

if ($MAXFAIL -gt 0 -and $state.fails.Count -gt $MAXFAIL) {
  $until = (Get-Date).AddSeconds($COOLDOWN)
  $state.cooldown_until = $until.ToString("o")
  $note = "[guard] failure rate exceeded ({0}>{1})  cooldown {2}s until {3}" -f $state.fails.Count, $MAXFAIL, $COOLDOWN, $state.cooldown_until
  Write-Host $note; Add-Content .\logs\cycle.out $note
}

# accumulate gas
$gasToday = [math]::Round($gasToday + $gasAdd, 4)
$state.gas_day = $today
$state.gas_usd_today = $gasToday

# persist state
$state | ConvertTo-Json -Depth 8 | Out-File -Encoding utf8 $statePath

# final summary (also written to log)
$final = "[guard] summary ran={0} ok={1} errs={2} gas_usd_added={3} gas_usd_today={4}" -f $ran,$ok,$errs,$gasAdd,$gasToday
Write-Host $final
Add-Content -Path .\logs\cycle.out -Value $final

exit 0
