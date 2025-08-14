# vaultslip/chains/registry.py
"""
Chain registry for VaultSlip.
- Reads enabled chains from settings.CHAINS
- Resolves RPC URIs from .env into ChainConfig objects
- Provides helpers to list and fetch chain configs
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

from vaultslip.config import settings, ChainConfig


@dataclass(frozen=True)
class ChainStatus:
    name: str
    rpc_uri: Optional[str]
    has_rpc: bool


def enabled_chains() -> List[ChainConfig]:
    """
    Returns ChainConfig entries for each chain in settings.CHAINS
    where an RPC URI is configured. Chains without RPC are skipped
    to avoid downstream connection errors.
    """
    out: List[ChainConfig] = []
    for name in settings.CHAINS:
        uri = settings.RPCS.get(name)
        if uri:
            out.append(ChainConfig(name=name, rpc_uri=uri, chain_id=None))
    return out


def enabled_chain_names() -> List[str]:
    """Convenience list of chain names with an RPC configured."""
    return [c.name for c in enabled_chains()]


def status_all() -> List[ChainStatus]:
    """
    Human-friendly status for all declared chains, including those missing RPCs.
    Useful for setup validation.
    """
    st: List[ChainStatus] = []
    declared = settings.CHAINS
    for name in declared:
        uri = settings.RPCS.get(name)
        st.append(ChainStatus(name=name, rpc_uri=uri, has_rpc=bool(uri)))
    return st


def get_chain(name: str) -> Optional[ChainConfig]:
    """Fetch a specific chain if RPC is configured; else None."""
    name = name.upper()
    uri = settings.RPCS.get(name)
    if not uri:
        return None
    return ChainConfig(name=name, rpc_uri=uri, chain_id=None)
