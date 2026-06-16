"""Web UI entry point for OptionCalculator.

Run:
    export OPTION_PWD=yourpassword
    PYTHONPATH=src python src/main_web.py
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta

from flask import (Flask, jsonify, redirect, render_template,
                   request, send_from_directory, session, url_for)

import yahoo_data as yd
import option_service as svc
import config as _cfg

# ---------------------------------------------------------------------------
# Auth setup — OPTION_PWD must be set before the server starts
# ---------------------------------------------------------------------------

_SESSION_TIMEOUT_MINUTES = 240


def _require_password() -> str:
    pwd = os.environ.get("OPTION_PWD", "")
    if not pwd:
        raise RuntimeError(
            "OPTION_PWD environment variable must be set before starting the web server."
        )
    return pwd


_password = _require_password()

app = Flask(
    __name__,
    template_folder="ui_web/templates",
    static_folder="ui_web/static",
)
app.secret_key = hashlib.sha256(_password.encode()).digest()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

@app.errorhandler(Exception)
def handle_exception(e):
    from werkzeug.exceptions import HTTPException
    # Let Flask return proper 4xx responses for routing/protocol errors
    # (e.g. 404 Not Found, 400 Bad Request for malformed URLs or bad JSON).
    if isinstance(e, HTTPException):
        return e
    import traceback
    app.logger.error(traceback.format_exc())
    return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _is_authenticated() -> bool:
    if not session.get("authenticated"):
        return False
    last_str = session.get("last_activity")
    if not last_str:
        return False
    cutoff = datetime.now() - timedelta(minutes=_SESSION_TIMEOUT_MINUTES)
    try:
        if datetime.fromisoformat(last_str) < cutoff:
            session.clear()
            return False
    except ValueError:
        session.clear()
        return False
    return True


def _touch_session() -> None:
    session["last_activity"] = datetime.now().isoformat()


@app.before_request
def check_auth():
    if request.endpoint in ("login", "logout", "favicon", "static"):
        return
    if not _is_authenticated():
        if request.path.startswith("/api/"):
            return jsonify({"error": "unauthorized"}), 401
        return redirect(url_for("login"))
    _touch_session()


# ---------------------------------------------------------------------------
# Login / logout
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == _password:
            session.clear()
            session["authenticated"] = True
            _touch_session()
            return redirect(url_for("index"))
        error = "Incorrect password."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Favicon (served from src/app_icon.png)
# ---------------------------------------------------------------------------

@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.dirname(os.path.abspath(__file__)),
        "app_icon.png",
        mimetype="image/png",
    )


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Config API
# ---------------------------------------------------------------------------

@app.route("/api/config")
def api_get_config():
    cfg = _cfg.load_config()
    return jsonify({"risk_free_rate": cfg.get("risk_free_rate", 0.045)})


@app.route("/api/config", methods=["POST"])
def api_save_config():
    d = request.json
    try:
        r = float(d["risk_free_rate"])
    except (ValueError, KeyError, TypeError):
        return jsonify({"error": "invalid value"}), 400
    cfg = _cfg.load_config()
    cfg["risk_free_rate"] = r
    _cfg.save_config(cfg)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Stock / search API
# ---------------------------------------------------------------------------

@app.route("/api/search/<query>")
def api_search(query: str):
    results = yd.search_ticker(query.strip(), max_results=10)
    return jsonify(results or [])


@app.route("/api/stock/<ticker>")
def api_stock(ticker: str):
    ticker = ticker.strip().upper()
    info = yd.get_stock_info(ticker)
    if not info.get("success"):
        return jsonify({"error": info.get("error", "Failed to load stock data")}), 400
    return jsonify({
        "ticker":        ticker,
        "company_name":  info.get("company_name"),
        "current_price": info.get("current_price"),
        "previous_close": info.get("previous_close"),
        "volume":        info.get("volume"),
        "dividend_yield": info.get("dividend_yield") or 0,
        "earnings_date":  info.get("earnings_date") or "unavailable",
    })


@app.route("/api/hist-vol/<ticker>")
def api_hist_vol(ticker: str):
    ticker = ticker.strip().upper()
    vol = yd.calculate_historical_volatility(ticker, period="1y")
    if vol is None:
        return jsonify({"error": "Failed to calculate historical volatility"}), 400
    return jsonify({"ticker": ticker, "hist_vol": vol})


# ---------------------------------------------------------------------------
# Options API
# ---------------------------------------------------------------------------

@app.route("/api/expirations/<ticker>")
def api_expirations(ticker: str):
    ticker = ticker.strip().upper()
    all_dates = request.args.get("all", "false").lower() == "true"
    chain = svc.fetch_expirations(ticker, all_dates=all_dates)
    if not chain.get("success"):
        return jsonify({"error": chain.get("error", "Failed to get expirations")}), 400
    return jsonify({"expirations": chain.get("expirations", [])})


@app.route("/api/options/<ticker>/<expiration>")
def api_options(ticker: str, expiration: str):
    ticker = ticker.strip().upper()
    options = yd.get_options_for_expiration(ticker, expiration)
    if not options.get("success"):
        return jsonify({"error": options.get("error", "Failed to get options")}), 400

    _keep = ("strike", "bid", "ask", "implied_volatility")

    def _slim(row):
        return {k: row.get(k) for k in _keep}

    return jsonify({
        "calls": [_slim(o) for o in options.get("calls", [])],
        "puts":  [_slim(o) for o in options.get("puts",  [])],
        "T":     yd.get_years_to_expiration(expiration),
    })


@app.route("/api/atm-iv/<ticker>/<expiration>/<opt_type>")
def api_atm_iv(ticker: str, expiration: str, opt_type: str):
    ticker   = ticker.strip().upper()
    opt_type = opt_type.lower()

    try:
        S = float(request.args.get("S", 0))
    except (ValueError, TypeError):
        S = 0.0

    try:
        r = float(request.args.get("r", 0.045))
    except (ValueError, TypeError):
        r = 0.045

    if not S:
        info = yd.get_stock_info(ticker)
        S = info.get("current_price") or 0.0

    iv = yd.get_atm_implied_volatility(ticker, expiration, S, opt_type, r=r)
    return jsonify({"atm_iv": iv})


# ---------------------------------------------------------------------------
# Calculation API — business logic lives entirely in option_service
# ---------------------------------------------------------------------------

@app.route("/api/calculate", methods=["POST"])
def api_calculate():
    import math
    d = request.json
    if not isinstance(d, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400
    try:
        S        = float(d["S"])
        K        = float(d["K"])
        exp      = d.get("expiration", "")
        sigma    = float(d["sigma"])
        r        = float(d.get("r", 0.045))
        q        = float(d.get("q", 0.0))
        opt_type = d.get("option_type", "call").lower()
    except (ValueError, TypeError, KeyError) as e:
        return jsonify({"error": f"Invalid input: {e}"}), 400

    # Reject non-finite or invalid values that would crash the pricer
    for name, val in [("S", S), ("K", K), ("sigma", sigma), ("r", r), ("q", q)]:
        if not math.isfinite(val):
            return jsonify({"error": f"{name} must be a finite number"}), 400
    if S <= 0:
        return jsonify({"error": "S (stock price) must be positive"}), 400
    if K <= 0:
        return jsonify({"error": "K (strike price) must be positive"}), 400
    if sigma < 0:
        return jsonify({"error": "sigma (volatility) must be non-negative"}), 400
    if sigma == 0:
        return jsonify({"error": "sigma (volatility) is zero — IV was not resolved for this strike"}), 400
    if opt_type not in ("call", "put"):
        return jsonify({"error": "option_type must be 'call' or 'put'"}), 400
    if not exp:
        return jsonify({"error": "expiration date is required"}), 400

    # T=0 is a valid 0DTE option: the pricer returns intrinsic value.
    result = svc.price_option(S, K, exp, sigma, r, q, opt_type)
    return jsonify(result)


@app.route("/api/iv", methods=["POST"])
def api_iv():
    """Compute implied volatility from a market (mid) price."""
    d = request.json
    try:
        market_price = float(d["market_price"])
        S            = float(d["S"])
        K            = float(d["K"])
        r            = float(d.get("r", 0.045))
        opt_type     = d.get("option_type", "call").lower()
    except (ValueError, TypeError, KeyError) as e:
        return jsonify({"error": f"Invalid input: {e}"}), 400

    expiration = d.get("expiration", "")
    if expiration:
        T = yd.get_years_to_expiration(expiration)
    else:
        try:
            T = float(d["T"])
        except (ValueError, TypeError, KeyError):
            return jsonify({"error": "Provide either 'expiration' or 'T'"}), 400

    if T <= 0:
        return jsonify({"iv": None})

    # Delegate to option_service using a minimal option-row shim
    opt_row = {"bid": market_price, "ask": market_price, "implied_volatility": None}
    iv = svc.iv_for_strike(opt_row, K, S, T, r, opt_type)
    return jsonify({"iv": iv})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, port=port)
