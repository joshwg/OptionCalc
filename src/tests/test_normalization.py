"""
Tests for normalize_dividend_yield() and normalize_implied_volatility().

Both functions handle the quirk that Yahoo Finance sometimes returns values
as percentages (e.g. 0.42 meaning 0.42%) rather than true decimals (0.0042).
All tests are pure-unit (no network).
"""

import unittest
import pytest
from option_lib.yahoo_data import normalize_dividend_yield, normalize_implied_volatility
from option_lib.math_util import get_days_to_expiration, get_years_to_expiration


# ═══════════════════════════════════════════════════════════════════════════
# Dividend-yield normalisation
# ═══════════════════════════════════════════════════════════════════════════

class TestNormalizeDividendYield(unittest.TestCase):
    """
    Business rule (from docstring / known Yahoo Finance behaviour):
      - Values ≤ 0.10 are treated as already-decimal  →  returned as-is
      - Values  > 0.10 are treated as percentage       →  divided by 100
      - None / zero                                    →  0.0
    """

    def _n(self, val):
        return normalize_dividend_yield(val)

    # ── None / zero ───────────────────────────────────────────────────────

    def test_none_returns_zero(self):
        self.assertEqual(self._n(None), 0.0)

    def test_zero_returns_zero(self):
        self.assertEqual(self._n(0), 0.0)

    def test_zero_float_returns_zero(self):
        self.assertEqual(self._n(0.0), 0.0)

    # ── already-decimal (≤ 0.10) ──────────────────────────────────────────

    def test_small_decimal_unchanged(self):
        # 0.0042 → already decimal (0.42%)
        self.assertAlmostEqual(self._n(0.0042), 0.0042, places=6)

    def test_threshold_exactly_at_0_10(self):
        # 0.10 = 10% yield — treated as already-decimal
        self.assertAlmostEqual(self._n(0.10), 0.10, places=6)

    def test_just_below_threshold(self):
        self.assertAlmostEqual(self._n(0.09), 0.09, places=6)

    def test_moderate_yield_already_decimal(self):
        # 0.055 = 5.5% — already decimal
        self.assertAlmostEqual(self._n(0.055), 0.055, places=6)

    # ── percentage values (> 0.10) ────────────────────────────────────────

    def test_apple_style_percent(self):
        # Yahoo returns 0.42 for 0.42% → should become 0.0042
        self.assertAlmostEqual(self._n(0.42), 0.0042, places=6)

    def test_just_above_threshold(self):
        # 0.11 → treated as 0.11% → 0.0011
        self.assertAlmostEqual(self._n(0.11), 0.0011, places=6)

    def test_typical_yield_percent(self):
        # 1.89 → 1.89% → 0.0189
        self.assertAlmostEqual(self._n(1.89), 0.0189, places=6)

    def test_moderate_yield_percent(self):
        # 5.5 → 5.5% → 0.055
        self.assertAlmostEqual(self._n(5.5), 0.055, places=6)

    def test_high_yield_reit_style(self):
        # 15.0 → 15% → 0.15
        self.assertAlmostEqual(self._n(15.0), 0.15, places=6)

    def test_extreme_etf_yield(self):
        # 83.17 → 83.17% → 0.8317 (YieldMax-style)
        self.assertAlmostEqual(self._n(83.17), 0.8317, places=4)

    # ── result is always in [0, 1] ────────────────────────────────────────

    def test_result_always_non_negative(self):
        for val in [None, 0, 0.001, 0.10, 0.42, 5.5, 83.17]:
            self.assertGreaterEqual(self._n(val), 0.0)

    def test_result_never_exceeds_one(self):
        # Even a 100% yield should not produce a value > 1
        for val in [0.42, 5.5, 15.0, 83.17, 100.0]:
            result = self._n(val)
            self.assertLessEqual(result, 1.0,
                                 msg=f"normalize_dividend_yield({val}) = {result} > 1")


# ═══════════════════════════════════════════════════════════════════════════
# Implied-volatility normalisation
# ═══════════════════════════════════════════════════════════════════════════

class TestNormalizeImpliedVolatility(unittest.TestCase):
    """
    Business rule:
      - Values > 2  are treated as percentage (e.g. 25.5 → 0.255)
      - Values ≤ 2  are treated as already-decimal (e.g. 0.255 → 0.255)
      - None / zero → 0.0
    """

    def _n(self, val):
        return normalize_implied_volatility(val)

    # ── None / zero ───────────────────────────────────────────────────────

    def test_none_returns_zero(self):
        self.assertEqual(self._n(None), 0.0)

    def test_zero_returns_zero(self):
        self.assertEqual(self._n(0), 0.0)

    # ── already-decimal (≤ 2.0) ───────────────────────────────────────────

    def test_typical_iv_decimal(self):
        # 0.255 → already decimal (25.5%)
        self.assertAlmostEqual(self._n(0.255), 0.255, places=6)

    def test_low_iv_decimal(self):
        self.assertAlmostEqual(self._n(0.05), 0.05, places=6)

    def test_high_iv_decimal_at_boundary(self):
        # 2.0 = 200% vol — still treated as decimal
        self.assertAlmostEqual(self._n(2.0), 2.0, places=6)

    def test_just_below_boundary(self):
        self.assertAlmostEqual(self._n(1.99), 1.99, places=4)

    # ── percentage values (> 2.0) ─────────────────────────────────────────

    def test_typical_iv_as_percent(self):
        # Yahoo sometimes returns 25.5 for 25.5%
        self.assertAlmostEqual(self._n(25.5), 0.255, places=4)

    def test_low_iv_as_percent(self):
        self.assertAlmostEqual(self._n(10.0), 0.10, places=4)

    def test_high_iv_as_percent(self):
        # 99.86% (CRDO-style)
        self.assertAlmostEqual(self._n(99.86), 0.9986, places=4)

    def test_just_above_boundary(self):
        self.assertAlmostEqual(self._n(2.01), 0.0201, places=4)

    # ── result sanity ─────────────────────────────────────────────────────

    def test_result_always_non_negative(self):
        for val in [None, 0, 0.25, 1.0, 25.5, 100.0]:
            self.assertGreaterEqual(self._n(val), 0.0)

    def test_decimal_and_percent_equivalent(self):
        """normalize(0.25) == normalize(25.0) — both represent 25% vol."""
        self.assertAlmostEqual(self._n(0.25), self._n(25.0), places=4)


# ═══════════════════════════════════════════════════════════════════════════
# Date / time utilities (pure, no network)
# ═══════════════════════════════════════════════════════════════════════════

class TestDateUtilities(unittest.TestCase):

    def _future(self, days):
        from datetime import datetime, timedelta
        return (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')

    def _past(self, days):
        from datetime import datetime, timedelta
        return (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    # ── get_days_to_expiration ─────────────────────────────────────────────

    def test_future_date_returns_positive_days(self):
        days = get_days_to_expiration(self._future(30))
        self.assertGreaterEqual(days, 29)
        self.assertLessEqual(days, 31)

    def test_past_date_returns_zero(self):
        days = get_days_to_expiration(self._past(5))
        self.assertEqual(days, 0)

    def test_far_future_days(self):
        days = get_days_to_expiration(self._future(500))
        self.assertAlmostEqual(days, 500, delta=2)

    # ── get_years_to_expiration ────────────────────────────────────────────

    def test_one_year_out(self):
        years = get_years_to_expiration(self._future(365))
        self.assertAlmostEqual(years, 1.0, delta=0.01)

    def test_short_term(self):
        years = get_years_to_expiration(self._future(30))
        self.assertAlmostEqual(years, 30 / 365, delta=0.005)

    def test_past_date_returns_zero_years(self):
        years = get_years_to_expiration(self._past(10))
        self.assertLessEqual(years, 0)

    def test_long_dated_option(self):
        # CRDO-style: ~500 days out
        years = get_years_to_expiration(self._future(500))
        self.assertAlmostEqual(years, 500 / 365, delta=0.01)


# ═══════════════════════════════════════════════════════════════════════════
# Time-to-expiry near expiration
# ═══════════════════════════════════════════════════════════════════════════

class TestNearExpiryTime(unittest.TestCase):
    """T must count the hours left to the 16:00 ET close, not whole days.

    Flooring to calendar days understates T by 20%+ on the day before expiry
    and collapses it to exactly zero on expiry day, which prices every OTM
    contract at intrinsic (0.00) with all greeks zeroed while it is still
    trading.
    """

    def _et_today(self):
        from datetime import datetime
        from option_lib.math_util import MARKET_TZ
        return datetime.now(MARKET_TZ).date()

    def _past(self, days):
        from datetime import timedelta
        return (self._et_today() - timedelta(days=days)).strftime('%Y-%m-%d')

    def _future(self, days):
        from datetime import timedelta
        return (self._et_today() + timedelta(days=days)).strftime('%Y-%m-%d')

    def test_expiry_day_has_time_left_before_close(self):
        from datetime import datetime
        from option_lib.math_util import MARKET_TZ, get_hours_to_expiration
        now = datetime.now(MARKET_TZ)
        today = self._et_today().strftime('%Y-%m-%d')
        hours = get_hours_to_expiration(today)
        if now.hour < 16:
            self.assertGreater(hours, 0, "0DTE before the close must retain time value")
            self.assertGreater(get_years_to_expiration(today), 0)
        else:
            self.assertEqual(hours, 0.0)

    def test_tomorrow_exceeds_one_day_when_before_close(self):
        from datetime import datetime, timedelta
        from option_lib.math_util import MARKET_TZ, get_hours_to_expiration
        now = datetime.now(MARKET_TZ)
        tomorrow = (self._et_today() + timedelta(days=1)).strftime('%Y-%m-%d')
        hours = get_hours_to_expiration(tomorrow)
        if now.hour < 16:
            # Intraday today → more than 24h remain to tomorrow's 16:00 close
            self.assertGreater(hours, 24.0)
        self.assertLessEqual(hours, 40.0)

    def test_past_expiry_is_zero_not_negative(self):
        from option_lib.math_util import get_hours_to_expiration
        self.assertEqual(get_hours_to_expiration(self._past(3)), 0.0)
        self.assertEqual(get_years_to_expiration(self._past(3)), 0.0)

    def test_days_field_remains_whole_days(self):
        # get_days_to_expiration stays integral — it is a display value
        days = get_days_to_expiration(self._future(7))
        self.assertIsInstance(days, int)

    def test_malformed_date_is_handled(self):
        from option_lib.math_util import get_hours_to_expiration
        self.assertEqual(get_hours_to_expiration('not-a-date'), 0.0)
        self.assertEqual(get_years_to_expiration('not-a-date'), 0.0)


# ═══════════════════════════════════════════════════════════════════════════
# Weekend price carry
# ═══════════════════════════════════════════════════════════════════════════

class TestWeekendCarry(unittest.TestCase):
    """Friday's after-hours print stays the freshest quote until Monday 04:00 ET.

    Falling back to current_price over the weekend would price two and a half
    days off Friday's 16:00 close and discard every after-hours move.
    """

    INFO = {'current_price': 100.0, 'post_market_price': 104.0, 'pre_market_price': 97.0}

    def _at(self, y, m, d, hh, mm=0):
        from datetime import datetime
        from option_lib.math_util import MARKET_TZ
        return datetime(y, m, d, hh, mm, tzinfo=MARKET_TZ)

    def _S(self, when):
        from option_lib.math_util import extended_underlying
        return extended_underlying(self.INFO, when)

    # 2026-08-07 is a Friday
    def test_friday_evening_uses_post(self):
        self.assertEqual(self._S(self._at(2026, 8, 7, 18)), 104.0)

    def test_saturday_small_hours_uses_post(self):
        self.assertEqual(self._S(self._at(2026, 8, 8, 2)), 104.0)

    def test_saturday_daytime_carries_friday_post(self):
        self.assertEqual(self._S(self._at(2026, 8, 8, 11)), 104.0)

    def test_sunday_carries_friday_post(self):
        self.assertEqual(self._S(self._at(2026, 8, 9, 12)), 104.0)

    def test_monday_before_premarket_carries_friday_post(self):
        self.assertEqual(self._S(self._at(2026, 8, 10, 2)), 104.0)

    def test_monday_premarket_switches_to_pre(self):
        self.assertEqual(self._S(self._at(2026, 8, 10, 5)), 97.0)

    def test_monday_regular_hours_uses_current(self):
        self.assertEqual(self._S(self._at(2026, 8, 10, 10)), 100.0)

    def test_weekend_falls_back_when_post_missing(self):
        from option_lib.math_util import extended_underlying
        info = {'current_price': 100.0, 'post_market_price': None}
        self.assertEqual(extended_underlying(info, self._at(2026, 8, 9, 12)), 100.0)


if __name__ == '__main__':
    unittest.main()
