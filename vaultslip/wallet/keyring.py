# vaultslip/wallet/keyring.py
"""
Ephemeral wallet keyring for VaultSlip.
- Derives HOT_WALLET_COUNT addresses from HOT_WALLET_MNEMONIC
- Standard path: m/44'/60'/0'/0/{index}
- Provides address list for rotation and Account objects for signing (executor use)
- Never prints secrets; do NOT log private keys or mnemonic
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from eth_account import Account  # provided by web3 deps
from web3 import Web3

from vaultslip.config import settings

# Required to use mnemonic derivation in eth-account
Account.enable_unaudited_hdwallet_features()


_DERIVATION_PATH = "m/44'/60'/0'/0/{}"


@dataclass(frozen=True, slots=True)
class WalletEntry:
    index: int
    address: str  # checksum address


class Keyring:
    def __init__(self, mnemonic: str, count: int) -> None:
        if not mnemonic or len(mnemonic.split()) < 12:
            raise RuntimeError("HOT_WALLET_MNEMONIC is missing or invalid (need 12+ words).")
        if count <= 0:
            raise RuntimeError("HOT_WALLET_COUNT must be > 0.")
        self._mnemonic = mnemonic
        self._count = int(count)
        self._addresses: List[WalletEntry] = []
        self._derive_all()

    def _derive_all(self) -> None:
        addrs: List[WalletEntry] = []
        for i in range(self._count):
            path = _DERIVATION_PATH.format(i)
            acct = Account.from_mnemonic(self._mnemonic, account_path=path)
            addrs.append(WalletEntry(index=i, address=Web3.to_checksum_address(acct.address)))
        object.__setattr__(self, "_addresses", addrs)

    # ---- Public API ----------------------------------------------------------

    @property
    def size(self) -> int:
        return self._count

    def addresses(self) -> List[str]:
        """Return all derived addresses (checksum)."""
        return [w.address for w in self._addresses]

    def entry(self, index: int) -> WalletEntry:
        """Return WalletEntry at index (no secrets)."""
        if index < 0 or index >= self._count:
            raise IndexError("wallet index out of range")
        return self._addresses[index]

    def account(self, index: int):
        """
        Return an eth_account Account (contains private key in memory).
        Use only for signing inside the executor. Do NOT print it.
        """
        if index < 0 or index >= self._count:
            raise IndexError("wallet index out of range")
        path = _DERIVATION_PATH.format(index)
        return Account.from_mnemonic(self._mnemonic, account_path=path)


# Singleton accessor wired to .env
_keyring_singleton: Keyring | None = None


def get_keyring() -> Keyring:
    global _keyring_singleton
    if _keyring_singleton is None:
        _keyring_singleton = Keyring(settings.HOT_WALLET_MNEMONIC, settings.HOT_WALLET_COUNT)
    return _keyring_singleton
