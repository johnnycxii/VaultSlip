# tests/test_safety.py
from web3 import Web3
from vaultslip.chains.registry import get_chain
from vaultslip.chains.evm_client import get_client
from vaultslip.safety.honeypot_rules import evaluate_safety
from vaultslip.verifier.abi_fetch import fetch_abi

def test_safety_runs_uniswap_router():
    ccfg = get_chain("ETH")
    assert ccfg is not None
    w3 = get_client(ccfg)
    addr = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
    abi = fetch_abi("ETH", addr)  # may be []
    ok, reasons = evaluate_safety(w3, addr, abi)
    assert isinstance(ok, bool)
