"""Ethereum / EVM vanity address generation (CPU)."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass

import ecdsa
from bip32_pure import BIP32
from Crypto.Hash import keccak
from mnemonic import Mnemonic

VERSION = "0.1.1"
HARDENED_OFFSET = 0x80000000
ALLOWED_STRENGTHS = [128, 160, 192, 224, 256]
DEFAULT_DERIVATION_PATH = "m/44'/60'/0'/0/0"
HEX_ALPHABET = "0123456789abcdef"
HEX_CHARSET_SIZE = 16

_CURVE_ORDER = ecdsa.SECP256k1.order
_MNEMO = Mnemonic("english")
_HEX_RE = re.compile(r"^[0-9a-fA-F]*$")


@dataclass(frozen=True)
class DifficultyEstimate:
    prefix_chars: int
    suffix_chars: int
    constrained_chars: int
    expected_attempts: float
    overlap_warning: bool
    charset_size: int


def _strip_0x(part: str) -> str:
    p = part.strip()
    if p.lower().startswith("0x"):
        return p[2:]
    return p


def invalid_hex_chars(part: str) -> list[str]:
    body = _strip_0x(part)
    if not _HEX_RE.fullmatch(body):
        return [ch for ch in body if ch.lower() not in HEX_ALPHABET]
    return []


def validate_pattern(prefix: str, suffix: str) -> None:
    for label, part in (("Prefix", prefix), ("Suffix", suffix)):
        if not part:
            continue
        bad = invalid_hex_chars(part)
        if bad:
            raise ValueError(
                f"Invalid hex character(s) in {label}: {', '.join(sorted(set(bad)))}. "
                "EVM addresses use 0-9 and a-f."
            )
        body = _strip_0x(part)
        if len(body) > 40:
            raise ValueError(f"{label} is longer than 40 hex characters (20 bytes).")


def estimate_difficulty(prefix: str, suffix: str) -> DifficultyEstimate:
    prefix_body = _strip_0x(prefix).lower()
    suffix_body = _strip_0x(suffix).lower()
    prefix_len = len(prefix_body)
    suffix_len = len(suffix_body)
    overlap = prefix_len + suffix_len > 0 and prefix.endswith(suffix) and suffix_len > 0
    constrained = prefix_len + suffix_len
    expected = float(HEX_CHARSET_SIZE**constrained) if constrained else 1.0
    return DifficultyEstimate(
        prefix_chars=prefix_len,
        suffix_chars=suffix_len,
        constrained_chars=constrained,
        expected_attempts=expected,
        overlap_warning=overlap and len(prefix) > len(suffix),
        charset_size=HEX_CHARSET_SIZE,
    )


def _pubkey_bytes(priv_bytes: bytes) -> bytes:
    sk = ecdsa.SigningKey.from_string(priv_bytes, curve=ecdsa.SECP256k1)
    return sk.get_verifying_key().to_string()


def _address_hex_lower(priv_bytes: bytes) -> str:
    digest = keccak.new(digest_bits=256, data=_pubkey_bytes(priv_bytes)).digest()
    return digest[-20:].hex()


def to_checksum_address(hex_addr: str) -> str:
    """EIP-55 mixed-case checksum address."""
    body = _strip_0x(hex_addr).lower()
    if len(body) != 40:
        raise ValueError("Address must be 40 hex characters")
    hash_hex = keccak.new(digest_bits=256, data=body.encode("ascii")).hexdigest()
    out = ["0x"]
    for i, ch in enumerate(body):
        if ch in "0123456789":
            out.append(ch)
        elif int(hash_hex[i], 16) >= 8:
            out.append(ch.upper())
        else:
            out.append(ch)
    return "".join(out)


def privkey_to_address(priv_bytes: bytes, *, checksum: bool = True) -> str:
    lower = _address_hex_lower(priv_bytes)
    if checksum:
        return to_checksum_address(lower)
    return "0x" + lower


def normalize_for_match(addr: str) -> str:
    return _strip_0x(addr).lower()


def matches_vanity(addr: str, prefix: str, suffix: str, *, case_sensitive: bool = False) -> bool:
    if case_sensitive:
        body = addr if addr.startswith("0x") else "0x" + addr
        pref = prefix if not prefix or prefix.startswith("0x") else "0x" + prefix
        suff = suffix
        return body.startswith(pref) and body.endswith(suff)
    a = normalize_for_match(addr)
    p = normalize_for_match(prefix)
    s = normalize_for_match(suffix)
    return a.startswith(p) and a.endswith(s)


def try_match_privkey(
    priv_bytes: bytes,
    prefix: str,
    suffix: str,
    *,
    checksum: bool = True,
    case_sensitive: bool = False,
) -> str | None:
    try:
        addr = privkey_to_address(priv_bytes, checksum=checksum)
    except Exception:
        return None
    return addr if matches_vanity(addr, prefix, suffix, case_sensitive=case_sensitive) else None


def random_privkey_from_entropy(strength_bits: int) -> bytes:
    if strength_bits not in ALLOWED_STRENGTHS:
        raise ValueError("Invalid strength_bits")
    nbytes = strength_bits // 8
    while True:
        raw = os.urandom(nbytes)
        if len(raw) != 32:
            raw = hashlib.sha256(raw).digest()
        priv_int = int.from_bytes(raw, "big")
        if 1 <= priv_int < _CURVE_ORDER:
            return raw


def mnemonic_to_privkey(strength_bits: int, derivation_path: str) -> tuple[bytes, str]:
    entropy_bytes = os.urandom(strength_bits // 8)
    words = _MNEMO.to_mnemonic(entropy_bytes)
    seed = _MNEMO.to_seed(words)
    bip32 = BIP32.from_seed(seed)
    path = derivation_path.lstrip("m/").split("/")
    path = [int(p.replace("'", "")) + HARDENED_OFFSET if "'" in p else int(p) for p in path]
    return bip32.get_privkey_from_path(path), words


def generate_keys_batch(
    batch_size: int,
    strength_bits: int,
    *,
    mnemonic: bool = False,
    derivation_path: str = DEFAULT_DERIVATION_PATH,
) -> tuple[list[bytes], list[str] | None]:
    if mnemonic:
        keys: list[bytes] = []
        mnemonics: list[str] = []
        for _ in range(batch_size):
            privkey, words = mnemonic_to_privkey(strength_bits, derivation_path)
            keys.append(privkey)
            mnemonics.append(words)
        return keys, mnemonics
    return [random_privkey_from_entropy(strength_bits) for _ in range(batch_size)], None


def check_key_indexed(
    item: tuple[int, bytes, str, str, bool, bool],
) -> tuple[int, str | None]:
    idx, priv_bytes, prefix, suffix, checksum, case_sensitive = item
    return idx, try_match_privkey(
        priv_bytes,
        prefix,
        suffix,
        checksum=checksum,
        case_sensitive=case_sensitive,
    )
