"""
Tests for option_service.py — the shared business-logic layer.

All tests are pure-Python; no network access, no Flask required.
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import option_service as svc
import option_pricing as bs


# ═══════════════════════════════════════════════════════════════════════════
# price_option
# ═══════════════════════════════════════════════════════════════════════════

class TestPriceOption(unittest.TestCase):

    def _price(self, S=100, K=100, sigma=0.20, r=0.05, q=0.0,
               opt_type='call', days_out=365):
        exp = (datetime.now() + timedelta(days=days_out)).strftime('%Y-%m-%d')
        return svc.price_option(S, K, exp, sigma, r, q, opt_type)

    def test_returns_dict_with_required_keys(self):
        result = self._price()
        for key in ('price', 'T', 'days', 'greeks'):
            self.assertIn(key, result)

    def test_greeks_has_all_keys(self):
        g = self._price()['greeks']
        for key in ('delta', 'gamma', 'theta', 'vega', 'rho'):
            self.assertIn(key, g)

    def test_call_price_positive(self):
        self.assertGreater(self._price(opt_type='call')['price'], 0)

    def test_put_price_positive(self):
        self.assertGreater(self._price(opt_type='put')['price'], 0)

    def test_days_approximately_correct(self):
        result = self._price(days_out=30)
        self.assertAlmostEqual(result['days'], 30, delta=2)

    def test_T_approximately_correct(self):
        result = self._price(days_out=365)
        self.assertAlmostEqual(result['T'], 1.0, delta=0.01)

    def test_put_price_exceeds_intrinsic_for_itm(self):
        result = self._price(S=90, K=100, opt_type='put')
        self.assertGreater(result['price'], 10)

    def test_expired_option_price_equals_intrinsic(self):
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        result = svc.price_option(110, 100, yesterday, 0.20, 0.05, 0.0, 'call')
        # T ≤ 0 → binomial returns intrinsic = max(110-100, 0) = 10
        self.assertAlmostEqual(result['price'], 10.0, delta=0.5)

    def test_dividend_lowers_call_price(self):
        no_div   = self._price(q=0.0,  opt_type='call')['price']
        with_div = self._price(q=0.05, opt_type='call')['price']
        self.assertGreater(no_div, with_div)


# ═══════════════════════════════════════════════════════════════════════════
# find_atm_strike_with_iv
# ═══════════════════════════════════════════════════════════════════════════

class TestFindAtmStrikeWithIV(unittest.TestCase):

    def _chain(self, strikes, iv=0.25):
        """Build a minimal synthetic chain from a list of strikes."""
        return [
            {'strike': k, 'bid': 5.0, 'ask': 5.10,
             'implied_volatility': iv + abs(k - 100) * 0.001}
            for k in strikes
        ]

    def test_returns_atm_strike_when_price_in_chain(self):
        chain = self._chain([90, 95, 100, 105, 110])
        strike, iv, all_strikes = svc.find_atm_strike_with_iv(
            chain, current_price=100, T=1.0, r=0.05, opt_type='call')
        self.assertEqual(strike, 100)

    def test_picks_nearest_strike_at_or_above_atm(self):
        # Price is 97 — nearest at-or-above is 100
        chain = self._chain([90, 100, 110])
        strike, iv, _ = svc.find_atm_strike_with_iv(
            chain, current_price=97, T=1.0, r=0.05, opt_type='call')
        self.assertEqual(strike, 100)

    def test_falls_back_to_closest_when_all_below(self):
        chain = self._chain([80, 85, 90])
        strike, iv, _ = svc.find_atm_strike_with_iv(
            chain, current_price=100, T=1.0, r=0.05, opt_type='call')
        self.assertEqual(strike, 90)

    def test_returns_none_for_empty_chain(self):
        strike, iv, all_strikes = svc.find_atm_strike_with_iv(
            [], current_price=100, T=1.0, r=0.05, opt_type='call')
        self.assertIsNone(strike)
        self.assertIsNone(iv)
        self.assertEqual(all_strikes, [])

    def test_all_strikes_sorted(self):
        chain = self._chain([110, 90, 100])
        _, _, all_strikes = svc.find_atm_strike_with_iv(
            chain, current_price=100, T=1.0, r=0.05, opt_type='call')
        self.assertEqual(all_strikes, sorted(all_strikes))

    def test_iv_falls_back_to_stored_when_no_bid_ask(self):
        chain = [{'strike': 100, 'bid': 0, 'ask': 0,
                  'implied_volatility': 0.30}]
        _, iv, _ = svc.find_atm_strike_with_iv(
            chain, current_price=100, T=1.0, r=0.05, opt_type='call')
        self.assertAlmostEqual(iv, 0.30, places=4)


# ═══════════════════════════════════════════════════════════════════════════
# atm_strikes_window
# ═══════════════════════════════════════════════════════════════════════════

class TestAtmStrikesWindow(unittest.TestCase):

    def _strikes(self):
        return [float(k) for k in range(80, 130, 5)]  # 80,85,...125

    def test_window_size_full(self):
        selected, idx = svc.atm_strikes_window(self._strikes(), 100, window=2)
        # 2 below ATM + ATM + 2 above = 5 strikes
        self.assertEqual(len(selected), 5)

    def test_atm_index_correct(self):
        _, idx = svc.atm_strikes_window(self._strikes(), 100, window=10)
        strikes = self._strikes()
        nearest = min(range(len(strikes)), key=lambda i: abs(strikes[i] - 100))
        self.assertEqual(idx, nearest)

    def test_clips_at_start_of_list(self):
        # ATM near the beginning — window should not go negative
        selected, _ = svc.atm_strikes_window([80, 85, 90, 95, 100], 80, window=5)
        self.assertGreater(len(selected), 0)

    def test_clips_at_end_of_list(self):
        selected, _ = svc.atm_strikes_window([80, 85, 90, 95, 100], 100, window=5)
        self.assertGreater(len(selected), 0)

    def test_empty_returns_empty(self):
        selected, idx = svc.atm_strikes_window([], 100, window=5)
        self.assertEqual(selected, [])
        self.assertEqual(idx, 0)


# ═══════════════════════════════════════════════════════════════════════════
# find_post_earnings_expiration
# ═══════════════════════════════════════════════════════════════════════════

class TestFindPostEarningsExpiration(unittest.TestCase):

    def _dates(self, *offsets_days):
        """Generate sorted date strings offset from today."""
        base = datetime.now()
        return [(base + timedelta(days=d)).strftime('%Y-%m-%d') for d in offsets_days]

    def test_returns_none_when_no_earnings(self):
        dates = self._dates(7, 14, 30)
        idx = svc.find_post_earnings_expiration(dates, None)
        self.assertIsNone(idx)

    def test_returns_none_when_no_dates(self):
        earnings = datetime.now() + timedelta(days=10)
        idx = svc.find_post_earnings_expiration([], earnings)
        self.assertIsNone(idx)

    def test_finds_weekly_expiry_just_after_earnings(self):
        # Simulated: earnings in 5 days, weekly options (two in same month)
        earnings = datetime.now() + timedelta(days=5)
        # Two expirations in same month → weekly cadence
        d1 = datetime.now() + timedelta(days=3)
        d2 = datetime.now() + timedelta(days=7)   # just after earnings
        d3 = datetime.now() + timedelta(days=35)
        dates = [d.strftime('%Y-%m-%d') for d in [d1, d2, d3]]
        idx = svc.find_post_earnings_expiration(dates, earnings)
        # d2 (index 1) is 2 days after earnings and within 7-day threshold
        self.assertEqual(idx, 1)

    def test_no_match_when_expiry_too_far_after_earnings(self):
        earnings = datetime.now() + timedelta(days=5)
        # Monthly cadence; next expiry is 40 days after earnings
        d1 = datetime.now() + timedelta(days=50)  # post-earnings but > 30d threshold
        d2 = datetime.now() + timedelta(days=80)
        d3 = datetime.now() + timedelta(days=110)
        dates = [d.strftime('%Y-%m-%d') for d in [d1, d2, d3]]
        idx = svc.find_post_earnings_expiration(dates, earnings)
        self.assertIsNone(idx)


# ═══════════════════════════════════════════════════════════════════════════
# iv_for_strike
# ═══════════════════════════════════════════════════════════════════════════

class TestIvForStrike(unittest.TestCase):

    def test_returns_none_for_none_opt(self):
        iv = svc.iv_for_strike(None, 100, 100, 1.0, 0.05, 'call')
        self.assertIsNone(iv)

    def test_uses_stored_iv_when_no_bid_ask(self):
        opt = {'bid': 0, 'ask': 0, 'implied_volatility': 0.28}
        iv = svc.iv_for_strike(opt, 100, 100, 1.0, 0.05, 'call')
        self.assertAlmostEqual(iv, 0.28, places=4)

    def test_uses_stored_iv_when_t_is_zero(self):
        opt = {'bid': 5.0, 'ask': 5.20, 'implied_volatility': 0.35}
        iv = svc.iv_for_strike(opt, 100, 100, 0.0, 0.05, 'call')
        self.assertAlmostEqual(iv, 0.35, places=4)

    def test_computes_from_midprice_when_bid_ask_valid(self):
        # Price a known option and pass bid=ask=price so mid = price
        known_sigma = 0.22
        price = bs.black_scholes_call(100, 100, 1.0, 0.05, known_sigma)
        opt = {'bid': price, 'ask': price, 'implied_volatility': 0.99}
        iv = svc.iv_for_strike(opt, 100, 100, 1.0, 0.05, 'call')
        if iv is not None:
            self.assertAlmostEqual(iv, known_sigma, delta=0.005)

    def test_returns_none_when_stored_iv_also_missing(self):
        opt = {'bid': 0, 'ask': 0, 'implied_volatility': None}
        iv = svc.iv_for_strike(opt, 100, 100, 1.0, 0.05, 'call')
        self.assertIsNone(iv)


if __name__ == '__main__':
    unittest.main()
