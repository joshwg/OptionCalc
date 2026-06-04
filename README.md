# Option Calculator

A comprehensive Black-Scholes option calculator. The business logic runs directly in the application process via `yahoo_data.py` and `option_pricing.py`.

## 🎯 Features

### Core Functionality
- **Multiple Pricing Models**
  - Black-Scholes for European options
  - Binomial Tree for American options
  
- **Complete Greeks Calculation**
  - Delta, Gamma, Theta, Vega, Rho
  
- **Real-time Market Data**
  - Yahoo Finance integration
  - Live stock prices and option chains
  - Historical volatility calculation
  
- **Advanced Features**
  - Ticker search with autocomplete
  - Multiple calculator windows
  - Dividend yield adjustments
  - Earnings date tracking

## 🏗️ Architecture

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
```

## 🚀 Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure**
   Create a `.env` file:
   ```env
   DEFAULT_RISK_FREE_RATE=0.05
   DEFAULT_VOLATILITY=0.30
   ```

3. **Run Calculator**
   ```bash
   python main.py
   ```

## 📁 Project Structure

```
OptionCalculator/
├── main.py                 # Desktop app entry point
├── calculator_window.py    # Main calculator UI
├── calculator_operations.py # Calculator logic
├── yahoo_data.py           # Market data
├── option_pricing.py       # Pricing models and Greeks
├── config_manager.py       # Configuration management
│
├── utils/                  # Utility modules
│   ├── font_manager.py
│   ├── input_validator.py
│   ├── suggestion_widget.py
│   └── threading_helper.py
│
└── kivy_app/              # Mobile application
    ├── main.py
    ├── optioncalculator.kv
    └── screens/
```

## 🛠️ Development

### Requirements
- Python 3.8+
- pip
- Virtual environment (recommended)

### Installation
```bash
# Clone repository
git clone <your-repo-url>
cd OptionCalculator

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Running
```bash
python main.py
```

### Testing

Tests live in `src/tests/` and run via pytest:

```bash
# Run the full suite
PYTHONPATH=src venv/bin/python -m pytest

# Run a specific file
PYTHONPATH=src venv/bin/python -m pytest src/tests/test_option_pricing.py

# Skip slow binomial-convergence tests
PYTHONPATH=src venv/bin/python -m pytest -m "not slow"
```

| Test file | Coverage |
|---|---|
| `test_option_pricing.py` | Black-Scholes, binomial tree, Greeks, IV round-trip, put-call parity |
| `test_option_service.py` | `price_option`, strike selection, IV lookup |
| `test_normalization.py` | Dividend/IV normalisation, date utilities |
| `test_config_manager.py` | Load/save, defaults, geometry parsing, concurrent writes |
| `test_input_validator.py` | Ticker, float, date, required-field validators |
| `test_web_api.py` | Flask endpoints with mocked dependencies |
| `test_web_security.py` | Auth, session expiry, XSS/path-traversal, boundary values |

## 🎮 Usage

### Basic Workflow
1. **Load Stock Data**
   - Enter ticker symbol (e.g., AAPL, MSFT)
   - Click "Load Stock Data"
   - Current price and dividend yield auto-populate

2. **Calculate Option Price**
   - Enter strike price
   - Select expiration date
   - Adjust volatility if needed
   - Choose pricing model
   - Click "Calculate Price"

3. **View Results**
   - Call and Put prices
   - All Greeks (Delta, Gamma, Theta, Vega, Rho)
   - Intrinsic and time value

### Advanced Features

**Multiple Windows**: Press `Ctrl+1` through `Ctrl+9` to open additional calculator windows for different stocks.

**Historical Volatility**: Click "Get Historical Volatility" to calculate from past prices.

**Option Chain**: View real market option prices and implied volatilities.

**Ticker Search**: Start typing a company name for autocomplete suggestions.

## 🔧 Configuration

### Environment Variables
Create a `.env` file:

```env
DEFAULT_RISK_FREE_RATE=0.05
DEFAULT_VOLATILITY=0.30
```

### Config File
Edit `config.json` for persistent settings:

```json
{
  "theme": "light",
  "default_risk_free_rate": 0.05,
  "default_volatility": 0.30
}
```

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

MIT License - See LICENSE file for details

## 🐛 Known Issues

- Yahoo Finance API rate limiting may occur with frequent requests
- Some tickers may have limited option chain data
- Historical volatility requires sufficient price history

## 💡 Tips

- Use historical volatility as starting point for implied volatility
- Compare Black-Scholes vs Binomial for American options
- Check dividend yield impact on option prices
- Monitor Greeks for risk management
- Save multiple windows for portfolio analysis

## 🔗 Links

- [Yahoo Finance](https://finance.yahoo.com)
- [Black-Scholes Model](https://en.wikipedia.org/wiki/Black%E2%80%93Scholes_model)

## ⚠️ Disclaimer

This tool is for educational and informational purposes only. Not financial advice. Use at your own risk.

---

**Built with**: Python, NumPy, SciPy, Tkinter, yfinance
