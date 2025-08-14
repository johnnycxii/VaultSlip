Param()
$ErrorActionPreference = "Stop"

# repo root
$root = Split-Path -Parent $PSScriptRoot
if (-not $root) { $root = (Resolve-Path ".").Path }
Set-Location $root

# python path
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

# ensure logs dir
if (-not (Test-Path ".\logs")) { New-Item -ItemType Directory -Force -Path ".\logs" | Out-Null }

# inline python that computes active index + address (read-only)
$code = @"
import os, datetime
from eth_account import Account

Account.enable_unaudited_hdwallet_features()

MNEM = os.environ.get('HOT_WALLET_MNEMONIC') or ''
COUNT = int(os.environ.get('HOT_WALLET_COUNT','1'))
ROT_D = int(os.environ.get('WALLET_ROTATION_EVERY_DAYS','7'))

epoch = datetime.datetime(2024,1,1,tzinfo=datetime.timezone.utc)
now   = datetime.datetime.now(datetime.timezone.utc)
days  = (now - epoch).days
active = (days // max(1, ROT_D)) % max(1, COUNT)

def derive(i):
    try:
        return Account.from_mnemonic(MNEM, account_path=f"m/44'/60'/0'/0/{i}").address
    except Exception:
        return None

addr = derive(active)
stamp = datetime.datetime.now().isoformat()
print(f"[rotation_ping] {stamp} active_index={active} address={addr}")
"@

# run the inline python via a temp file, append to logs\rotation.log
$tmp = [System.IO.Path]::GetTempFileName()
[System.IO.File]::WriteAllText($tmp, $code)
& $py $tmp 2>&1 | Tee-Object -FilePath ".\logs\rotation.log" -Append
Remove-Item $tmp -Force
