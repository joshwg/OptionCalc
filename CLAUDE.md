# OptionCalculator

Black-Scholes/Binomial Tree option pricing tool. All pricing logic and market data run directly in the application process via `yahoo_data.py` and `option_pricing.py`.

## Structure

```
OptionCalculator/
├── src/            all Python source code + web UI assets
├── data/           persistent config (config.json) — gitignored
├── venv/           Python virtual environment
└── requirements.txt
```

## Architecture

```
src/
  yahoo_data.py             # Yahoo Finance data: prices, option chains, IV, volatility
  option_pricing.py         # Pricing models: Black-Scholes, Binomial Tree, Greeks
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

```bash
PYTHONPATH=src venv/bin/python src/test_option_pricing.py
PYTHONPATH=src venv/bin/python src/test_yahoo_data.py
PYTHONPATH=src venv/bin/python src/test_dividend_normalization.py
PYTHONPATH=src venv/bin/python src/test_ticker_search.py
```

## Key Notes

- Dividend yield and implied volatility from Yahoo Finance may arrive as percentages (>0.5 or >2) — `normalize_dividend_yield()` and `normalize_implied_volatility()` handle this.
- Black-Scholes is for European options; Binomial Tree (`american_option_binomial`) handles early exercise for American options.
- `Ctrl+1` through `Ctrl+9` opens multiple calculator windows in the desktop app.
- Shell commands run via PowerShell. Use the Read/Write/Edit tools for file operations.
