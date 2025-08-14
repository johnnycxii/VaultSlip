# tests/test_patterns.py
from vaultslip.discovery.signatures import FUNCTION_NAMES, BYTECODE_PATTERNS
def test_signatures_nonempty():
    assert len(FUNCTION_NAMES) >= 3
    assert "open_claim" in BYTECODE_PATTERNS
