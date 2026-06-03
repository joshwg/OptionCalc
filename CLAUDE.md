# OptionCalculator

Black-Scholes/Binomial Tree option pricing tool. All pricing logic and market data run directly in the application process via `yahoo_data.py` and `option_pricing.py`.

## Structure

```
OptionCalculator/
├── src/            all Python source code + web UI assets
│   └── tests/      automated test suite (pytest)
├── data/           persistent config (config.json) — gitignored
├── venv/           Python virtual environment
├── pytest.ini      pytest configuration
└── requirements.txt
```

## Architecture

```
src/
  yahoo_data.py             # Yahoo Finance data: prices, option chains, IV, volatility
  option_pricing.py         # Pricing models: Black-Scholes, Binomial Tree, Greeks
  option_service.py         # Shared business logic (pricing, strike selection)
  main.py                   # Desktop app entry point (Tkinter)
  calculator_window.py      # Tkinter UI
  calculator_operations.py  # Business logic for desktop app
  config_manager.py         # config.json loading (reads from data/)
  main_web.py               # Flask web UI entry point
  utils/                    # Font, input validation, threading, autocomplete widgets
  ui_web/
    templates/index.html    # Bootstrap 5 single-page app
    static/app.js           # Frontend JavaScript
    static/style.css        # Custom styles
  tests/
    conftest.py             # pytest fixtures and sys.path setup
    test_option_pricing.py  # BS, binomial, greeks, IV, monotonicity
    test_option_service.py  # service layer: price_option, strike selection
    test_normalization.py   # dividend/IV normalisation + date utilities
    test_config_manager.py  # load/save, geometry parsing, concurrency
    test_input_validator.py # ticker, float, date, required-field validators
    test_web_api.py         # Flask endpoints (mocked dependencies)
    test_web_security.py    # auth, session expiry, input sanitisation, boundaries
```

## Running

```bash
# Desktop app
PYTHONPATH=src venv/bin/python src/main.py

# Web server (http://localhost:5001)
PYTHONPATH=src venv/bin/python src/main_web.py
```

`run.bat` launches the desktop app via WSL.

## Configuration

`.env` file at project root (optional overrides):
```env
DEFAULT_RISK_FREE_RATE=0.05
DEFAULT_VOLATILITY=0.30
```

`data/config.json` stores persistent UI settings (risk-free rate, window geometry).

## Dependencies

- `requirements.txt` (numpy, scipy, yfinance, pandas, requests, pytz, flask)
- Single supported environment: `venv` (Linux/Python 3.12 in WSL2)

## Tests

All tests live in `src/tests/` and run via pytest (configured in `pytest.ini`).

```bash
# Run the full suite (from the project root)
PYTHONPATH=src:/mnt/c/Users/josh/Docs/lab venv/bin/python -m pytest

# Run a specific file
PYTHONPATH=src:/mnt/c/Users/josh/Docs/lab venv/bin/python -m pytest src/tests/test_option_pricing.py

# Skip slow binomial-convergence tests
PYTHONPATH=src:/mnt/c/Users/josh/Docs/lab venv/bin/python -m pytest -m "not slow"

# Skip live-network tests (none by default; add @pytest.mark.network to new ones)
PYTHONPATH=src:/mnt/c/Users/josh/Docs/lab venv/bin/python -m pytest -m "not network"
```

Test files and what they cover:

| File | Coverage |
|---|---|
| `test_option_pricing.py` | Black-Scholes, binomial tree, greeks, IV round-trip, put-call parity, monotonicity |
| `test_option_service.py` | `price_option`, `find_atm_strike_with_iv`, `atm_strikes_window`, post-earnings expiry, `iv_for_strike` |
| `test_normalization.py` | `normalize_dividend_yield`, `normalize_implied_volatility`, date utilities |
| `test_config_manager.py` | load/save round-trip, defaults merge, geometry parsing/validation, concurrent writes |
| `test_input_validator.py` | ticker, float (with bounds), date, required-fields, dividend-yield helpers |
| `test_web_api.py` | All Flask endpoints with mocked external calls; calculate/IV endpoint math |
| `test_web_security.py` | Auth bypass, session expiry, login brute-force, XSS/path-traversal inputs, boundary values, payload hardening |

## Key Notes

- Dividend yield and implied volatility from Yahoo Finance may arrive as percentages (>0.5 or >2) — `normalize_dividend_yield()` and `normalize_implied_volatility()` handle this.
- Black-Scholes is for European options; Binomial Tree (`american_option_binomial`) handles early exercise for American options.
- `Ctrl+1` through `Ctrl+9` opens multiple calculator windows in the desktop app.
- Shell commands run via PowerShell. Use the Read/Write/Edit tools for file operations.
