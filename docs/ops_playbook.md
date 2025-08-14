# VaultSlip Ops Playbook

This is the quick reference for day-to-day usage.

## 1) Presets & live/dry-run switch

Presets live in the repo; `.env` is the throwaway working file.

- Dry-run preset: `.env.alpha`  (`EXECUTE_LIVE=false`)
- Live preset:    `.env.prod`   (`EXECUTE_LIVE=true` + any prod overrides)

**Switch presets safely:**
```powershell
# from repo root
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\use_preset.ps1 -Preset alpha   # dry run
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\use_preset.ps1 -Preset prod    # live
# set live
(Get-Content .\.env) -replace '^EXECUTE_LIVE\s*=.*','EXECUTE_LIVE=true' | Set-Content .\.env
# set dry-run
(Get-Content .\.env) -replace '^EXECUTE_LIVE\s*=.*','EXECUTE_LIVE=false' | Set-Content .\.env

**2) Create a short troubleshooting page (covers the exact errors you saw):**
```powershell
@'
# VaultSlip Troubleshooting

### 1) `history_not_verified: no_successful_logs_found (0)`
No on-chain proof of successful claims for that contract/method in the recent history window.
- This is expected for many candidates.
- Action: let discovery keep filling queue; only a small % will be viable.

### 2) `safety_blocked: ['delegatecall_in_runtime', 'selfdestruct_in_runtime', 'create2_in_runtime']`
Hard safety rules blocked execution.
- Action: leave them blocked (by design).

### 3) PowerShell Add-Member member already exists
Fixed by the guardrail state init in `cycle_dryrun.ps1` (we added `Ensure-Prop`).

### 4) `.env` confusion / switching
Use presets:
```powershell
.\scripts\use_preset.ps1 -Preset alpha    # dry-run
.\scripts\use_preset.ps1 -Preset prod     # live
# ensure docs/ exists
New-Item -ItemType Directory -Force .\docs | Out-Null

@'
# VaultSlip Ops Playbook (quick reference)

## Presets & live/dry-run switch

Presets are versioned files; `.env` is the working copy the app reads.

- Dry-run preset: `.env.alpha`  (EXECUTE_LIVE=false)
- Live preset:    `.env.prod`   (EXECUTE_LIVE=true)

**Switch presets safely:**
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\use_preset.ps1 -Preset alpha   # dry run
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\use_preset.ps1 -Preset prod    # live

**Fast flip (just EXECUTE_LIVE in current .env):**
# set live
(Get-Content .\.env) -replace '^EXECUTE_LIVE\s*=.*','EXECUTE_LIVE=true'  | Set-Content .\.env
# set dry-run
(Get-Content .\.env) -replace '^EXECUTE_LIVE\s*=.*','EXECUTE_LIVE=false' | Set-Content .\.env

## Core commands
# Dry-run cycle
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\cycle_dryrun.ps1
Get-Content .\logs\cycle.out -Tail 50

# One-off discovery
python .\vaultslip\discovery\intake.py
Get-Content .\data\queue.json | Select-String -SimpleMatch '"chain":'

## Guardrails (env)
OPS_KILL_SWITCH, OPS_MAX_FAILS_PER_HOUR, OPS_COOLDOWN_SECONDS, OPS_DAILY_GAS_USD_BUDGET
State file: .\data\runtime_guard.json

## Logs
logs\cycle.out, logs\app.log, logs\security.log, data\review\*
