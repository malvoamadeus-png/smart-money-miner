# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Smart Money Miner — a Python tool that discovers high-performing Solana and BNB Chain (BSC) wallet addresses ("smart money") by analyzing token trading data. It fetches top profitable traders from tokens (via OKX APIs), evaluates their trading history, and filters by performance metrics.

Three input modes:
1. Auto-fetch graduated tokens from PumpFun API (Solana)
2. Auto-fetch graduated tokens from Four Meme API (BSC)
3. User-provided token contract addresses (auto-detects chain by address format)

## Commands

```bash
# Run analysis from PumpFun tokens (Solana)
python scripts/miner.py --pumpfun --limit 20

# Run analysis from Four Meme tokens (BSC)
python scripts/miner.py --fourmeme --fourmeme-limit 10

# Run analysis from specific token addresses (auto-detects chain)
python scripts/miner.py --tokens <addr1>,<addr2>,0x<bsc_addr>

# Mixed mode
python scripts/miner.py --tokens <addr1> --pumpfun --limit 10 --fourmeme

# Test API connectivity
python scripts/miner.py --test-pumpfun
python scripts/miner.py --test-fourmeme

# Custom skip file
python scripts/miner.py --pumpfun --skip-file my_skip_list.json
```

Only dependency: `pip install requests`

## Architecture

Single-script tool: `scripts/miner.py` (~800 lines). No package structure or test suite.

### Data Flow

1. **Token collection** — `fetch_pumpfun_tokens()` (Solana), `fetch_four_meme_tokens()` (BSC), or user-provided addresses
2. **Chain detection** — `detect_chain_id()` auto-detects chain by address format (`0x` prefix = BSC, otherwise = Solana)
3. **Top trader discovery** — `fetch_top_traders()` gets TOP 100 profitable addresses per token via OKX API 1
4. **Deduplication & skip filtering** — merges addresses across tokens, removes addresses from `skip_addresses.json`
5. **Per-wallet analysis** — `analyze_wallet_address()` for each unique address:
   - `fetch_token_pnl_summary()` (OKX API 4) → TOP 5/10 avg profit rates
   - `fetch_token_list_paged()` (OKX API 2) → full token trading history, paginated
   - Calculates win rate, avg profit (USDT), avg profit rate
   - BSC only: `is_binance_token()` check and `fetch_binance_ai_narrative()`
6. **Filtering** — 5 criteria must all pass (see constants at top of file)
7. **Output** — JSON saved to `smart_money_results.json`

### Key APIs

| Function | OKX Endpoint | Purpose |
|---|---|---|
| `fetch_top_traders` | API_BASE_URL_1 | TOP 100 traders per token |
| `fetch_token_list_paged` | API_BASE_URL_2 | Wallet's token PnL details (paginated) |
| `fetch_token_pnl_summary` | API_BASE_URL_4 | Wallet's TOP 5/10 avg profit rates |

All OKX APIs support both Solana (chain ID 501) and BSC (chain ID 56), include retry logic (3 attempts, 5s delay), and append a `t` timestamp param. Chain is auto-detected from address format.

### Filtering Thresholds (configurable constants in miner.py)

- `TOP5_MIN_PROFIT_RATE` / `TOP10_MIN_PROFIT_RATE` — TOP 5/10 avg profit rate > 0%
- `MIN_WIN_RATE` — overall win rate >= 10%
- `MIN_AVG_PROFIT_USDT` — avg profit >= 500 USDT
- `MIN_AVG_PROFIT_RATE` — avg profit rate >= 0%

## Key Files

- `scripts/miner.py` — entire tool implementation
- `skip_addresses.json` — optional address exclusion list (see `.example`)
- `smart_money_results.json` — output (generated at runtime)
- `SKILL.md` — Claude Code skill definition for natural language invocation
- `参考getMC.py` — reference/legacy script (not part of main tool)

## Conventions

- Code comments and print output are in Chinese (中文)
- The project is a Claude Code skill — `SKILL.md` defines when/how it activates
- Output JSON includes both `filtered_addresses` (passed all criteria) and `full_data` (all analyzed)
- Long-running: analyzing 20 tokens takes 40-60 minutes due to API rate limiting
