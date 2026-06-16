"""
Integration test: end-to-end fair value computation for multiple tickers.

Strike and expiry are resolved from live market data at run-time:
  - strike : nearest listed strike to S * (1 + strike_pct / 100)
  - expiry  : first available expiration that is at least `months_ahead` calendar
              months in the future

── Adding regression cases ──────────────────────────────────────────────────
Append a tuple to CASES below.  Format:
  (ticker, strike_pct, months_ahead, option_type)

  ticker       : str   — e.g. "AAPL"
  strike_pct   : float — percentage offset from current price
                         positive → above spot  (e.g. +20 = 20% OTM call)
                         negative → below spot  (e.g. -20 = 20% OTM put)
  months_ahead : int   — minimum calendar months to expiry; the nearest
                         listed expiration on or after that date is used
  option_type  : str   — "call" or "put"

Run with:
    PYTHONPATH=src:/mnt/c/Users/josh/Docs/lab venv/bin/python \\
        -m pytest src/tests/test_fair_value_load.py -v
─────────────────────────────────────────────────────────────────────────────

Marked @pytest.mark.network — requires live Yahoo Finance access.
"""

import json
import math
import pytest
from datetime import datetime, date


# ── Regression cases ─────────────────────────────────────────────────────────
# (ticker, strike_pct, months_ahead, option_type)
CASES = [
    ("RBRK", +20, 2, "call"),
    ("LEN",  +20, 2, "call"),
    ("SRPT", -20, 2, "put"),
    ("CASY",  +10, 3, "call"),
]

_IDS = [
    f"{t}-{'+' if p >= 0 else ''}{p}pct-{m}mo-{ot}"
    for t, p, m, ot in CASES
]


# ── Per-case resolution cache ─────────────────────────────────────────────────
# Populated on first access; shared across all test steps within a session.
# Value: {"S": float, "strike": float, "expiry": str}
_resolved: dict = {}


def _months_ahead_date(n: int) -> date:
    """Return the date exactly n calendar months from today."""
    today = date.today()
    month = today.month + n
    year  = today.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    # Clamp day for short months (e.g. Jan 31 + 1 month → Feb 28)
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(today.day, last_day))


def _resolve(live_client, ticker: str, strike_pct: float,
             months_ahead: int, option_type: str) -> dict | None:
    """
    Derive (S, strike, expiry) from live data for one CASES entry.

    Results are cached by case key so each API call is made only once
    regardless of how many test steps reference the same case.
    """
    key = (ticker, strike_pct, months_ahead, option_type)
    if key in _resolved:
        return _resolved[key]

    # Current stock price
    resp = live_client.get(f"/api/stock/{ticker}")
    if resp.status_code != 200:
        return None
    S = (resp.get_json() or {}).get("current_price")
    if not S:
        return None

    # Target strike = S offset by strike_pct %
    target_strike = S * (1 + strike_pct / 100)

    # All expirations (need ?all=true so months-ahead cases aren't clipped)
    resp = live_client.get(f"/api/expirations/{ticker}?all=true")
    if resp.status_code != 200:
        return None
    expirations = (resp.get_json() or {}).get("expirations", [])

    # First expiry on or after the cutoff date; if the chain doesn't reach that
    # far (e.g. thinly-traded CEFs), fall back to the last available expiry.
    cutoff = _months_ahead_date(months_ahead)
    expiry = next(
        (e for e in expirations
         if datetime.strptime(e, "%Y-%m-%d").date() >= cutoff),
        expirations[-1] if expirations else None,
    )
    if not expiry:
        return None

    # Nearest listed strike to target
    resp = live_client.get(f"/api/options/{ticker}/{expiry}")
    if resp.status_code != 200:
        return None
    chain = resp.get_json() or {}
    leg     = "calls" if option_type == "call" else "puts"
    strikes = [o["strike"] for o in chain.get(leg, [])]
    if not strikes:
        return None
    strike = min(strikes, key=lambda s: abs(s - target_strike))

    result = {"S": S, "strike": strike, "expiry": expiry}
    _resolved[key] = result
    return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _strict_json(response):
    """
    Parse the response body the way a browser would.

    Python's json.loads() accepts bare NaN/Infinity by default; browsers do
    not — JSON.parse() throws SyntaxError on them.  We replicate browser
    strictness by scanning the raw text before parsing.
    """
    raw = response.data.decode("utf-8")
    for token in ("NaN", "Infinity", "-Infinity"):
        if token in raw:
            idx = raw.index(token)
            pytest.fail(
                f"Response body contains '{token}' — not valid JSON; "
                f"browsers will throw SyntaxError:\n"
                f"  context: …{raw[max(0, idx - 30):idx + 40]}…"
            )
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"Response body is not valid JSON:\n"
            f"  error  : {exc}\n"
            f"  snippet: {raw[:300]}"
        )


def _has_nan(obj) -> bool:
    """Recursively check for NaN floats in a parsed JSON structure."""
    if isinstance(obj, float) and math.isnan(obj):
        return True
    if isinstance(obj, dict):
        return any(_has_nan(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_has_nan(v) for v in obj)
    return False


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def live_client():
    """Flask test client with a valid session — no mocking."""
    from main_web import app
    app.config["TESTING"] = True
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["authenticated"] = True
        sess["last_activity"] = datetime.now().isoformat()
    return client


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.network
class TestFairValueLoad:
    """
    Each parametrized run exercises the complete fair value flow for one case.
    Strike and expiry are resolved from live data; all six steps must pass.
    """

    # ── Step 1: stock info ────────────────────────────────────────────────────
    @pytest.mark.parametrize("ticker,strike_pct,months_ahead,option_type", CASES, ids=_IDS)
    def test_01_stock_info(self, live_client, ticker, strike_pct, months_ahead, option_type):
        resp = live_client.get(f"/api/stock/{ticker}")
        assert resp.status_code == 200, (
            f"GET /api/stock/{ticker} → {resp.status_code}: {resp.data.decode()}"
        )
        data = _strict_json(resp)
        S = data.get("current_price") or 0
        assert S > 0, f"current_price missing or zero for {ticker}: {data}"
        target = S * (1 + strike_pct / 100)
        sign   = "+" if strike_pct >= 0 else ""
        print(f"\n  [{months_ahead}mo {option_type}] S=${S:.2f}  "
              f"target_strike=${target:.2f} ({sign}{strike_pct}%)")

    # ── Step 2: expiry resolution ─────────────────────────────────────────────
    @pytest.mark.parametrize("ticker,strike_pct,months_ahead,option_type", CASES, ids=_IDS)
    def test_02_expiry_resolved(self, live_client, ticker, strike_pct, months_ahead, option_type):
        r = _resolve(live_client, ticker, strike_pct, months_ahead, option_type)
        if r is None:
            pytest.skip(f"{ticker}: no expiry >= {months_ahead} month(s) out in option chain")
        cutoff   = _months_ahead_date(months_ahead)
        exp_date = datetime.strptime(r["expiry"], "%Y-%m-%d").date()
        print(f"\n  cutoff={cutoff}  resolved expiry={r['expiry']}")
        assert exp_date >= cutoff, (
            f"Resolved expiry {r['expiry']} is before cutoff {cutoff}"
        )

    # ── Step 3: options chain — valid JSON, no NaN ────────────────────────────
    @pytest.mark.parametrize("ticker,strike_pct,months_ahead,option_type", CASES, ids=_IDS)
    def test_03_options_chain_valid_json(
        self, live_client, ticker, strike_pct, months_ahead, option_type
    ):
        r = _resolve(live_client, ticker, strike_pct, months_ahead, option_type)
        if r is None:
            pytest.skip(f"{ticker}: no expiry >= {months_ahead} month(s) out in option chain")
        resp = live_client.get(f"/api/options/{ticker}/{r['expiry']}")
        assert resp.status_code == 200, (
            f"GET /api/options/{ticker}/{r['expiry']} → "
            f"{resp.status_code}: {resp.data.decode()}"
        )
        data = _strict_json(resp)
        assert "calls" in data, f"'calls' key missing: {list(data)}"
        assert "puts"  in data, f"'puts'  key missing: {list(data)}"
        assert not _has_nan(data), "Option chain contains NaN float values"

    # ── Step 4: resolved strike present in the chain ──────────────────────────
    @pytest.mark.parametrize("ticker,strike_pct,months_ahead,option_type", CASES, ids=_IDS)
    def test_04_strike_in_chain(
        self, live_client, ticker, strike_pct, months_ahead, option_type
    ):
        r = _resolve(live_client, ticker, strike_pct, months_ahead, option_type)
        if r is None:
            pytest.skip(f"{ticker}: no expiry >= {months_ahead} month(s) out in option chain")
        resp    = live_client.get(f"/api/options/{ticker}/{r['expiry']}")
        data    = _strict_json(resp)
        leg     = "calls" if option_type == "call" else "puts"
        strikes = {o["strike"] for o in data.get(leg, [])}
        print(f"\n  target=${r['S'] * (1 + strike_pct/100):.2f}  "
              f"resolved_strike=${r['strike']:.2f}  expiry={r['expiry']}")
        assert r["strike"] in strikes, (
            f"Resolved strike {r['strike']} not found in {ticker} {leg} for {r['expiry']}.\n"
            f"Available: {sorted(strikes)}"
        )

    # ── Step 5: ATM IV ────────────────────────────────────────────────────────
    @pytest.mark.parametrize("ticker,strike_pct,months_ahead,option_type", CASES, ids=_IDS)
    def test_05_atm_iv(self, live_client, ticker, strike_pct, months_ahead, option_type):
        r = _resolve(live_client, ticker, strike_pct, months_ahead, option_type)
        if r is None:
            pytest.skip(f"{ticker}: no expiry >= {months_ahead} month(s) out in option chain")
        resp = live_client.get(
            f"/api/atm-iv/{ticker}/{r['expiry']}/{option_type}"
            f"?S={r['S']}&r=0.045"
        )
        assert resp.status_code == 200, resp.data.decode()
        data = _strict_json(resp)
        iv   = data.get("atm_iv")
        print(f"\n  atm_iv={iv}")
        assert iv is not None, f"atm_iv missing: {data}"
        assert iv > 0,         f"atm_iv not positive: {iv}"

    # ── Step 6: fair value ────────────────────────────────────────────────────
    @pytest.mark.parametrize("ticker,strike_pct,months_ahead,option_type", CASES, ids=_IDS)
    def test_06_fair_value(self, live_client, ticker, strike_pct, months_ahead, option_type):
        """
        POST /api/calculate must return a valid, positive fair value.

        Mirrors the UI: uses live price + dividend yield, prefers the
        specific strike's IV, falls back to ATM IV, then 30% default.
        """
        r = _resolve(live_client, ticker, strike_pct, months_ahead, option_type)
        if r is None:
            pytest.skip(f"{ticker}: no expiry >= {months_ahead} month(s) out in option chain")

        S      = r["S"]
        K      = r["strike"]
        expiry = r["expiry"]

        stock = _strict_json(live_client.get(f"/api/stock/{ticker}"))
        q     = stock.get("dividend_yield") or 0.0

        chain = _strict_json(live_client.get(f"/api/options/{ticker}/{expiry}"))
        leg   = "calls" if option_type == "call" else "puts"
        opts  = {o["strike"]: o for o in chain.get(leg, [])}
        opt   = opts.get(K)
        sigma = (opt or {}).get("implied_volatility") or None

        if not sigma or sigma <= 0:
            atm   = _strict_json(live_client.get(
                f"/api/atm-iv/{ticker}/{expiry}/{option_type}?S={S}&r=0.045"
            ))
            sigma = atm.get("atm_iv") or 0.30

        payload = {
            "S": S, "K": K, "expiration": expiry,
            "sigma": sigma, "r": 0.045, "q": q,
            "option_type": option_type,
        }
        print(f"\n  S=${S:.2f}  K=${K:.2f}  exp={expiry}  "
              f"sigma={sigma:.4f}  q={q:.4f}")

        resp = live_client.post(
            "/api/calculate", json=payload, content_type="application/json",
        )
        assert resp.status_code == 200, (
            f"POST /api/calculate failed for {ticker} K={K} {expiry} {option_type}\n"
            f"  payload  : {payload}\n"
            f"  response ({resp.status_code}): {resp.data.decode()}"
        )

        result = _strict_json(resp)
        price  = result.get("price")

        assert price is not None,      f"'price' key missing: {result}"
        assert math.isfinite(price),   f"price is not finite: {price}"
        assert price > 0,              f"price not positive: {price}"
        assert result.get("T", 0) >= 0, f"T is negative: {result}"

        for greek in ("delta", "gamma", "theta", "vega", "rho"):
            assert greek in result.get("greeks", {}), (
                f"Greek '{greek}' missing: {result.get('greeks')}"
            )
        print(f"  price=${price:.4f}  T={result['T']:.4f}  "
              f"greeks={result['greeks']}")
