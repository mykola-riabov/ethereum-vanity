# ethereum-vanity

CPU vanity address generator for **Ethereum / EVM** networks with desktop GUI and balance scanner.

One private key produces the **same `0x…` address** on Ethereum mainnet, Polygon, BSC, Arbitrum, and other EVM chains.

## Install

```bash
cd ethereum-vanity
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Debian package

```bash
./scripts/build-deb.sh
sudo apt install ./dist/ethereum-vanity_*.deb
```

Installed commands: `eth-vanity-gui`, `eth-vanity`, `eth-scan`

## GUI

```bash
eth-vanity-gui
```

Two pages:

- **Generator** — vanity search with EIP-55 checksum, themes, bulk mode, per-file rotation
- **Balance Scanner** — checks generated wallets via JSON-RPC `eth_getBalance`

### Workspace folder

Choose one **workspace** in the sidebar (saved between sessions). Everything lives under it:

```
~/ethereum-vanity/          ← default workspace (change via Choose…)
├── generated/              ← generator output (*.jsonl)
│   └── eth_addrs.jsonl
├── found_wallets/          ← scanner: addresses with balance
└── checked_cache.json      ← scanner resume cache
```

Generator and scanner paths stay in sync — no separate file pickers.

## CLI

```bash
# Address starting with 0xdead…
eth-vanity --prefix 0xdead --count 1

# Lowercase without EIP-55 checksum
eth-vanity --prefix dead --no-checksum --count 1

# Recoverable from a phrase and fast: one phrase per worker, address index searched
eth-vanity --prefix 0xbeef --mnemonic --index-search --count 1

# 8 workers + split 500k addresses per file
eth-vanity --prefix 0x --suffix ff --count 1000000 --per-file 500000 --workers 8

# Scan balances on Ethereum mainnet
eth-scan

# Scan on Sepolia or custom RPC
ETH_CHAIN=sepolia eth-scan
ETH_RPC_URL=https://my-rpc.example eth-scan
```

### Speed and modes

Every worker process generates, derives and checks keys on its own; only matches cross processes,
so speed grows with `--workers` (default: CPU count). Curve math goes through the system
**libsecp256k1** (the library Bitcoin Core uses) when installed —
`sudo apt install libsecp256k1-6` — and pure-Python `ecdsa` otherwise.
`SECP256K1_LIBRARY=/path/libsecp256k1.so` picks a library, `SECP256K1_DISABLE=1` forces the fallback.

- random key (default) — fastest, no recovery phrase;
- `--mnemonic` — a new BIP39 phrase per attempt (slow: PBKDF2 with 2048 rounds per phrase);
- `--mnemonic --index-search` — one phrase per worker, then the last path index 0, 1, 2…;
  as fast as random keys and recoverable. The found `path` is saved with the result: write down
  the phrase **and** the path, and open that address index in the wallet.

Measured on a 16-thread desktop CPU (2026-11-08), keys per second:

| Mode | before (1 process / `--pool-workers 16`) | now, 16 workers |
|------|-----------------------------------------:|----------------:|
| Random key | 2,500 / 18,400 | 322,000 |
| `--mnemonic --index-search` | — | 278,000 |
| `--mnemonic` | the pool waited for one generator | 8,200 |

`--batch` is how many keys each worker checks between progress reports and Stop checks (default 500).
`--pool` is ignored and `--pool-workers` is an alias of `--workers`.

## Output

JSONL records (one object per line):

```json
{"address": "0xf39F…", "private_key": "0xac09…", "mnemonic": "…", "path": "m/44'/60'/0'/0/1749"}
```

## Scanner

The scanner queries `eth_getBalance` over JSON-RPC. Preset chains in the GUI:

| Chain | Symbol |
|-------|--------|
| Ethereum Mainnet | ETH |
| Sepolia | ETH |
| Polygon | MATIC |
| BNB Smart Chain | BNB |
| Arbitrum One | ETH |

Balances are stored in **wei** in cache and found-wallet files.

## Security

Generated keys are written with mode `0600`. Only scan wallets you created locally.

## License

MIT
