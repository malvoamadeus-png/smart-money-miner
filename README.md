# Smart Money Miner Skill

A Claude Code skill for discovering and filtering high-performing wallet addresses from PumpFun graduated tokens or user-provided token addresses.

## Installation

This skill is located in the `skills/smart-money-miner/` directory.

To use it in Claude Code, you can either:
1. Copy the entire `skills/` directory to your Claude plugins directory
2. Or simply ask Claude to "mine smart money addresses" and it will use this skill

## Structure

```
skills/smart-money-miner/
├── SKILL.md                      # Main skill definition
├── README.md                     # This file
├── scripts/
│   └── miner.py                  # Main analysis script
└── skip_addresses.json.example   # Example skip list configuration
```

## Quick Start

### Using the Skill in Claude Code

Simply ask Claude:
- "Mine smart money addresses from 20 PumpFun tokens"
- "Find profitable traders from these tokens: token1, token2"
- "Analyze PumpFun graduated tokens and find good addresses"

Claude will automatically invoke this skill and run the analysis.

### Direct Script Usage

```bash
# Navigate to the skill directory
cd skills/smart-money-miner

# Test PumpFun API
python scripts/miner.py --test-pumpfun

# Analyze 20 tokens
python scripts/miner.py --pumpfun --limit 20

# Analyze specific tokens
python scripts/miner.py --tokens token1,token2,token3
```

## Features

- ✅ Automatic PumpFun API integration
- ✅ Multi-metric address analysis
- ✅ Smart filtering based on 5 criteria
- ✅ JSON output for easy integration
- ✅ Skip list support
- ✅ Command-line interface

## Filtering Criteria

Addresses must meet ALL criteria:
1. TOP 5 avg profit rate > 0%
2. TOP 10 avg profit rate > 0%
3. Overall win rate >= 10%
4. Average profit >= 500 USDT
5. Average profit rate >= 0%

## Output

Results are saved to `smart_money_results.json` in the current directory:

```json
{
  "timestamp": "2026-02-28T10:30:00",
  "source": "pumpfun",
  "tokens_analyzed": 20,
  "filtered_addresses_count": 45,
  "filtered_addresses": [...]
}
```

## Configuration

### Skip Addresses

Create `skip_addresses.json` to exclude specific addresses:

```json
{
  "skip_addresses": [
    "address1",
    "address2"
  ]
}
```

### Adjust Filtering Thresholds

Edit `scripts/miner.py` to customize:

```python
MIN_WIN_RATE = 10.0
MIN_AVG_PROFIT_USDT = 500
MIN_AVG_PROFIT_RATE = 0.0
```

## Performance

| Tokens | Time | Addresses Found |
|--------|------|-----------------|
| 5      | 10-15 min | ~500 |
| 20     | 40-60 min | ~2000 |
| 50     | 2-3 hours | ~5000 |

## Dependencies

```bash
pip install requests
```

## Documentation

- See `SKILL.md` for complete skill documentation
- See `../QUICK_START.md` for detailed usage guide
- See `../JSON_FORMAT_REFERENCE.md` for output format details

## License

MIT
