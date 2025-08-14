# vaultslip/safety/honeypot_rules.py
"""
Honeypot / trap heuristics for VaultSlip.
- Hard-deny: DELEGATECALL (0xf4)
- Soft-warn: SELFDESTRUCT (0xff), CREATE2 (0xf5)
- ABI soft-warn: approve(address,uint256) present (we never call approves)
evaluate_safety() -> (ok: bool, reasons: list[str])
"""
from __future__ import annotations
from typing import Dict, List, Tuple
from web3 import Web3
from vaultslip.verifier.abi_fetch import has_function

_HARD_DENY = {"delegatecall_in_runtime": "0xf4"}        # DELEGATECALL
_SOFT_WARN = {"selfdestruct_in_runtime": "0xff",         # SELFDESTRUCT
              "create2_in_runtime": "0xf5"}              # CREATE2
_ABI_SOFT_DENY = {"approve(address,uint256)"}

def _opcode_present(code_hex: str, opcode_hex: str) -> bool:
    try:
        if not code_hex or not code_hex.startswith("0x"):
            return False
        code = bytes.fromhex(code_hex[2:])
        target = bytes.fromhex(opcode_hex[2:] if opcode_hex.startswith("0x") else opcode_hex)
        return target in code
    except Exception:
        return False

def bytecode_flags(code_hex: str) -> Tuple[List[str], List[str]]:
    hard, soft = [], []
    for name, op in _HARD_DENY.items():
        if _opcode_present(code_hex, op): hard.append(name)
    for name, op in _SOFT_WARN.items():
        if _opcode_present(code_hex, op): soft.append(name)
    return hard, soft

def abi_flags(abi: List[Dict]) -> List[str]:
    soft = []
    for deny in _ABI_SOFT_DENY:
        fn_name = deny.split("(")[0]
        if has_function(abi or [], fn_name):
            soft.append(f"abi_warn:{deny}")
    return soft

def evaluate_safety(w3, address: str, abi: List[Dict]) -> Tuple[bool, List[str]]:
    try:
        code_hex = w3.eth.get_code(Web3.to_checksum_address(address)).hex()
    except Exception:
        return False, ["code_fetch_failed"]
    hard, soft = bytecode_flags(code_hex)
    soft += abi_flags(abi or [])
    if hard: return False, hard + soft
    return True, soft
