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

# Multiprocessing + split 500k addresses per file
eth-vanity --prefix 0x --suffix ff --count 1000000 --per-file 500000 --pool --pool-workers 4

# Scan balances on Ethereum mainnet
eth-scan

# Scan on Sepolia or custom RPC
ETH_CHAIN=sepolia eth-scan
ETH_RPC_URL=https://my-rpc.example eth-scan
```

## Output

JSONL records (one object per line):

```json
{"address": "0xf39F…", "private_key": "0xac09…", "mnemonic": "…"}
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
