"""Preset EVM networks for balance scanning (same 0x address, different chains)."""

from __future__ import annotations

from typing import TypedDict


class ChainInfo(TypedDict):
    name: str
    rpc: str
    symbol: str


EVM_CHAINS: dict[str, ChainInfo] = {
    "ethereum": {
        "name": "Ethereum Mainnet",
        "rpc": "https://ethereum.publicnode.com",
        "symbol": "ETH",
    },
    "sepolia": {
        "name": "Sepolia Testnet",
        "rpc": "https://rpc.sepolia.org",
        "symbol": "ETH",
    },
    "polygon": {
        "name": "Polygon",
        "rpc": "https://polygon-rpc.com",
        "symbol": "MATIC",
    },
    "bsc": {
        "name": "BNB Smart Chain",
        "rpc": "https://bsc-dataseed.binance.org",
        "symbol": "BNB",
    },
    "arbitrum": {
        "name": "Arbitrum One",
        "rpc": "https://arb1.arbitrum.io/rpc",
        "symbol": "ETH",
    },
    "custom": {
        "name": "Custom RPC",
        "rpc": "",
        "symbol": "ETH",
    },
}

DEFAULT_CHAIN = "ethereum"
BALANCE_UNIT = "wei"


def chain_keys() -> list[str]:
    return list(EVM_CHAINS.keys())


def chain_label(key: str) -> str:
    info = EVM_CHAINS.get(key, EVM_CHAINS["custom"])
    sym = info["symbol"]
    return f"{info['name']} ({sym})"
