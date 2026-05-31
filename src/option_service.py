"""
Shared option business logic for both the desktop app and the web server.

Neither the Tkinter UI nor the Flask routes should contain raw calls to
american_option_binomial / calculate_greeks / implied_volatility — they
call these functions through this module so the behaviour is identical
regardless of which frontend is running.
"""

from __future__ import annotations

import yahoo_data as yd
import option_pricing as bs


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

    best_iv = _iv_for_strike(
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

    Returns::

        {
            "price":  float,
            "T":      float,   # years to expiration
            "days":   int,
            "greeks": {"delta", "gamma", "theta", "vega", "rho"},
        }
    """
    T    = yd.get_years_to_expiration(expiration)
    days = yd.get_days_to_expiration(expiration)
    price  = bs.american_option_binomial(
        S, K, T, r, sigma, q=q, option_type=opt_type, steps=steps
    )
    greeks = bs.calculate_greeks(S, K, T, r, sigma, opt_type)
    return {"price": price, "T": T, "days": days, "greeks": greeks}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _iv_for_strike(
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
    return opt.get("implied_volatility") or None
