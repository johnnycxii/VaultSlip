# Rotates logs and creates a timestamped backup of data/ + logs/
param(
  [string]$Root = (Resolve-Path "$PSScriptRoot\..").Path,
  [int]$KeepZips = 14,
  [int]$RotateMB = 5
)
Set-Location $Root
$logs = Join-Path $Root "logs"
$archive = Join-Path $logs "archive"
$backups = Join-Path $Root "backups"
New-Item -ItemType Directory -Force -Path $logs,$archive,$backups | Out-Null

# 1) rotate big .log files
Get-ChildItem $logs -File -Filter *.log -ErrorAction SilentlyContinue | ForEach-Object {
  if ($_.Length -ge ($RotateMB * 1MB)) {
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $dest = Join-Path $archive ("{0}_{1}.log" -f $_.BaseName, $stamp)
    Move-Item $_.FullName $dest -Force
    New-Item -ItemType File -Path $_.FullName -Force | Out-Null
  }
}

# 2) make zip backup of data/ + logs/
Add-Type -AssemblyName System.IO.Compression.FileSystem
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$zip = Join-Path $backups ("vaultslip_backup_{0}.zip" -f $ts)
$tmpdir = Join-Path $backups ("__stage_{0}" -f [System.Guid]::NewGuid())
New-Item -ItemType Directory -Force -Path $tmpdir | Out-Null
if (Test-Path "$Root\data") { Copy-Item "$Root\data" -Destination (Join-Path $tmpdir "data") -Recurse -Force }
Copy-Item $logs -Destination (Join-Path $tmpdir "logs") -Recurse -Force
[System.IO.Compression.ZipFile]::CreateFromDirectory($tmpdir, $zip)
Remove-Item $tmpdir -Recurse -Force

# 3) keep last N zips
Get-ChildItem $backups -Filter "vaultslip_backup_*.zip" -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending | Select-Object -Skip $KeepZips | Remove-Item -Force

Write-Host "[rotate+backup] wrote $zip (keeping last $KeepZips)"
