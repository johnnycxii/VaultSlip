# vaultslip/chains/evm_client.py
"""
Unified Web3 client factory + simple health checks.
- Uses HTTP providers defined in settings.RPCS
- Exposes get_client(chain_cfg) and ping(chain_name) helpers
"""

from __future__ import annotations

from typing import Optional

from web3 import Web3
from web3.types import RPCEndpoint

from vaultslip.chains.registry import enabled_chains, get_chain
from vaultslip.config import settings


_clients: dict[str, Web3] = {}


def _make_http_provider(uri: str) -> Web3:
    w3 = Web3(Web3.HTTPProvider(uri, request_kwargs={"timeout": 10}))
    return w3


def get_client(chain_cfg) -> Web3:
    """
    Accepts a ChainConfig object and returns a cached Web3 client.
    """
    key = chain_cfg.name.upper()
    if key in _clients:
        return _clients[key]
    w3 = _make_http_provider(chain_cfg.rpc_uri)
    _clients[key] = w3
    return w3


def ping(chain_name: str) -> bool:
    """
    Quick connectivity check for a chain by name.
    Returns True if connected and can fetch latest block number.
    """
    ccfg = get_chain(chain_name)
    if not ccfg:
        return False
    w3 = get_client(ccfg)
    try:
        # is_connected() is a lightweight sanity check
        if not w3.is_connected():
            return False
        # Fetching the latest block ensures basic RPC health
        _ = w3.eth.block_number  # noqa: F841
        return True
    except Exception:
        return False


def list_health() -> dict[str, bool]:
    """
    Returns a dict of {chain_name: healthy_bool} for all enabled chains.
    """
    out: dict[str, bool] = {}
    for ccfg in enabled_chains():
        out[ccfg.name] = ping(ccfg.name)
    return out
