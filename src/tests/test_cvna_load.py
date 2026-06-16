"""
Integration test: simulate the full "Load Stock Data" button click for CVNA.

Reproduces the bug where NaN implied_volatility values in low-liquidity option
strikes produce invalid JSON: Python's json.dumps serialises float('nan') as
the bare token NaN, which browsers reject with a SyntaxError — exactly what
breaks CVNA while AAPL (fully liquid, no NaN) works fine.

Marked @pytest.mark.network — requires live Yahoo Finance access.  Run with:

    PYTHONPATH=src:/mnt/c/Users/josh/Docs/lab venv/bin/python \
        -m pytest src/tests/test_cvna_load.py -v
"""

import json
import math
import pytest
from datetime import datetime


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strict_json(response):
    """
    Parse the response body the way a browser would.

    Python's json.loads() accepts bare NaN/Infinity tokens by default
    (allow_nan=True).  Browsers do not — JSON.parse() throws SyntaxError on
    them.  We replicate browser strictness by checking the raw text before
    parsing.
    """
    raw = response.data.decode("utf-8")
    # Browser-equivalent check: NaN/Infinity are not valid JSON tokens
    for token in ("NaN", "Infinity", "-Infinity"):
        if token in raw:
            idx = raw.index(token)
            pytest.fail(
                f"Response body contains '{token}' — not valid JSON; "
                f"browsers will throw SyntaxError:\n"
                f"  context: …{raw[max(0, idx-30):idx+40]}…"
            )
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"Response body is not valid JSON (browsers would fail here):\n"
            f"  error  : {exc}\n"
            f"  snippet: {raw[:200]}"
        )


def _has_nan(obj):
    """Recursively check for NaN floats in a parsed JSON structure."""
    if isinstance(obj, float) and math.isnan(obj):
        return True
    if isinstance(obj, dict):
        return any(_has_nan(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_has_nan(v) for v in obj)
    return False


# ---------------------------------------------------------------------------
# Tests — same sequence as the browser's loadStockData() → loadExpirations()
#          → onExpirationChange() → loadQuickView()
# ---------------------------------------------------------------------------

@pytest.mark.network
class TestCVNALoad:

    TICKER = "CVNA"

    # Step 1 ─────────────────────────────────────────────────────────────────
    def test_01_stock_info_returns_200(self, live_client):
        resp = live_client.get(f"/api/stock/{self.TICKER}")
        assert resp.status_code == 200, resp.data

    def test_02_stock_info_valid_json(self, live_client):
        resp = live_client.get(f"/api/stock/{self.TICKER}")
        data = _strict_json(resp)
        assert data.get("current_price") is not None, "current_price missing"
        assert data.get("current_price") > 0

    # Step 2 ─────────────────────────────────────────────────────────────────
    def test_03_expirations_returns_200(self, live_client):
        resp = live_client.get(f"/api/expirations/{self.TICKER}")
        assert resp.status_code == 200, resp.data

    def test_04_expirations_has_dates(self, live_client):
        resp = live_client.get(f"/api/expirations/{self.TICKER}")
        data = _strict_json(resp)
        assert len(data.get("expirations", [])) > 0, "no expirations returned"

    # Step 3 — the bug lives here ────────────────────────────────────────────
    def test_05_options_chain_valid_json(self, live_client):
        """
        /api/options/<ticker>/<exp> must return strictly valid JSON.

        Python's json.dumps() serialises float('nan') as the bare token NaN,
        which is not valid JSON.  Browsers call JSON.parse() and throw a
        SyntaxError; the JS catch block returns null and shows the vague
        "Failed to load options" message.
        """
        exps = _strict_json(live_client.get(f"/api/expirations/{self.TICKER}"))
        first_exp = exps["expirations"][0]
        resp = live_client.get(f"/api/options/{self.TICKER}/{first_exp}")
        assert resp.status_code == 200, resp.data
        data = _strict_json(resp)          # raises if NaN tokens are present
        assert "calls" in data
        assert "puts" in data

    def test_06_options_chain_no_nan_values(self, live_client):
        """No NaN floats in the parsed option chain (belt-and-braces check)."""
        exps = _strict_json(live_client.get(f"/api/expirations/{self.TICKER}"))
        first_exp = exps["expirations"][0]
        resp = live_client.get(f"/api/options/{self.TICKER}/{first_exp}")
        data = _strict_json(resp)
        assert not _has_nan(data), "Option chain contains NaN values"

    # Step 4 ─────────────────────────────────────────────────────────────────
    def test_07_iv_endpoint_with_atm_strike(self, live_client):
        """POST /api/iv should succeed for the CVNA ATM call."""
        stock = _strict_json(live_client.get(f"/api/stock/{self.TICKER}"))
        S = stock["current_price"]
        exps  = _strict_json(live_client.get(f"/api/expirations/{self.TICKER}"))
        exp   = exps["expirations"][0]
        chain = _strict_json(live_client.get(f"/api/options/{self.TICKER}/{exp}"))

        calls = sorted(chain["calls"], key=lambda o: o["strike"])
        atm   = next((o for o in calls if o["strike"] >= S), calls[-1])

        resp = live_client.post(
            "/api/iv",
            json={
                "market_price": (atm["bid"] + atm["ask"]) / 2,
                "S":            S,
                "K":            atm["strike"],
                "T":            chain["T"],
                "r":            0.045,
                "option_type":  "call",
            },
            content_type="application/json",
        )
        assert resp.status_code == 200, resp.data

    # Step 5 ─────────────────────────────────────────────────────────────────
    def test_08_atm_iv_quick_view(self, live_client):
        """GET /api/atm-iv/<ticker>/<exp>/call should succeed."""
        stock = _strict_json(live_client.get(f"/api/stock/{self.TICKER}"))
        S = stock["current_price"]
        exps = _strict_json(live_client.get(f"/api/expirations/{self.TICKER}"))
        exp  = exps["expirations"][0]
        resp = live_client.get(f"/api/atm-iv/{self.TICKER}/{exp}/call?S={S}&r=0.045")
        assert resp.status_code == 200, resp.data
        data = _strict_json(resp)
        assert "atm_iv" in data
