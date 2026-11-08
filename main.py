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

import secp
from ethereum_address import (
    ALLOWED_STRENGTHS,
    DEFAULT_DERIVATION_PATH,
    VERSION,
    estimate_difficulty,
    make_matcher,
    validate_pattern,
)
from search_engine import Job, SearchEngine, default_workers

OUTPUT_MODE = 0o600


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ethereum vanity generator — same 0x address on all EVM chains.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--prefix", type=str, default="0x", help="Address prefix (hex, 0x optional).")
    parser.add_argument("--suffix", type=str, default="", help="Address suffix (hex).")
    parser.add_argument(
        "--batch",
        type=int,
        default=500,
        help="Keys each worker checks between progress reports and stop checks",
    )
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
    parser.add_argument(
        "--workers",
        "--pool-workers",
        dest="workers",
        type=int,
        default=default_workers(),
        help="Worker processes; each generates and checks keys on its own (default: CPU count)",
    )
    parser.add_argument("--pool", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--mnemonic", action="store_true", help="BIP39 + BIP32 (default m/44'/60'/0'/0/0)")
    parser.add_argument(
        "--index-search",
        action="store_true",
        help="With --mnemonic: one phrase per worker, scan the last path index (fast). "
        "The found path is saved with the result.",
    )
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
    path: str | None = None,
) -> dict:
    rec: dict = {"address": addr}
    if include_secrets:
        rec["private_key"] = "0x" + priv.hex()
        if mnemonic:
            rec["mnemonic"] = mnemonic
    if path:
        rec["path"] = path
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

    if args.workers < 1 or args.batch < 1:
        print("❌ --workers and --batch must be >= 1")
        sys.exit(1)
    if args.index_search and not args.mnemonic:
        print("❌ --index-search needs --mnemonic")
        sys.exit(1)
    mode = ("index" if args.index_search else "mnemonic") if args.mnemonic else "key"

    diff = estimate_difficulty(args.prefix, args.suffix)
    out_root, _ = split_output_name(args.output)
    include_secrets = not args.no_private_key
    checksum = not args.no_checksum

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

    def handle_match(found: dict) -> bool:
        nonlocal found_count, written_in_part
        rec = build_record(
            found["address"], bytes.fromhex(found["private_key"]), found.get("mnemonic"),
            include_secrets=include_secrets, path=found.get("path"),
        )
        out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        found_count += 1
        written_in_part += 1
        rotate_if_needed()
        print(f"\n✅ Found! {found_count}/{args.count}")
        print(f"🔗 {rec['address']}")
        if include_secrets:
            print(f"🔑 {rec['private_key']}")
        if rec.get("path"):
            print(f"📍 Path: {rec['path']}")
        return found_count >= args.count

    engine: SearchEngine | None = None

    def on_interrupt(_sig, _frame) -> None:
        if mp.current_process().name != "MainProcess":
            return
        if engine is not None:
            engine.stop()
        attempts = engine.attempts if engine is not None else 0
        elapsed = time.time() - start
        print(f"\n🛑 Interrupted. Attempts: {attempts:,}, found: {found_count}")
        if elapsed > 0:
            print(f"⚡ {attempts / elapsed:,.0f} keys/sec")
        sys.exit(0)  # the finally block below stops the workers and closes the output

    signal.signal(signal.SIGINT, on_interrupt)

    print("🚀 Ethereum vanity search — EVM address (0x…)")
    print(f"🔹 Prefix  : {args.prefix}")
    print(f"🔹 Suffix  : {args.suffix or '(none)'}")
    print(f"🔹 Target  : {args.count:,} match(es)")
    print(f"🔹 Checksum: {'EIP-55' if checksum else 'lowercase'}")
    if args.mnemonic:
        print(f"🔹 Path    : {args.path}" + (" (last index scanned)" if mode == "index" else ""))
    print(f"🧵 Workers : {args.workers} · mode: {mode} · curve backend: {secp.BACKEND}")
    print(f"💾 Output  : {out_root}*.jsonl (per_file={args.per_file})")
    if diff.constrained_chars == 0:
        print("📊 Difficulty: trivial")
    else:
        print(
            f"📊 Difficulty: ~{diff.expected_attempts:,.0f} attempts "
            f"({diff.constrained_chars} hex char(s), ×{diff.charset_size})"
        )
    print()

    job = Job(
        matcher=make_matcher(args.prefix, args.suffix, checksum=checksum, case_sensitive=args.case_sensitive),
        mode=mode,
        strength=args.strength,
        path=args.path,
        report_every=args.batch,
    )
    try:
        engine = SearchEngine(job, args.workers).start()
        start = time.time()
        while found_count < args.count:
            try:
                found = engine.next_match(timeout=0.5)
            except RuntimeError as e:
                print(f"\n❌ Worker failed: {e}")
                sys.exit(1)
            if found and handle_match(found):
                break
            if not engine.alive():
                print("\n❌ All workers exited unexpectedly")
                sys.exit(1)
            now = time.time()
            if now - last_log >= 1:
                attempts = engine.attempts
                elapsed = now - start
                speed = attempts / elapsed if elapsed > 0 else 0.0
                print(
                    f"\r🔄 {attempts:,} keys | ⚡ {speed:,.0f}/s | found {found_count}/{args.count}",
                    end="",
                    flush=True,
                )
                last_log = now
    finally:
        if engine is not None:
            engine.stop()
        if not out_f.closed:
            out_f.flush()
            out_f.close()

    print(f"\n💾 Done. {found_count} address(es) → {out_root}*.jsonl")


if __name__ == "__main__":
    mp.freeze_support()
    main()
