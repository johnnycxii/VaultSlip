# VaultSlip Troubleshooting

## 1) Preset / live switch
- Dry-run:  `.env.alpha`  (EXECUTE_LIVE=false)
- Live:     `.env.prod`   (EXECUTE_LIVE=true)

**Switch presets:**
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\use_preset.ps1 -Preset alpha
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\use_preset.ps1 -Preset prod

**Quick flip only EXECUTE_LIVE (no preset copy):**
(Get-Content .\.env) -replace '^EXECUTE_LIVE\s*=.*','EXECUTE_LIVE=true'  | Set-Content .\.env
(Get-Content .\.env) -replace '^EXECUTE_LIVE\s*=.*','EXECUTE_LIVE=false' | Set-Content .\.env

## 2) Common dry-run messages
- `safety_blocked: ['delegatecall_in_runtime', 'selfdestruct_in_runtime', 'create2_in_runtime']`
  - By design: these are hard-deny bytecodes. Candidate is skipped.
- `history_not_verified: no_successful_logs_found (0)`
  - Signal is weak (no prior successful claims). Discovery is working; router declines.

## 3) Guardrails not running / errors flood
State file: `data\runtime_guard.json`
- To reset state safely: `Remove-Item .\data\runtime_guard.json -ErrorAction SilentlyContinue; '{}' | Out-File -Encoding utf8 .\data\runtime_guard.json`

## 4) `.env` contents not applied
Reload current session:

## 5) Cycle log looks garbled (NUL blocks)
- Ensure scripts write with UTF-8: our scripts already use `Out-File -Encoding utf8`.
- If VS Code renders weirdly, close/reopen the file; or run:
  `Get-Content .\logs\cycle.out -Tail 60`

## 6) GitHub Actions stays red
- Our baseline marks deps/import/tests as non-fatal. Open **Actions  last run  red step** and copy last ~10 lines into an issue; usually a transient network or pip resolver hiccup. Re-run job.

## 7) Scheduled task didnt run
- Query: `schtasks /Query /TN "VaultSlip - Rotate & Backup" /V /FO LIST`
- Run now: `schtasks /Run /TN "VaultSlip - Rotate & Backup"`
- Update action/trigger: recreate with the known-good `schtasks /Create ...` command from the docs.

## 8) Where things are logged
- Main: `logs\cycle.out`
- App/security: `logs\app.log`, `logs\security.log`
- Reviews/CSV: `data\review\*`

