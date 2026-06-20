#!/usr/bin/env python3
"""
Scan generated wallet files for on-chain EVM balances via JSON-RPC eth_getBalance.

Intended for checking addresses you generated locally (see main.py).
Do not use this tool to probe third-party or unknown wallets.
"""

from __future__ import annotations

import os
import signal
import sys
import threading

from tqdm import tqdm

from chains import DEFAULT_CHAIN, EVM_CHAINS
from scanner import ScanConfig, load_cache, process_file, resolve_input_files, save_cache_atomic

NUM_WORKERS = int(os.getenv("NUM_WORKERS", "10"))
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "10"))
HTTP_RETRIES = int(os.getenv("HTTP_RETRIES", "2"))
RESULT_DIR = os.getenv("RESULT_DIR", "found_wallets")
CACHE_FILE = os.getenv("CACHE_FILE", "checked_cache.json")
CACHE_FLUSH_EVERY_OK = int(os.getenv("CACHE_FLUSH_EVERY_OK", "10000"))
FOUND_FLUSH_EVERY = int(os.getenv("FOUND_FLUSH_EVERY", "1"))
CREATE_EMPTY_CACHE_ON_START = os.getenv("CREATE_EMPTY_CACHE_ON_START", "false").lower() in ("1", "true", "yes")
IN_FLIGHT_MULTIPLIER = int(os.getenv("IN_FLIGHT_MULTIPLIER", "20"))
INPUT_GLOB = os.getenv("INPUT_GLOB", "*.jsonl")
CHAIN = os.getenv("ETH_CHAIN", DEFAULT_CHAIN)
RPC_URL = os.getenv("ETH_RPC_URL", EVM_CHAINS.get(CHAIN, EVM_CHAINS[DEFAULT_CHAIN])["rpc"]).rstrip("/")

os.makedirs(RESULT_DIR, exist_ok=True)


def _default_config() -> ScanConfig:
    chain_info = EVM_CHAINS.get(CHAIN, EVM_CHAINS[DEFAULT_CHAIN])
    return ScanConfig(
        input_glob=INPUT_GLOB,
        rpc_url=RPC_URL,
        chain=CHAIN,
        chain_symbol=chain_info["symbol"],
        num_workers=NUM_WORKERS,
        http_timeout=HTTP_TIMEOUT,
        http_retries=HTTP_RETRIES,
        result_dir=RESULT_DIR,
        cache_file=CACHE_FILE,
        cache_flush_every_ok=CACHE_FLUSH_EVERY_OK,
        found_flush_every=FOUND_FLUSH_EVERY,
        in_flight_multiplier=IN_FLIGHT_MULTIPLIER,
        create_empty_cache_on_start=CREATE_EMPTY_CACHE_ON_START,
    )


def main() -> None:
    config = _default_config()
    cache_lock = threading.Lock()
    cache = load_cache(config.cache_file)

    if config.create_empty_cache_on_start and not os.path.exists(config.cache_file):
        save_cache_atomic(config.cache_file, cache)

    ok_since_flush_ref = [0]
    stop_event = threading.Event()

    def flush_all_and_exit(exit_code: int = 130) -> None:
        try:
            with cache_lock:
                if ok_since_flush_ref[0] > 0:
                    save_cache_atomic(config.cache_file, cache)
                    ok_since_flush_ref[0] = 0
                    print(f"\n💾 Cache flushed (SIGINT tail). cache_size={len(cache):,}")
        except Exception:
            pass
        print("\n🛑 Interrupted.")
        raise SystemExit(exit_code)

    signal.signal(signal.SIGINT, lambda s, f: flush_all_and_exit(130))

    wallet_files = resolve_input_files(config)
    if not wallet_files:
        print(f"❌ No wallet files found for '{config.input_glob}'.")
        sys.exit(1)

    chain_name = EVM_CHAINS.get(config.chain, {}).get("name", config.chain)
    print(f"🔍 EVM balance scan — {chain_name}")
    print(f"🔗 RPC: {config.rpc_url}")
    print(f"📁 {len(wallet_files)} file(s) | cache: {len(cache):,} addresses")
    for f in wallet_files:
        print(f"  • {f}")

    total_found = 0
    with tqdm(desc="Scanning", unit=" addr") as bar:
        for file_path in wallet_files:
            if stop_event.is_set():
                break
            skipped, checked, errors, found, _, out_jsonl, _ = process_file(
                file_path,
                config,
                cache,
                cache_lock,
                ok_since_flush_ref,
                stop_event=stop_event,
            )
            total_found += found
            bar.update(checked)
            print(
                f"\n✓ {file_path}: found {found}, checked {checked:,}, "
                f"skipped {skipped:,}, errors {errors}"
            )
            if out_jsonl and found:
                print(f"  → {out_jsonl}")

    print(f"\n💾 Done. {total_found} wallet(s) with balance. Results: {config.result_dir}")


if __name__ == "__main__":
    main()
