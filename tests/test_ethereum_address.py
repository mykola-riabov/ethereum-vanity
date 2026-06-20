"""Tests for Ethereum address derivation."""

import ecdsa

from ethereum_address import (
    ALLOWED_STRENGTHS,
    DEFAULT_DERIVATION_PATH,
    estimate_difficulty,
    matches_vanity,
    privkey_to_address,
    random_privkey_from_entropy,
    to_checksum_address,
    try_match_privkey,
    validate_pattern,
)


def test_hardhat_account0() -> None:
    priv = bytes.fromhex("ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80")
    assert privkey_to_address(priv) == "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"


def test_checksum_known() -> None:
    assert to_checksum_address("0x529084064985278230fb9293318db598bfc67788") == (
        "0x529084064985278230Fb9293318DB598bFC67788"
    )


def test_vanity_match_case_insensitive() -> None:
    addr = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
    assert matches_vanity(addr, "0xf39f", "")
    assert matches_vanity(addr, "f39f", "")


def test_try_match_prefix() -> None:
    priv = bytes.fromhex("ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80")
    addr = privkey_to_address(priv)
    assert try_match_privkey(priv, "0xf39f", "", checksum=True) == addr


def test_validate_rejects_bad_hex() -> None:
    try:
        validate_pattern("0xGHI", "")
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "hex" in str(e).lower()


def test_estimate_difficulty() -> None:
    d = estimate_difficulty("0xdead", "")
    assert d.charset_size == 16
    assert d.constrained_chars == 4
    assert d.expected_attempts == 16**4


def test_random_key_on_curve() -> None:
    priv = random_privkey_from_entropy(256)
    n = int.from_bytes(priv, "big")
    assert 1 <= n < ecdsa.SECP256k1.order
    assert privkey_to_address(priv).startswith("0x")


def test_default_path_constant() -> None:
    assert DEFAULT_DERIVATION_PATH == "m/44'/60'/0'/0/0"
    assert 256 in ALLOWED_STRENGTHS
