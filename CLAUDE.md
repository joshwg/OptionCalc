# OptionCalculator

Black-Scholes/Binomial Tree option pricing tool. All pricing logic and market data run directly in the application process via `yahoo_data.py` and `option_pricing.py`.

## Architecture

```
yahoo_data.py             # Yahoo Finance data: prices, option chains, IV, volatility
option_pricing.py         # Pricing models: Black-Scholes, Binomial Tree, Greeks
server_client.py          # Thin shim re-exporting yahoo_data + option_pricing
main.py                   # Desktop app entry point (Tkinter)
calculator_window.py      # Tkinter UI
calculator_operations.py  # Business logic for desktop app
config_manager.py         # .env / config.json loading
utils/                    # Font, input validation, threading, autocomplete widgets
kivy_app/                 # Android/mobile app (Kivy + KivyMD)
  screens/calculator_screen.py  # Main mobile screen
```

## Running

```bash
python main.py
```

## Configuration

`.env` file at project root:
```env
DEFAULT_RISK_FREE_RATE=0.05
DEFAULT_VOLATILITY=0.30
```

`config.json` stores persistent UI settings (theme, defaults).

## Dependencies

- `requirements.txt` (numpy, scipy, yfinance, pandas, requests, pytz)
- Mobile: `kivy_app/requirements-kivy.txt`
- Single supported environment: `venv` (Linux/Python 3.12 in WSL2)

## Tests

```bash
python test_option_pricing.py
python test_yahoo_data.py
python test_dividend_normalization.py
python test_ticker_search.py
```

## Key Notes

- Dividend yield and implied volatility from Yahoo Finance may arrive as percentages (>0.5 or >2) — `normalize_dividend_yield()` and `normalize_implied_volatility()` handle this.
- Black-Scholes is for European options; Binomial Tree (`american_option_binomial`) handles early exercise for American options.
- `Ctrl+1` through `Ctrl+9` opens multiple calculator windows in the desktop app.
- Shell commands run via PowerShell. Use the Read/Write/Edit tools for file operations.
