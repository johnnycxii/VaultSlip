# VaultSlip Build Protocol v3.0  
**Zero Drift Edition â€” Full Lifecycle**  
*From absolute zero â†’ production-scale deployment*

---

## ðŸŽ¯ Mission
VaultSlip is a **zero-dependency, chain-native** asset recovery and claim automation protocol designed to run fully autonomously from a single laptop or server.  
The system must:
- Launch in complete, operational state on first run.
- Generate real claimable asset sweeps from day one.
- Maintain security, stealth, and resilience against changes in chain environments.

---

## ðŸ“ Folder & File Setup (Steps 1â€“5)

**Step 1 â€” Create Base Folder**
- Create `VaultSlip/` root directory.
- Create `.venv` Python virtual environment.
- Activate `.venv`.

**Step 2 â€” Create Folder Structure**
VaultSlip/
â”‚
â”œâ”€â”€ vaultslip/
â”‚ â”œâ”€â”€ init.py
â”‚ â”œâ”€â”€ config/
â”‚ â”‚ â”œâ”€â”€ init.py
â”‚ â”‚ â””â”€â”€ settings.py
â”‚ â”œâ”€â”€ constants/
â”‚ â”‚ â”œâ”€â”€ init.py
â”‚ â”‚ â””â”€â”€ patterns.py
â”‚ â”œâ”€â”€ logging_utils/
â”‚ â”‚ â”œâ”€â”€ init.py
â”‚ â”‚ â””â”€â”€ log_setup.py
â”‚ â”œâ”€â”€ telemetry/
â”‚ â”‚ â”œâ”€â”€ init.py
â”‚ â”‚ â””â”€â”€ metrics.py
â”‚ â”œâ”€â”€ wallet/
â”‚ â”‚ â”œâ”€â”€ init.py
â”‚ â”‚ â”œâ”€â”€ wallet_manager.py
â”‚ â”‚ â””â”€â”€ wallet_sweeper.py
â”‚ â”œâ”€â”€ chains/
â”‚ â”‚ â”œâ”€â”€ init.py
â”‚ â”‚ â”œâ”€â”€ registry.py
â”‚ â”‚ â””â”€â”€ eth.py
â”‚ â”œâ”€â”€ discovery/
â”‚ â”‚ â”œâ”€â”€ init.py
â”‚ â”‚ â””â”€â”€ bytecode_scanner.py
â”‚ â”œâ”€â”€ verifier/
â”‚ â”‚ â”œâ”€â”€ init.py
â”‚ â”‚ â””â”€â”€ simulation.py
â”‚ â”œâ”€â”€ safety/
â”‚ â”‚ â”œâ”€â”€ init.py
â”‚ â”‚ â””â”€â”€ filters.py
â”‚ â”œâ”€â”€ executor/
â”‚ â”‚ â”œâ”€â”€ init.py
â”‚ â”‚ â””â”€â”€ claim_router.py
â”‚ â”œâ”€â”€ state/
â”‚ â”‚ â”œâ”€â”€ init.py
â”‚ â”‚ â””â”€â”€ models.py
â”‚ â”œâ”€â”€ data/
â”‚ â”‚ â”œâ”€â”€ init.py
â”‚ â”‚ â””â”€â”€ queue.json
â”‚ â”œâ”€â”€ logs/
â”‚ â”‚ â”œâ”€â”€ app.log
â”‚ â”‚ â”œâ”€â”€ claims.log
â”‚ â”‚ â”œâ”€â”€ queue.log
â”‚ â”‚ â””â”€â”€ security.log
â”‚ â””â”€â”€ run.py
â”‚
â”œâ”€â”€ tests/
â”‚ â”œâ”€â”€ init.py
â”‚ â”œâ”€â”€ test_patterns.py
â”‚ â”œâ”€â”€ test_safety.py
â”‚ â””â”€â”€ test_simulation.py
â”‚
â”œâ”€â”€ .env
â”œâ”€â”€ requirements.txt
â””â”€â”€ README.md

go
Copy code

**Step 3 â€” Install Requirements**
```bash
pip install -r requirements.txt
Step 4 â€” Configure .env
Example:

env
Copy code
APP_ENV=prod
BOT_TOKEN=xxxx
CHAT_ID=xxxx
CHAINS=ETH,POLY,CELO
RPC_URI_ETH=...
RPC_URI_POLY=...
RPC_URI_CELO=...
HOT_WALLET_MNEMONIC="..."
HOT_WALLET_COUNT=12
SWEEP_WALLET=0x...
MIN_PROFIT_USD=5
GAS_MAX_GWEI=60
GAS_SAFETY_MULTIPLIER=1.15
WALLET_ROTATION_EVERY=7
CLAIM_INTERVAL_SECONDS=45
MAX_PARALLEL_CLAIMS=1
REQUIRE_HISTORY=false
POST_CLAIM_SWEEP=true
Step 5 â€” Init Files

All __init__.py exist (even if empty).

Purpose: treat every folder as a Python package.

âš™ï¸ Core Build Sequence (Steps 6â€“20)
Step 6 â€” vaultslip/config.py

Load .env, expose settings.

Step 7 â€” vaultslip/constants.py

Shared constants (opcode bytes, deny lists, defaults).

Step 8 â€” vaultslip/logging_utils.py

JSON logs to logs/app.log, logs/security.log, logs/claims.log.

Step 9 â€” vaultslip/telemetry.py

Telegram send with error logging.

Step 10 â€” Chains

vaultslip/chains/registry.py (enable/URIs/status).

vaultslip/chains/evm_client.py (Web3 client factory).

Step 11 â€” State

vaultslip/state/models.py (Candidate, ClaimResult, etc.).

vaultslip/state/store.py (seen keys, simple KV on disk).

Step 12 â€” Discovery: signatures

vaultslip/discovery/signatures.py (FUNCTION_NAMES, BYTECODE_PATTERNS).

Step 13 â€” Discovery: bytecode scanner

vaultslip/discovery/bytecode_scanner.py (pattern match in code).

Step 14 â€” Discovery: event scanner

vaultslip/discovery/event_scanner.py (chunked recent logs).

Step 15 â€” Discovery: intake

vaultslip/discovery/intake.py (dedupe, persist).

Step 16 â€” Verifier: ABI fetch/cache

vaultslip/verifier/abi_fetch.py.

Step 17 â€” Verifier: zero-arg sim

vaultslip/verifier/claim_sim.py.

Step 18 â€” Verifier: history heuristic

vaultslip/verifier/history_check.py.

Step 19 â€” Safety: honeypot rules

vaultslip/safety/honeypot_rules.py (hard deny: delegatecall; soft: create2/selfdestruct; ABI warns).

Step 20 â€” Safety: gas/profit sentry

vaultslip/safety/gas_sentry.py.

ðŸ‘› Wallet & Execution Scaffolding (Steps 21â€“27)
Step 21 â€” Wallet keyring

vaultslip/wallet/keyring.py (HD derive, no secrets logged).

Step 22 â€” Wallet nonce/gas helpers

vaultslip/wallet/nonce_manager.py

vaultslip/wallet/gas.py

Step 23 â€” Scheduler

vaultslip/executor/scheduler.py (jitter, rotation, rate-limit).

Step 24 â€” Sweeper (draft only)

vaultslip/executor/sweeper.py (native & ERC20 drafts).

Step 25 â€” Claim router (dry-run)

vaultslip/executor/claim_router.py (re-sim â†’ safety â†’ history â†’ gas â†’ draft tx).

Step 26 â€” Claim router + sweep drafts

Adds optional post-claim sweep drafts (dry-run) behind POST_CLAIM_SWEEP.

Step 27 â€” Runner (single entrypoint CLI)

run.py with subcommands: discover, route (no-op alone), cycle.

ðŸ§ª Tests & Backfill (Steps 28â€“30)
Step 28 â€” Backfill script

scripts/backfill_index.py (seed addresses â†’ intake).

Step 29 â€” Tests

tests/test_patterns.py, tests/test_safety.py, tests/test_simulation.py, tests/conftest.py.

Step 30 â€” Green suite

pytest -q must pass.

ðŸš€ Production Readiness (Steps 31â€“35)
Step 31 â€” Live-send toggle & signer path (guarded)

EXECUTE_LIVE=false default; sender module uses nonce manager & gas limits.

Mirror all dry-run logs in live path.

Step 32 â€” Value estimator v1

Read-only payout estimates (balance deltas, common return decoding).

Step 33 â€” ABI-aware simulation

If ABI present, try safe parameterized eth_call variants; decode revert reasons.

Step 34 â€” Token sweep config

Per-chain token list (USDC/WETH/etc) + ERC20 sweep drafts end-to-end.

Step 35 â€” Resilience

RPC retry/backoff policy, autosize chunks, throttle adaption.

ðŸ“ˆ Expansion & Scaling (Steps 36â€“50)
Step 36 â€” Allow/block policy

Default allowlists, stricter history thresholds; maintenance commands.

Step 37 â€” Metrics

Daily profit report, gas spend, success rate (file or lightweight HTML).

Step 38 â€” Deployment

Single host service (systemd/PM2); log rotation; backups.

Step 39 â€” Multi-chain growth

Add EVM-compatible chains; tune params.

Step 40 â€” Executor parallelism

Safe parallel claim attempts (nonce isolation per wallet).

Step 41 â€” Advanced sims

Callpath branching, storage reads for value signals.

Step 42 â€” Prioritization

Rank candidates by estimated payout/gas â†’ route top-N.

Step 43 â€” Mempool hygiene

Private RPC, replacement policy, tip caps.

Step 44 â€” Key hygiene

Rotation cadence, hotâ†’cold sweep schedule, drift alarms.

Step 45 â€” Ops guardrails

Kill-switch, cooldowns, rate-limit clamps.

Step 46 â€” CI/CD

Lint, tests, packaging, release tags.

Step 47 â€” Docs

README quickstart, ops playbook, troubleshooting.

Step 48 â€” Audit pass

Internal review of safety gates; dry-run snapshots archived.

Step 49 â€” Alpha â†’ Prod toggle

ENV presets, feature flags; staged ramp.

Step 50 â€” Autonomy mode

Unattended cycles, daily report, alert-on-anomaly only.

ðŸ“Š Current Build Progress
<!-- PROGRESS_TABLE_START -->
| Step Range | Description | Status | Notes |
|------------|-------------|--------|-------|
| 1-5 | Folder & file setup |  Complete | Structure, venv, env, init files done |
| 6-20 | Core build sequence |  Complete | Config, constants, logging, telemetry, chains, state, discovery, verifier, safety |
| 21-27 | Wallet & execution scaffold |  Complete | Keyring, nonce/gas, scheduler, sweeper drafts, router w/ sweeps |
| 28-30 | Tests & backfill |  Complete | Backfill script and tests; pytest green |
| 31-35 | Production readiness |  Complete | Live-send toggle, estimator v1, ABI-aware sims, token sweep config, resilience |
| 36-50 | Expansion & scaling |  Not Started | Not started |
<!-- PROGRESS_TABLE_END -->


<!-- PROGRESS_METRICS_START -->
**Completion (by protocol steps):** **70.0%**
**Functional readiness:** **70.0%**
**Resume at:** Step 36
<!-- PROGRESS_METRICS_END -->

python .\scripts\update_progress.py
git add .\docs\protocol.md .\progress_status.json
git commit -m "Progress: Step 46 CI green"
git push
python .\scripts\update_progress.py
git add .\docs\protocol.md .\progress_status.json
git commit -m "Progress: Step 46 CI green"
git push
python .\scripts\update_progress.py
git add .\docs\protocol.md .\progress_status.json
git commit -m "Progress: Step 46 CI green"
git push
python .\scripts\update_progress.py
git add .\docs\protocol.md .\progress_status.json
git commit -m "Progress: Step 46 CI green"
git push

