"""
Comprehensive tests for option_pricing (Black-Scholes, Binomial, Greeks, IV).

Covers:
  - Closed-form Black-Scholes calls and puts
  - Put-call parity
  - Greeks structure, signs, and inter-relationships
  - Implied-volatility round-trip
  - American binomial tree (early exercise premium, convergence)
  - Monotonicity and boundary conditions
  - Numerical edge cases
"""

import math
import unittest
import numpy as np
import pytest

import option_pricing as bs


# ═══════════════════════════════════════════════════════════════════════════
# Black-Scholes calls
# ═══════════════════════════════════════════════════════════════════════════

class TestBlackScholesCall(unittest.TestCase):

    def _bs_call(self, S=100, K=100, T=1.0, r=0.05, sigma=0.20):
        return bs.black_scholes_call(S, K, T, r, sigma)

    def test_atm_call_reasonable_range(self):
        price = self._bs_call()
        self.assertGreater(price, 5)
        self.assertLess(price, 15)

    def test_itm_call_exceeds_intrinsic(self):
        price = self._bs_call(S=110)
        self.assertGreater(price, 10)   # intrinsic = 10

    def test_otm_call_below_atm(self):
        atm  = self._bs_call(S=100)
        otm  = self._bs_call(S=90)
        self.assertGreater(atm, otm)

    def test_expired_itm_call_equals_intrinsic(self):
        price = self._bs_call(S=110, T=0)
        self.assertEqual(price, 10.0)

    def test_expired_otm_call_is_zero(self):
        price = self._bs_call(S=90, T=0)
        self.assertEqual(price, 0.0)

    def test_call_bounded_above_by_stock_price(self):
        price = self._bs_call(sigma=5.0)   # extreme vol
        self.assertLess(price, 100)        # can never exceed S

    def test_call_non_negative(self):
        for S in [50, 100, 150]:
            for sigma in [0.01, 0.5, 2.0]:
                self.assertGreaterEqual(self._bs_call(S=S, sigma=sigma), 0)

    def test_higher_vol_raises_call_price(self):
        low  = self._bs_call(sigma=0.10)
        high = self._bs_call(sigma=0.40)
        self.assertGreater(high, low)

    def test_higher_rate_raises_call_price(self):
        low  = self._bs_call(r=0.01)
        high = self._bs_call(r=0.10)
        self.assertGreater(high, low)

    def test_longer_maturity_raises_call_price(self):
        short = self._bs_call(T=0.25)
        long_ = self._bs_call(T=2.0)
        self.assertGreater(long_, short)

    def test_returns_float(self):
        price = self._bs_call()
        self.assertIsInstance(price, (float, np.floating))


# ═══════════════════════════════════════════════════════════════════════════
# Black-Scholes puts
# ═══════════════════════════════════════════════════════════════════════════

class TestBlackScholesPut(unittest.TestCase):

    def _bs_put(self, S=100, K=100, T=1.0, r=0.05, sigma=0.20):
        return bs.black_scholes_put(S, K, T, r, sigma)

    def test_atm_put_reasonable_range(self):
        price = self._bs_put()
        self.assertGreater(price, 3)
        self.assertLess(price, 12)

    def test_itm_put_exceeds_intrinsic(self):
        price = self._bs_put(S=90)
        self.assertGreater(price, 10)   # intrinsic = 10

    def test_expired_itm_put_equals_intrinsic(self):
        price = self._bs_put(S=90, T=0)
        self.assertEqual(price, 10.0)

    def test_expired_otm_put_is_zero(self):
        price = self._bs_put(S=110, T=0)
        self.assertEqual(price, 0.0)

    def test_put_non_negative(self):
        for S in [50, 100, 150]:
            for sigma in [0.01, 0.5, 2.0]:
                self.assertGreaterEqual(self._bs_put(S=S, sigma=sigma), 0)

    def test_higher_vol_raises_put_price(self):
        low  = self._bs_put(sigma=0.10)
        high = self._bs_put(sigma=0.40)
        self.assertGreater(high, low)

    def test_higher_rate_lowers_put_price(self):
        low  = self._bs_put(r=0.01)
        high = self._bs_put(r=0.10)
        self.assertGreater(low, high)

    def test_put_bounded_above_by_pv_of_strike(self):
        price = self._bs_put(S=1, K=100, sigma=0.01)   # deep ITM
        pv_k  = 100 * math.exp(-0.05 * 1.0)
        self.assertLessEqual(price, pv_k + 0.01)       # small rounding tolerance


# ═══════════════════════════════════════════════════════════════════════════
# Put-call parity
# ═══════════════════════════════════════════════════════════════════════════

class TestPutCallParity(unittest.TestCase):

    def _check_parity(self, S, K, T, r, sigma):
        c   = bs.black_scholes_call(S, K, T, r, sigma)
        p   = bs.black_scholes_put(S, K, T, r, sigma)
        lhs = c - p
        rhs = S - K * math.exp(-r * T)
        self.assertAlmostEqual(lhs, rhs, places=6,
                               msg=f"PCP failed for S={S} K={K} T={T}")

    def test_atm_parity(self):        self._check_parity(100, 100, 1.0, 0.05, 0.20)
    def test_itm_call_parity(self):   self._check_parity(110, 100, 1.0, 0.05, 0.20)
    def test_otm_call_parity(self):   self._check_parity(90,  100, 1.0, 0.05, 0.20)
    def test_short_term_parity(self): self._check_parity(100, 100, 0.1, 0.05, 0.30)
    def test_long_term_parity(self):  self._check_parity(100, 100, 3.0, 0.05, 0.25)
    def test_zero_rate_parity(self):  self._check_parity(100, 100, 1.0, 0.00, 0.20)
    def test_high_vol_parity(self):   self._check_parity(100, 100, 1.0, 0.05, 1.50)


# ═══════════════════════════════════════════════════════════════════════════
# Greeks
# ═══════════════════════════════════════════════════════════════════════════

class TestGreeks(unittest.TestCase):

    def _greeks(self, opt_type='call', S=100, K=100, T=1.0, r=0.05, sigma=0.20):
        return bs.calculate_greeks(S, K, T, r, sigma, opt_type)

    # ── structure ─────────────────────────────────────────────────────────

    def test_all_keys_present(self):
        g = self._greeks()
        for key in ('delta', 'gamma', 'theta', 'vega', 'rho'):
            self.assertIn(key, g)

    # ── delta ─────────────────────────────────────────────────────────────

    def test_call_delta_in_range(self):
        g = self._greeks('call')
        self.assertGreaterEqual(g['delta'], 0)
        self.assertLessEqual(g['delta'],    1)

    def test_put_delta_in_range(self):
        g = self._greeks('put')
        self.assertGreaterEqual(g['delta'], -1)
        self.assertLessEqual(g['delta'],     0)

    def test_put_call_delta_sum_near_one(self):
        """Call delta - put delta ≈ 1 (both BS, same params)."""
        dc = self._greeks('call')['delta']
        dp = self._greeks('put') ['delta']
        self.assertAlmostEqual(dc - dp, 1.0, places=4)

    def test_deep_itm_call_delta_near_one(self):
        g = self._greeks('call', S=200, K=100)
        self.assertGreater(g['delta'], 0.95)

    def test_deep_otm_call_delta_near_zero(self):
        g = self._greeks('call', S=50, K=100)
        self.assertLess(g['delta'], 0.05)

    def test_atm_call_delta_near_half(self):
        g = self._greeks('call')
        self.assertGreater(g['delta'], 0.45)
        self.assertLess(g['delta'],    0.65)

    # ── gamma ─────────────────────────────────────────────────────────────

    def test_gamma_positive_for_call(self):
        self.assertGreater(self._greeks('call')['gamma'], 0)

    def test_gamma_positive_for_put(self):
        self.assertGreater(self._greeks('put')['gamma'], 0)

    def test_call_put_gamma_equal(self):
        gc = self._greeks('call')['gamma']
        gp = self._greeks('put') ['gamma']
        self.assertAlmostEqual(gc, gp, places=6)

    def test_gamma_peaks_atm(self):
        """ATM gamma > deep-ITM or deep-OTM gamma."""
        atm  = self._greeks('call', S=100)['gamma']
        deep = self._greeks('call', S=200)['gamma']
        self.assertGreater(atm, deep)

    # ── vega ──────────────────────────────────────────────────────────────

    def test_vega_positive(self):
        for t in ('call', 'put'):
            self.assertGreater(self._greeks(t)['vega'], 0)

    def test_call_put_vega_equal(self):
        vc = self._greeks('call')['vega']
        vp = self._greeks('put') ['vega']
        self.assertAlmostEqual(vc, vp, places=6)

    # ── theta ─────────────────────────────────────────────────────────────

    def test_theta_negative_for_call(self):
        self.assertLess(self._greeks('call')['theta'], 0)

    def test_theta_negative_for_put(self):
        # Deep ITM puts can have positive theta, but ATM should be negative
        self.assertLess(self._greeks('put')['theta'], 0)

    # ── rho ───────────────────────────────────────────────────────────────

    def test_call_rho_positive(self):
        self.assertGreater(self._greeks('call')['rho'], 0)

    def test_put_rho_negative(self):
        self.assertLess(self._greeks('put')['rho'], 0)

    # ── numerical delta check (finite difference) ─────────────────────────

    def test_delta_matches_finite_difference(self):
        S, K, T, r, sigma = 100, 100, 1.0, 0.05, 0.20
        h     = 0.01
        dC    = (bs.black_scholes_call(S + h, K, T, r, sigma) -
                 bs.black_scholes_call(S - h, K, T, r, sigma)) / (2 * h)
        delta = bs.calculate_greeks(S, K, T, r, sigma, 'call')['delta']
        self.assertAlmostEqual(delta, dC, places=4)


# ═══════════════════════════════════════════════════════════════════════════
# Implied volatility
# ═══════════════════════════════════════════════════════════════════════════

class TestImpliedVolatility(unittest.TestCase):

    def _roundtrip(self, sigma, opt_type='call', S=100, K=100, T=1.0, r=0.05):
        pricer = bs.black_scholes_call if opt_type == 'call' else bs.black_scholes_put
        price  = pricer(S, K, T, r, sigma)
        iv     = bs.implied_volatility(price, S, K, T, r, opt_type)
        return iv

    def test_call_roundtrip_atm(self):
        iv = self._roundtrip(0.25)
        self.assertIsNotNone(iv)
        self.assertAlmostEqual(iv, 0.25, places=4)

    def test_put_roundtrip_atm(self):
        iv = self._roundtrip(0.30, 'put')
        self.assertIsNotNone(iv)
        self.assertAlmostEqual(iv, 0.30, places=4)

    def test_call_roundtrip_itm(self):
        iv = self._roundtrip(0.20, S=110)
        self.assertIsNotNone(iv)
        self.assertAlmostEqual(iv, 0.20, places=3)

    def test_call_roundtrip_otm(self):
        iv = self._roundtrip(0.20, S=90)
        self.assertIsNotNone(iv)
        self.assertAlmostEqual(iv, 0.20, places=3)

    def test_high_vol_roundtrip(self):
        iv = self._roundtrip(1.50)
        if iv is not None:
            self.assertAlmostEqual(iv, 1.50, delta=0.05)

    def test_expired_option_returns_none(self):
        iv = bs.implied_volatility(10, 100, 100, 0, 0.05, 'call')
        self.assertIsNone(iv)

    def test_zero_price_returns_none_or_very_low(self):
        iv = bs.implied_volatility(0, 100, 110, 1.0, 0.05, 'call')
        # Deep OTM with zero price → None or a very small vol (solver finds floor)
        if iv is not None:
            self.assertLess(iv, 0.05)


# ═══════════════════════════════════════════════════════════════════════════
# American binomial tree
# ═══════════════════════════════════════════════════════════════════════════

class TestAmericanBinomial(unittest.TestCase):

    def _amer(self, opt_type='call', S=100, K=100, T=1.0, r=0.05, sigma=0.20,
              q=0.0, steps=100):
        return bs.american_option_binomial(S, K, T, r, sigma, q=q,
                                           option_type=opt_type, steps=steps)

    # ── basic sanity ───────────────────────────────────────────────────────

    def test_call_positive(self):
        self.assertGreater(self._amer('call'), 0)

    def test_put_positive(self):
        self.assertGreater(self._amer('put'), 0)

    def test_call_expired_equals_intrinsic(self):
        price = self._amer('call', S=110, T=0)
        self.assertAlmostEqual(price, 10.0, places=4)

    def test_put_expired_equals_intrinsic(self):
        price = self._amer('put', S=90, T=0)
        self.assertAlmostEqual(price, 10.0, places=4)

    def test_call_no_dividend_matches_bs(self):
        """American call without dividends ≈ Black-Scholes call."""
        amer = self._amer('call', steps=200)
        eur  = bs.black_scholes_call(100, 100, 1.0, 0.05, 0.20)
        self.assertAlmostEqual(amer, eur, delta=0.40)

    # ── early-exercise premium ─────────────────────────────────────────────

    def test_american_put_ge_european_put(self):
        """American put must be worth at least as much as European put."""
        amer = self._amer('put', S=80, steps=200)
        eur  = bs.black_scholes_put(80, 100, 1.0, 0.05, 0.20)
        self.assertGreaterEqual(amer, eur - 0.01)

    def test_deep_itm_put_has_early_exercise_premium(self):
        amer = self._amer('put', S=60, steps=200)
        eur  = bs.black_scholes_put(60, 100, 1.0, 0.05, 0.20)
        self.assertGreater(amer, eur)

    def test_american_call_with_dividend_lower_than_no_dividend(self):
        # Dividends reduce the stock value so call value falls.
        # American early exercise may compensate partially, but the call is still
        # cheaper with a high dividend than without any dividend.
        amer_no_div  = self._amer('call', q=0.0,  steps=200)
        amer_with_div = self._amer('call', q=0.05, steps=200)
        self.assertGreater(amer_no_div, amer_with_div)

    # ── monotonicity ──────────────────────────────────────────────────────

    def test_call_increasing_in_S(self):
        prices = [self._amer('call', S=s) for s in [80, 90, 100, 110, 120]]
        self.assertEqual(prices, sorted(prices))

    def test_put_decreasing_in_S(self):
        prices = [self._amer('put', S=s) for s in [80, 90, 100, 110, 120]]
        self.assertEqual(prices, sorted(prices, reverse=True))

    def test_both_increasing_in_vol(self):
        for opt in ('call', 'put'):
            low  = self._amer(opt, sigma=0.10)
            high = self._amer(opt, sigma=0.50)
            self.assertGreater(high, low, msg=f"{opt} not increasing in vol")

    def test_call_decreasing_in_K(self):
        prices = [self._amer('call', K=k) for k in [80, 90, 100, 110, 120]]
        self.assertEqual(prices, sorted(prices, reverse=True))

    def test_put_increasing_in_K(self):
        prices = [self._amer('put', K=k) for k in [80, 90, 100, 110, 120]]
        self.assertEqual(prices, sorted(prices))

    # ── convergence ───────────────────────────────────────────────────────

    @pytest.mark.slow
    def test_convergence_with_more_steps(self):
        """Prices with 100 and 400 steps should differ by less than 0.05."""
        p100 = self._amer('put', steps=100)
        p400 = self._amer('put', steps=400)
        self.assertAlmostEqual(p100, p400, delta=0.05)

    # ── high-vol long-dated (CRDO-style) ─────────────────────────────────

    def test_high_vol_long_dated_put(self):
        """Smoke test for a ~100% vol, 1.5yr OTM put (like CRDO Oct 2027 $190)."""
        price = self._amer('put', S=229, K=190, T=1.37, r=0.043,
                           sigma=0.998, q=0.0, steps=200)
        self.assertGreater(price, 0)
        self.assertLess(price, 229)    # cannot exceed stock price
        self.assertGreater(price, 10)  # significant time value expected

    # ── boundary / edge cases ─────────────────────────────────────────────

    def test_very_short_expiry(self):
        price = self._amer('call', T=1/365)
        self.assertGreater(price, 0)
        self.assertLess(price, 5)

    def test_very_high_vol(self):
        price = self._amer('call', sigma=3.0)
        self.assertGreater(price, 0)

    def test_zero_risk_free_rate(self):
        price = self._amer('call', r=0.0)
        self.assertGreater(price, 0)

    def test_dividend_lowers_call_price(self):
        no_div  = self._amer('call', q=0.0)
        with_div = self._amer('call', q=0.05)
        self.assertGreater(no_div, with_div)


if __name__ == '__main__':
    unittest.main()
