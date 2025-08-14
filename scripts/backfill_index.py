# scripts/backfill_index.py
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import List
from vaultslip.discovery.bytecode_scanner import scan_batch
from vaultslip.discovery.intake import intake_single_batch

def load_addresses(path: str) -> List[str]:
    p = Path(path)
    if not p.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return []
    txt = p.read_text(encoding="utf-8").strip()
    # Accept JSON array or newline list
    try:
        arr = json.loads(txt)
        if isinstance(arr, list):
            return [str(a).strip() for a in arr if str(a).strip()]
    except Exception:
        pass
    return [ln.strip() for ln in txt.splitlines() if ln.strip()]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chain", required=True)
    ap.add_argument("--file", required=True, help="file with addresses (json array or newline-separated)")
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()

    addrs = load_addresses(args.file)[: args.limit]
    if not addrs:
        print("No addresses loaded.")
        return

    cands = scan_batch(args.chain.upper(), addrs)
    accepted = intake_single_batch(cands)
    print(f"accepted={len(accepted)}")
    for c in accepted:
        print(f"{c.chain}:{c.contract}:{c.pattern}")

if __name__ == "__main__":
    main()
