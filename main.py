#!/usr/bin/env python3
"""CLI for Ethereum / EVM vanity address generation."""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import signal
import sys
import time

from ethereum_address import (
    ALLOWED_STRENGTHS,
    DEFAULT_DERIVATION_PATH,
    VERSION,
    check_key_indexed,
    estimate_difficulty,
    generate_keys_batch,
    try_match_privkey,
    validate_pattern,
)

OUTPUT_MODE = 0o600


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ethereum vanity generator — same 0x address on all EVM chains.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--prefix", type=str, default="0x", help="Address prefix (hex, 0x optional).")
    parser.add_argument("--suffix", type=str, default="", help="Address suffix (hex).")
    parser.add_argument("--batch", type=int, default=10_000, help="Keys per CPU batch")
    parser.add_argument("--output", type=str, default="eth_addrs.jsonl", help="Output base filename (.jsonl)")
    parser.add_argument("--per-file", type=int, default=0, help="Rotate output after N matches. 0 = single file.")
    parser.add_argument("--count", type=int, default=1, help="Matches required before stopping")
    parser.add_argument(
        "--strength",
        type=int,
        default=256,
        choices=ALLOWED_STRENGTHS,
        help="Entropy bits for random key generation",
    )
    parser.add_argument("--pool", action="store_true", help="Enable multiprocessing for filtering")
    parser.add_argument("--pool-workers", type=int, default=2, help="Worker process count")
    parser.add_argument("--mnemonic", action="store_true", help="BIP39 + BIP32 (default m/44'/60'/0'/0/0)")
    parser.add_argument("--path", type=str, default=DEFAULT_DERIVATION_PATH, help="BIP32 path with --mnemonic")
    parser.add_argument("--no-checksum", action="store_true", help="Lowercase 0x… without EIP-55 checksum")
    parser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Match prefix/suffix with exact letter case (harder vanity)",
    )
    parser.add_argument("--no-private-key", action="store_true", help="Do not write private_key/mnemonic")
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    return parser.parse_args()


def split_output_name(path: str) -> tuple[str, str]:
    root, ext = os.path.splitext(path)
    return root, ext or ".jsonl"


def secure_chmod(path: str) -> None:
    try:
        os.chmod(path, OUTPUT_MODE)
    except OSError:
        pass


def build_record(
    addr: str,
    priv: bytes,
    mnemonic: str | None,
    *,
    include_secrets: bool,
) -> dict:
    rec: dict = {"address": addr}
    if include_secrets:
        rec["private_key"] = "0x" + priv.hex()
        if mnemonic:
            rec["mnemonic"] = mnemonic
    return rec


def main() -> None:
    args = parse_args()
    if args.version:
        print(f"eth-vanity {VERSION}")
        return

    try:
        validate_pattern(args.prefix, args.suffix)
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

    diff = estimate_difficulty(args.prefix, args.suffix)
    out_root, _ = split_output_name(args.output)
    include_secrets = not args.no_private_key
    checksum = not args.no_checksum

    attempts = 0
    start = time.time()
    last_log = start
    found_count = 0
    current_part = 1
    written_in_part = 0

    def make_part_path(part_idx: int) -> str:
        if args.per_file > 0:
            return f"{out_root}_{part_idx:03d}.jsonl"
        return f"{out_root}.jsonl"

    current_path = make_part_path(current_part)
    os.makedirs(os.path.dirname(current_path) or ".", exist_ok=True)
    out_f = open(current_path, "a", encoding="utf-8")
    secure_chmod(current_path)

    def rotate_if_needed() -> None:
        nonlocal current_part, current_path, out_f, written_in_part
        if args.per_file <= 0 or written_in_part < args.per_file:
            return
        out_f.flush()
        out_f.close()
        current_part += 1
        current_path = make_part_path(current_part)
        out_f = open(current_path, "a", encoding="utf-8")
        secure_chmod(current_path)
        written_in_part = 0
        print(f"\n📁 Rotated output → {current_path}")

    pool_args = (args.prefix, args.suffix, checksum, args.case_sensitive)

    def handle_match(idx: int, priv: bytes, mnemonics: list[str] | None, addr: str) -> bool:
        nonlocal found_count, written_in_part
        rec = build_record(
            addr, priv, mnemonics[idx] if mnemonics else None, include_secrets=include_secrets
        )
        out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        found_count += 1
        written_in_part += 1
        rotate_if_needed()
        print(f"\n✅ Found! {found_count}/{args.count}")
        print(f"🔗 {rec['address']}")
        if include_secrets:
            print(f"🔑 {rec['private_key']}")
        return found_count >= args.count

    def on_interrupt(_sig, _frame) -> None:
        elapsed = time.time() - start
        print(f"\n🛑 Interrupted. Attempts: {attempts:,}, found: {found_count}")
        if elapsed > 0:
            print(f"⚡ {attempts / elapsed:,.0f} keys/sec")
        out_f.flush()
        out_f.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, on_interrupt)

    print("🚀 Ethereum vanity search — EVM address (0x…)")
    print(f"🔹 Prefix  : {args.prefix}")
    print(f"🔹 Suffix  : {args.suffix or '(none)'}")
    print(f"🔹 Target  : {args.count:,} match(es)")
    print(f"🔹 Checksum: {'EIP-55' if checksum else 'lowercase'}")
    if args.mnemonic:
        print(f"🔹 Path    : {args.path}")
    print(f"💾 Output  : {out_root}*.jsonl (per_file={args.per_file})")
    if diff.constrained_chars == 0:
        print("📊 Difficulty: trivial")
    else:
        print(
            f"📊 Difficulty: ~{diff.expected_attempts:,.0f} attempts "
            f"({diff.constrained_chars} hex char(s), ×{diff.charset_size})"
        )
    print()

    try:
        while found_count < args.count:
            keys, mnemonics = generate_keys_batch(
                args.batch,
                args.strength,
                mnemonic=args.mnemonic,
                derivation_path=args.path,
            )
            attempts += len(keys)

            if args.pool:
                work = [(i, k, *pool_args) for i, k in enumerate(keys)]
                with mp.Pool(processes=args.pool_workers) as pool:
                    for idx, addr in pool.imap_unordered(check_key_indexed, work, chunksize=256):
                        if addr and handle_match(idx, keys[idx], mnemonics, addr):
                            break
            else:
                for idx, priv in enumerate(keys):
                    addr = try_match_privkey(
                        priv,
                        args.prefix,
                        args.suffix,
                        checksum=checksum,
                        case_sensitive=args.case_sensitive,
                    )
                    if addr and handle_match(idx, priv, mnemonics, addr):
                        break

            now = time.time()
            if now - last_log >= 1:
                elapsed = now - start
                speed = attempts / elapsed if elapsed > 0 else 0.0
                print(
                    f"\r🔄 {attempts:,} keys | ⚡ {speed:,.0f}/s | found {found_count}/{args.count}",
                    end="",
                    flush=True,
                )
                last_log = now
    finally:
        out_f.flush()
        out_f.close()

    print(f"\n💾 Done. {found_count} address(es) → {out_root}*.jsonl")


if __name__ == "__main__":
    mp.freeze_support()
    main()
