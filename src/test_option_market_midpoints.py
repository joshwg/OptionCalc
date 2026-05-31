"""
Option Market Mid-Price vs Model Comparison
Fetches live option chains for AAPL, TSLA, NVDA and compares Yahoo Finance
mid-prices against our American binomial pricing model.  Explains divergences.
"""

import sys
import os
import math
from collections import defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yahoo_data as yd
import option_pricing as bs

TICKERS = ['AAPL', 'TSLA', 'NVDA']
RISK_FREE_RATE = 0.045   # 4.5% — adjust to current T-bill rate as needed
TARGET_DAYS = 30          # target ~30 DTE expiration
N_STRIKES = 2             # strikes on each side of ATM to include


def find_target_expiration(expirations, target_days=30):
    target_date = datetime.now() + timedelta(days=target_days)
    return min(
        expirations,
        key=lambda d: abs((datetime.strptime(d, '%Y-%m-%d') - target_date).days)
    )


def get_atm_strikes(all_strikes_sorted, current_price, n=2):
    if not all_strikes_sorted:
        return []
    atm_idx = min(range(len(all_strikes_sorted)),
                  key=lambda i: abs(all_strikes_sorted[i] - current_price))
    start = max(0, atm_idx - n)
    end = min(len(all_strikes_sorted), atm_idx + n + 1)
    return all_strikes_sorted[start:end]


def analyze_ticker(ticker):
    print(f"\n{'━' * 80}")
    print(f"  {ticker}")
    print(f"{'━' * 80}")

    stock = yd.get_stock_info(ticker)
    if not stock['success']:
        print(f"  ERROR: {stock.get('error')}")
        return []

    S = stock['current_price']
    q = stock['dividend_yield']

    hist_vol = yd.calculate_historical_volatility(ticker, days=30)
    if hist_vol is None:
        hist_vol = 0.30
        hv_note = "(default — could not calculate)"
    else:
        hv_note = ""

    expirations = yd.get_expiration_dates(ticker)
    if not expirations:
        print("  ERROR: No expirations available")
        return []

    exp_date = find_target_expiration(expirations, TARGET_DAYS)
    T = yd.get_years_to_expiration(exp_date)
    dte = yd.get_days_to_expiration(exp_date)

    if T <= 0:
        print(f"  ERROR: Expiration {exp_date} is in the past")
        return []

    options = yd.get_options_for_expiration(ticker, exp_date)
    if not options['success']:
        print(f"  ERROR: {options.get('error')}")
        return []

    print(f"  Stock price : ${S:.2f}")
    print(f"  Div yield   : {q * 100:.2f}%")
    print(f"  Hist vol 30d: {hist_vol * 100:.1f}% {hv_note}")
    print(f"  Expiration  : {exp_date}  ({dte} DTE)")
    print(f"  Risk-free r : {RISK_FREE_RATE * 100:.1f}%")

    calls_map = {o['strike']: o for o in options['calls']}
    puts_map  = {o['strike']: o for o in options['puts']}
    all_strikes = sorted(set(list(calls_map.keys()) + list(puts_map.keys())))
    target_strikes = get_atm_strikes(all_strikes, S, n=N_STRIKES)

    header = (
        f"  {'Strike':>8}  {'Type':>4}  {'Bid':>7}  {'Ask':>7}  "
        f"{'Mid':>7}  {'Model(HV)':>9}  {'Mkt IV':>6}  "
        f"{'Model(IV)':>9}  {'Diff$':>7}  {'Diff%':>7}"
    )
    sep = "  " + "  ".join([
        "-" * 8, "-" * 4, "-" * 7, "-" * 7, "-" * 7,
        "-" * 9, "-" * 6, "-" * 9, "-" * 7, "-" * 7
    ])
    print(f"\n{header}")
    print(sep)

    rows = []
    for strike in target_strikes:
        for opt_type, chain in [('call', calls_map), ('put', puts_map)]:
            opt = chain.get(strike)
            if opt is None:
                continue
            bid, ask = opt['bid'], opt['ask']
            if bid <= 0 and ask <= 0:
                continue
            mid = (bid + ask) / 2.0
            if mid <= 0:
                continue

            model_hv = bs.american_option_binomial(
                S, strike, T, RISK_FREE_RATE, hist_vol, q=q, option_type=opt_type
            )

            mkt_iv = opt.get('implied_volatility') or 0
            if mkt_iv > 0:
                model_iv = bs.american_option_binomial(
                    S, strike, T, RISK_FREE_RATE, mkt_iv, q=q, option_type=opt_type
                )
                iv_str = f"{mkt_iv * 100:.1f}%"
                iv_model_str = f"${model_iv:>8.2f}"
            else:
                model_iv = None
                iv_str = "  N/A"
                iv_model_str = "      N/A"

            diff_d = model_hv - mid
            diff_pct = (diff_d / mid * 100) if mid > 0 else float('nan')

            print(
                f"  {strike:>8.1f}  {opt_type:>4}  ${bid:>6.2f}  ${ask:>6.2f}  "
                f"${mid:>6.2f}  ${model_hv:>8.2f}  {iv_str:>6}  "
                f"{iv_model_str:>9}  ${diff_d:>+6.2f}  {diff_pct:>+6.1f}%"
            )

            rows.append({
                'ticker': ticker,
                'strike': strike,
                'type': opt_type,
                'S': S, 'T': T, 'q': q,
                'mid': mid,
                'bid': bid, 'ask': ask,
                'spread': ask - bid,
                'hist_vol': hist_vol,
                'model_hv': model_hv,
                'mkt_iv': mkt_iv,
                'model_iv': model_iv,
                'diff_d': diff_d,
                'diff_pct': diff_pct,
            })

    return rows


def print_analysis(all_rows):
    if not all_rows:
        return

    by_ticker = defaultdict(list)
    for r in all_rows:
        by_ticker[r['ticker']].append(r)

    print(f"\n\n{'═' * 80}")
    print("  WHY MODEL PRICES DIFFER FROM MARKET MID PRICES")
    print(f"{'═' * 80}")

    # ── 1. Volatility mismatch ────────────────────────────────────────────────
    print("\n  1.  VOLATILITY MISMATCH  (usually the dominant driver)")
    print("  " + "─" * 76)
    print(
        "  Model(HV) uses 30-day HISTORICAL volatility — backward-looking realized vol.\n"
        "  The market prices options via IMPLIED volatility: a forward-looking consensus\n"
        "  that includes a volatility risk premium.  IV is almost always above HV,\n"
        "  meaning the market charges more than a pure historical-vol model would predict.\n"
    )
    for ticker, rows in by_ticker.items():
        avg_hv = sum(r['hist_vol'] for r in rows) / len(rows) * 100
        ivs = [r['mkt_iv'] for r in rows if r['mkt_iv'] and r['mkt_iv'] > 0]
        if ivs:
            avg_iv = sum(ivs) / len(ivs) * 100
            premium = avg_iv - avg_hv
            print(f"  {ticker:>5}  hist vol: {avg_hv:.1f}%   avg mkt IV: {avg_iv:.1f}%   "
                  f"IV premium: {premium:+.1f} pp")
        else:
            print(f"  {ticker:>5}  hist vol: {avg_hv:.1f}%   avg mkt IV: N/A")

    print(
        "\n  When the model uses the market's own IV  (Model(IV) column)  the price\n"
        "  should be very close to mid.  Any remaining gap comes from items 2–5."
    )

    # ── 2. Volatility smile / skew ────────────────────────────────────────────
    print("\n  2.  VOLATILITY SMILE / SKEW")
    print("  " + "─" * 76)
    print(
        "  Even with the market IV, our model uses a SINGLE flat volatility across\n"
        "  all strikes.  Real markets price each strike at a different IV (the smile).\n"
        "  OTM puts trade at higher IV than OTM calls (put skew) because institutions\n"
        "  buy puts for tail-risk protection.  Our binomial tree cannot reproduce this\n"
        "  strike-dependent pricing; a stochastic-vol model (Heston, SABR) is needed."
    )
    for ticker, rows in by_ticker.items():
        calls = sorted([r for r in rows if r['type'] == 'call' and r['mkt_iv'] > 0],
                       key=lambda r: r['strike'])
        puts  = sorted([r for r in rows if r['type'] == 'put'  and r['mkt_iv'] > 0],
                       key=lambda r: r['strike'])
        if calls and puts:
            call_ivs = [f"{r['strike']:.0f}→{r['mkt_iv']*100:.1f}%" for r in calls]
            put_ivs  = [f"{r['strike']:.0f}→{r['mkt_iv']*100:.1f}%" for r in puts]
            print(f"\n  {ticker} call IVs by strike: {', '.join(call_ivs)}")
            print(f"  {ticker} put  IVs by strike: {', '.join(put_ivs)}")

    # ── 3. Bid-ask spread ─────────────────────────────────────────────────────
    print("\n\n  3.  BID-ASK SPREAD — MID IS NOT A GUARANTEED FILL PRICE")
    print("  " + "─" * 76)
    print(
        "  The mid-price is the arithmetic centre of the spread, not necessarily\n"
        "  where the last trade occurred.  A wide spread means the mid is imprecise.\n"
        "  A model price within ½ the spread is effectively 'at market'.\n"
    )
    for ticker, rows in by_ticker.items():
        if not rows:
            continue
        avg_spread = sum(r['spread'] for r in rows) / len(rows)
        avg_mid    = sum(r['mid']    for r in rows) / len(rows)
        pct        = avg_spread / avg_mid * 100 if avg_mid > 0 else 0
        print(f"  {ticker:>5}  avg spread: ${avg_spread:.2f}  ({pct:.1f}% of mid avg ${avg_mid:.2f})")
        half = avg_spread / 2
        contained = [r for r in rows if abs(r['diff_d']) <= half]
        print(f"         {len(contained)}/{len(rows)} model(HV) prices fall within ½ spread of mid")

    # ── 4. Discrete vs continuous dividends ───────────────────────────────────
    print("\n  4.  DISCRETE vs CONTINUOUS DIVIDENDS")
    print("  " + "─" * 76)
    print(
        "  Our binomial model treats dividends as a continuous yield q, which\n"
        "  effectively leaks value from the stock price at every time step.  Real\n"
        "  dividends are discrete cash payments on specific ex-dividend dates.\n"
        "  For AAPL (~0.4% yield) the effect is minor; it would matter more for\n"
        "  a high-dividend stock where the ex-date falls inside the option's life."
    )

    # ── 5. Model assumptions ─────────────────────────────────────────────────
    print("\n  5.  MODEL ASSUMPTIONS NOT REFLECTED IN MARKET PRICES")
    print("  " + "─" * 76)
    print(
        "  • Constant volatility: actual vol is stochastic; realized vol changes day\n"
        "    to day, and the market demands a premium for that uncertainty.\n"
        "  • No jumps: earnings releases, macro events, and FDA decisions cause\n"
        "    overnight gap moves that geometric Brownian motion cannot model.\n"
        "    TSLA and NVDA are particularly jump-prone; hence their elevated IV.\n"
        "  • Interest-rate sensitivity: traders borrow to delta-hedge; their cost\n"
        "    of capital may differ from the T-bill rate we use.\n"
        "  • Finite binomial steps: 100 steps introduces a small discretization\n"
        "    error vs the Black-Scholes closed form (~0.1–0.5 cents for typical\n"
        "    inputs); this is negligible relative to the other drivers above."
    )

    # ── Summary table ─────────────────────────────────────────────────────────
    print(f"\n  {'─' * 76}")
    print(f"  {'Ticker':>6}  {'Avg |Diff%| (HV)':>17}  {'Avg |Diff%| (IV)':>17}  {'Assessment'}")
    print(f"  {'─' * 6}  {'─' * 17}  {'─' * 17}  {'─' * 30}")
    for ticker, rows in by_ticker.items():
        hv_diffs = [abs(r['diff_pct']) for r in rows if not math.isnan(r['diff_pct'])]
        iv_diffs = []
        for r in rows:
            if r['model_iv'] is not None and r['mid'] > 0:
                iv_diffs.append(abs(r['model_iv'] - r['mid']) / r['mid'] * 100)

        avg_hv = sum(hv_diffs) / len(hv_diffs) if hv_diffs else float('nan')
        avg_iv = sum(iv_diffs) / len(iv_diffs) if iv_diffs else float('nan')

        if not math.isnan(avg_hv):
            assessment = (
                "good fit" if avg_hv < 10 else
                "moderate mismatch" if avg_hv < 30 else
                "large mismatch — IV >> HV"
            )
            hv_str = f"{avg_hv:.1f}%"
        else:
            hv_str, assessment = "N/A", ""

        iv_str = f"{avg_iv:.1f}%" if not math.isnan(avg_iv) else "N/A"
        print(f"  {ticker:>6}  {hv_str:>17}  {iv_str:>17}  {assessment}")

    print()


def main():
    print("╔" + "═" * 78 + "╗")
    print("║   OPTION MARKET MID-PRICE vs MODEL  —  AAPL · TSLA · NVDA" + " " * 19 + "║")
    print("╚" + "═" * 78 + "╝")
    print()
    print("  Columns:")
    print("    Model(HV)  American binomial tree priced with 30-day historical vol")
    print("    Mkt IV     Implied vol reported by Yahoo Finance for that contract")
    print("    Model(IV)  American binomial tree priced with Mkt IV")
    print("    Diff$      Model(HV) − Mid  (positive = model overprices the option)")
    print("    Diff%      Diff$ / Mid")

    all_rows = []
    for ticker in TICKERS:
        rows = analyze_ticker(ticker)
        if rows:
            all_rows.extend(rows)

    print_analysis(all_rows)


if __name__ == '__main__':
    main()
