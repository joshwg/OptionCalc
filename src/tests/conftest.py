"""
Pytest configuration and shared fixtures for the OptionCalculator test suite.

PYTHONPATH note: pytest.ini sets testpaths=src/tests.  This conftest adds
src/ (and the option_lib parent) to sys.path before any test module is
imported, so all application modules resolve correctly.
"""

import os
import sys
from datetime import datetime

# ── Path setup ─────────────────────────────────────────────────────────────
# src/  — application modules (option_pricing, yahoo_data, …)
_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# lab/  — parent of OptionCalculator, needed so `import option_lib` works
_LAB = os.path.abspath(os.path.join(_SRC, "..", ".."))
for _p in (_SRC, _LAB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── OPTION_PWD must be set before main_web is imported (it reads it at
#    module load time).  os.environ.setdefault leaves a real value intact.
os.environ.setdefault("OPTION_PWD", "test")

import pytest


# ── Flask application fixture ───────────────────────────────────────────────

@pytest.fixture(scope="session")
def flask_app():
    """Return a Flask app instance configured for testing."""
    from main_web import app
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    return app


@pytest.fixture
def client(flask_app):
    """Unauthenticated test client."""
    return flask_app.test_client()


@pytest.fixture
def auth_client(flask_app):
    """Test client with a valid authenticated session already established."""
    c = flask_app.test_client()
    with c.session_transaction() as sess:
        sess["authenticated"] = True
        sess["last_activity"] = datetime.now().isoformat()
    return c


# ── Common option-pricing parameters ──────────────────────────────────────

@pytest.fixture
def atm_params():
    """Standard ATM option parameters used across many tests."""
    return dict(S=100.0, K=100.0, T=1.0, r=0.05, sigma=0.20, q=0.0)


@pytest.fixture
def chain_data():
    """Minimal synthetic option chain (5 puts, 5 calls around $100)."""
    strikes = [80.0, 90.0, 100.0, 110.0, 120.0]
    iv_base = 0.25
    rows = []
    for k in strikes:
        # rough synthetic bid/ask — not meant to be arbitrage-free
        mid = max(0.5, abs(k - 100) * 0.4 + iv_base * 10)
        rows.append({
            "strike": k,
            "bid": round(mid * 0.95, 2),
            "ask": round(mid * 1.05, 2),
            "implied_volatility": iv_base + abs(k - 100) * 0.001,
        })
    return rows
