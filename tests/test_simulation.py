# tests/test_simulation.py
from vaultslip.state.models import Candidate
from vaultslip.verifier.claim_sim import simulate_candidate

def test_sim_returns_result_object():
    c = Candidate(chain="ETH", contract="0x0000000000000000000000000000000000000001", origin="bytecode", pattern="open_claim")
    r = simulate_candidate(c)
    assert hasattr(r, "ok")
