"""
Shared option business logic for both the desktop app and the web server.

Neither the Tkinter UI nor the Flask routes should contain raw calls to
american_option_binomial / calculate_greeks / implied_volatility — they
call these functions through this module so the behaviour is identical
regardless of which frontend is running.
"""

from __future__ import annotations

from datetime import datetime

from option_lib.data_provider import get_provider
from option_lib.math_util import get_days_to_expiration, get_years_to_expiration
import option_pricing as bs


# ---------------------------------------------------------------------------
# Expiration helpers
# ---------------------------------------------------------------------------

def fetch_expirations(ticker: str, all_dates: bool = False) -> dict:
    """Return the option expiration chain for *ticker*.

    When *all_dates* is ``True``, all available expirations are returned.
    Otherwise the result is limited to the next 6 months.

    Automatically uses Massive.com when MASSIVE_API_KEY is set, otherwise
    falls back to Yahoo Finance.
    """
    provider = get_provider()
    if all_dates:
        return provider.get_option_chain(ticker)
    return provider.get_option_chain_next_months(ticker, months=6)


# ---------------------------------------------------------------------------
# Strike selection
# ---------------------------------------------------------------------------

def find_atm_strike_with_iv(
    chain_data: list[dict],
    current_price: float,
    T: float,
    r: float,
    opt_type: str,
) -> tuple[float | None, float | None, list[float]]:
    """Return *(best_strike, best_iv, all_strikes_sorted)* for an option chain.

    *best_strike* is the nearest strike at-or-above *current_price*; falls
    back to the closest strike when all strikes are below the price.
    *best_iv* is computed from bid/ask mid-price when available, otherwise
    taken from the chain's stored ``implied_volatility`` field.
    """
    if not chain_data:
        return None, None, []

    all_strikes = sorted(opt["strike"] for opt in chain_data)
    by_strike   = {opt["strike"]: opt for opt in chain_data}

    # Prefer the nearest strike at or above ATM
    best_strike = next((s for s in all_strikes if s >= current_price), None)
    if best_strike is None:
        best_strike = min(all_strikes, key=lambda s: abs(s - current_price))

    best_iv = iv_for_strike(
        by_strike.get(best_strike), best_strike, current_price, T, r, opt_type
    )
    return best_strike, best_iv, all_strikes


def atm_strikes_window(
    all_strikes: list[float],
    current_price: float,
    window: int = 10,
) -> tuple[list[float], int]:
    """Return *(selected_strikes, atm_idx)* — a ±*window* slice around ATM.

    *atm_idx* is the index within *all_strikes* that is closest to
    *current_price* (useful for populating a combobox).
    """
    if not all_strikes:
        return [], 0
    atm_idx = min(range(len(all_strikes)),
                  key=lambda i: abs(all_strikes[i] - current_price))
    lo = max(0, atm_idx - window)
    hi = atm_idx + window + 1
    return all_strikes[lo:hi], atm_idx


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------

def price_option(
    S: float,
    K: float,
    expiration: str,
    sigma: float,
    r: float,
    q: float,
    opt_type: str,
    steps: int = 100,
) -> dict:
    """Calculate American option price, time values, and all Greeks.

    Uses the American binomial model for price and delta/gamma/theta/vega
    (finite-difference bumps on the same tree), and the European
    Black-Scholes formula for rho (cheap and nearly identical in practice).

    Returns::

        {
            "price":  float,
            "T":      float,   # years to expiration
            "days":   int,
            "greeks": {"delta", "gamma", "theta", "vega", "rho"},
        }
    """
    T    = get_years_to_expiration(expiration)
    days = get_days_to_expiration(expiration)

    # american_option_greeks returns price + delta/gamma/theta/vega in one pass,
    # but its T=0 early-return omits 'price', so we fall back to american_option_binomial.
    g     = bs.american_option_greeks(S, K, T, r, sigma, q=q, option_type=opt_type, steps=steps)
    price = g.get("price") if g.get("price") is not None else bs.american_option_binomial(S, K, T, r, sigma, q=q, option_type=opt_type, steps=steps)

    # Rho from the European formula — cheap, and the difference vs American is negligible
    rho = bs.calculate_greeks(S, K, T, r, sigma, opt_type)["rho"]

    greeks = {
        "delta": g["delta"],
        "gamma": g["gamma"],
        "theta": g["theta"],
        "vega":  g["vega"],
        "rho":   rho,
    }
    return {"price": price, "T": T, "days": days, "greeks": greeks}


# ---------------------------------------------------------------------------
# Earnings / expiration helpers
# ---------------------------------------------------------------------------

def find_post_earnings_expiration(
    dates: list[str],
    earnings_date: datetime | None,
) -> int | None:
    """Return the index (within the first 3 dates) of the first expiration that
    falls after *earnings_date* and within the cadence-appropriate threshold.

    The threshold is 7 days for stocks with weekly options (two expirations in
    the same calendar month) and 30 days for monthly-only chains.  Returns
    ``None`` when *earnings_date* is ``None`` or no matching expiration exists.
    """
    if not earnings_date or not dates:
        return None

    has_weekly = False
    if len(dates) >= 2:
        try:
            d1 = datetime.strptime(dates[0], '%Y-%m-%d')
            d2 = datetime.strptime(dates[1], '%Y-%m-%d')
            has_weekly = (d1.month == d2.month and d1.year == d2.year)
        except ValueError:
            pass
    threshold = 7 if has_weekly else 30

    for i, exp in enumerate(dates[:3]):
        try:
            exp_dt = datetime.strptime(exp, '%Y-%m-%d')
            if exp_dt > earnings_date and (exp_dt - earnings_date).days <= threshold:
                return i
        except ValueError:
            pass
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def iv_for_strike(
    opt: dict | None,
    K: float,
    S: float,
    T: float,
    r: float,
    opt_type: str,
) -> float | None:
    """Compute IV from a single option row.

    Tries bid/ask mid first; falls back to the row's stored
    ``implied_volatility`` value.
    """
    if opt is None:
        return None
    if opt.get("bid", 0) > 0 and opt.get("ask", 0) > 0 and T > 0:
        mid = (opt["bid"] + opt["ask"]) / 2
        iv  = bs.implied_volatility(mid, S, K, T, r, option_type=opt_type)
        if iv and iv > 0:
            return iv
    return opt.get("implied_volatility")
