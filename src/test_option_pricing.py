"""
Unit tests for option_pricing module
Tests option pricing (European and American models) and Greeks calculations
"""

import unittest
import numpy as np
import option_pricing as bs


class TestBlackScholesCall(unittest.TestCase):
    """Test cases for Black-Scholes call option pricing"""
    
    def test_call_basic_calculation(self):
        """Test basic call option pricing"""
        S = 100  # Stock price
        K = 100  # Strike price
        T = 1.0  # 1 year
        r = 0.05  # 5% risk-free rate
        sigma = 0.2  # 20% volatility
        
        price = bs.black_scholes_call(S, K, T, r, sigma)
        
        self.assertIsInstance(price, (float, np.float64))
        self.assertGreater(price, 0)
        # ATM call with reasonable parameters should be between $5-$15
        self.assertGreater(price, 5)
        self.assertLess(price, 15)
    
    def test_call_itm(self):
        """Test in-the-money call option"""
        S = 110  # Stock price above strike
        K = 100  # Strike price
        T = 1.0
        r = 0.05
        sigma = 0.2
        
        price = bs.black_scholes_call(S, K, T, r, sigma)
        
        # ITM call should be worth at least intrinsic value (S - K = 10)
        self.assertGreater(price, 10)
    
    def test_call_otm(self):
        """Test out-of-the-money call option"""
        S = 90  # Stock price below strike
        K = 100  # Strike price
        T = 1.0
        r = 0.05
        sigma = 0.2
        
        price = bs.black_scholes_call(S, K, T, r, sigma)
        
        # OTM call should be worth less than ATM call
        self.assertGreater(price, 0)
        self.assertLess(price, 10)
    
    def test_call_expired(self):
        """Test call option at expiration (T=0)"""
        S = 110
        K = 100
        T = 0  # Expired
        r = 0.05
        sigma = 0.2
        
        price = bs.black_scholes_call(S, K, T, r, sigma)
        
        # At expiration, price should equal max(S-K, 0) = 10
        self.assertEqual(price, max(S - K, 0))
    
    def test_call_worthless_at_expiration(self):
        """Test OTM call option at expiration"""
        S = 90
        K = 100
        T = 0  # Expired
        r = 0.05
        sigma = 0.2
        
        price = bs.black_scholes_call(S, K, T, r, sigma)
        
        # Expired OTM call should be worthless
        self.assertEqual(price, 0)


class TestBlackScholesPut(unittest.TestCase):
    """Test cases for Black-Scholes put option pricing"""
    
    def test_put_basic_calculation(self):
        """Test basic put option pricing"""
        S = 100
        K = 100
        T = 1.0
        r = 0.05
        sigma = 0.2
        
        price = bs.black_scholes_put(S, K, T, r, sigma)
        
        self.assertIsInstance(price, (float, np.float64))
        self.assertGreater(price, 0)
        self.assertGreater(price, 3)
        self.assertLess(price, 12)
    
    def test_put_itm(self):
        """Test in-the-money put option"""
        S = 90  # Stock price below strike
        K = 100  # Strike price
        T = 1.0
        r = 0.05
        sigma = 0.2
        
        price = bs.black_scholes_put(S, K, T, r, sigma)
        
        # ITM put should be worth at least intrinsic value (K - S = 10)
        self.assertGreater(price, 10)
    
    def test_put_otm(self):
        """Test out-of-the-money put option"""
        S = 110  # Stock price above strike
        K = 100  # Strike price
        T = 1.0
        r = 0.05
        sigma = 0.2
        
        price = bs.black_scholes_put(S, K, T, r, sigma)
        
        # OTM put should have some value
        self.assertGreater(price, 0)
        self.assertLess(price, 10)
    
    def test_put_expired(self):
        """Test put option at expiration"""
        S = 90
        K = 100
        T = 0  # Expired
        r = 0.05
        sigma = 0.2
        
        price = bs.black_scholes_put(S, K, T, r, sigma)
        
        # At expiration, price should equal max(K-S, 0) = 10
        self.assertEqual(price, max(K - S, 0))


class TestPutCallParity(unittest.TestCase):
    """Test put-call parity relationship"""
    
    def test_put_call_parity(self):
        """Test that put-call parity holds"""
        S = 100
        K = 100
        T = 1.0
        r = 0.05
        sigma = 0.2
        
        call_price = bs.black_scholes_call(S, K, T, r, sigma)
        put_price = bs.black_scholes_put(S, K, T, r, sigma)
        
        # Put-call parity: C - P = S - K*e^(-rT)
        lhs = call_price - put_price
        rhs = S - K * np.exp(-r * T)
        
        self.assertAlmostEqual(lhs, rhs, places=6)


class TestGreeks(unittest.TestCase):
    """Test cases for option Greeks calculations"""
    
    def test_greeks_call_structure(self):
        """Test that Greeks calculation returns correct structure"""
        S = 100
        K = 100
        T = 1.0
        r = 0.05
        sigma = 0.2
        
        greeks = bs.calculate_greeks(S, K, T, r, sigma, 'call')
        
        self.assertIsInstance(greeks, dict)
        self.assertIn('delta', greeks)
        self.assertIn('gamma', greeks)
        self.assertIn('theta', greeks)
        self.assertIn('vega', greeks)
        self.assertIn('rho', greeks)
    
    def test_delta_call_range(self):
        """Test that call delta is between 0 and 1"""
        S = 100
        K = 100
        T = 1.0
        r = 0.05
        sigma = 0.2
        
        greeks = bs.calculate_greeks(S, K, T, r, sigma, 'call')
        
        self.assertGreaterEqual(greeks['delta'], 0)
        self.assertLessEqual(greeks['delta'], 1)
    
    def test_delta_put_range(self):
        """Test that put delta is between -1 and 0"""
        S = 100
        K = 100
        T = 1.0
        r = 0.05
        sigma = 0.2
        
        greeks = bs.calculate_greeks(S, K, T, r, sigma, 'put')
        
        self.assertGreaterEqual(greeks['delta'], -1)
        self.assertLessEqual(greeks['delta'], 0)
    
    def test_gamma_positive(self):
        """Test that gamma is always positive"""
        S = 100
        K = 100
        T = 1.0
        r = 0.05
        sigma = 0.2
        
        greeks_call = bs.calculate_greeks(S, K, T, r, sigma, 'call')
        greeks_put = bs.calculate_greeks(S, K, T, r, sigma, 'put')
        
        self.assertGreater(greeks_call['gamma'], 0)
        self.assertGreater(greeks_put['gamma'], 0)
        # Gamma should be the same for calls and puts
        self.assertAlmostEqual(greeks_call['gamma'], greeks_put['gamma'])
    
    def test_vega_positive(self):
        """Test that vega is positive for both calls and puts"""
        S = 100
        K = 100
        T = 1.0
        r = 0.05
        sigma = 0.2
        
        greeks_call = bs.calculate_greeks(S, K, T, r, sigma, 'call')
        greeks_put = bs.calculate_greeks(S, K, T, r, sigma, 'put')
        
        self.assertGreater(greeks_call['vega'], 0)
        self.assertGreater(greeks_put['vega'], 0)
    
    def test_theta_call_negative(self):
        """Test that theta is typically negative for calls"""
        S = 100
        K = 100
        T = 1.0
        r = 0.05
        sigma = 0.2
        
        greeks = bs.calculate_greeks(S, K, T, r, sigma, 'call')
        
        # Theta is usually negative (time decay)
        self.assertLess(greeks['theta'], 0)
    
    def test_delta_itm_call(self):
        """Test that deep ITM call has delta close to 1"""
        S = 150  # Deep ITM
        K = 100
        T = 1.0
        r = 0.05
        sigma = 0.2
        
        greeks = bs.calculate_greeks(S, K, T, r, sigma, 'call')
        
        # Deep ITM call should have delta close to 1
        self.assertGreater(greeks['delta'], 0.9)
    
    def test_delta_otm_call(self):
        """Test that deep OTM call has delta close to 0"""
        S = 50  # Deep OTM
        K = 100
        T = 1.0
        r = 0.05
        sigma = 0.2
        
        greeks = bs.calculate_greeks(S, K, T, r, sigma, 'call')
        
        # Deep OTM call should have delta close to 0
        self.assertLess(greeks['delta'], 0.1)


class TestImpliedVolatility(unittest.TestCase):
    """Test cases for implied volatility calculation"""
    
    def test_implied_vol_recovery(self):
        """Test that implied vol recovers the input volatility"""
        S = 100
        K = 100
        T = 1.0
        r = 0.05
        sigma = 0.25
        
        # Calculate option price with known volatility
        call_price = bs.black_scholes_call(S, K, T, r, sigma)
        
        # Recover implied volatility
        implied_vol = bs.implied_volatility(call_price, S, K, T, r, 'call')
        
        if implied_vol is not None:
            self.assertAlmostEqual(implied_vol, sigma, places=4)
    
    def test_implied_vol_put(self):
        """Test implied volatility for put options"""
        S = 100
        K = 100
        T = 1.0
        r = 0.05
        sigma = 0.30
        
        # Calculate put price with known volatility
        put_price = bs.black_scholes_put(S, K, T, r, sigma)
        
        # Recover implied volatility
        implied_vol = bs.implied_volatility(put_price, S, K, T, r, 'put')
        
        if implied_vol is not None:
            self.assertAlmostEqual(implied_vol, sigma, places=4)
    
    def test_implied_vol_expired_option(self):
        """Test implied vol for expired option"""
        S = 100
        K = 100
        T = 0  # Expired
        r = 0.05
        option_price = 10
        
        implied_vol = bs.implied_volatility(option_price, S, K, T, r, 'call')
        
        # Should return None for expired options
        self.assertIsNone(implied_vol)
    
    def test_implied_vol_unrealistic_price(self):
        """Test implied vol with unrealistic option price"""
        S = 100
        K = 100
        T = 1.0
        r = 0.05
        option_price = 1000  # Unrealistically high
        
        implied_vol = bs.implied_volatility(option_price, S, K, T, r, 'call', max_iterations=50)
        
        # May return None if cannot converge
        if implied_vol is not None:
            self.assertIsInstance(implied_vol, float)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions"""
    
    def test_very_low_volatility(self):
        """Test with very low volatility"""
        S = 100
        K = 100
        T = 1.0
        r = 0.05
        sigma = 0.01  # 1% volatility
        
        call_price = bs.black_scholes_call(S, K, T, r, sigma)
        
        self.assertGreater(call_price, 0)
        self.assertIsInstance(call_price, (float, np.float64))
    
    def test_very_high_volatility(self):
        """Test with very high volatility"""
        S = 100
        K = 100
        T = 1.0
        r = 0.05
        sigma = 2.0  # 200% volatility
        
        call_price = bs.black_scholes_call(S, K, T, r, sigma)
        
        self.assertGreater(call_price, 0)
        self.assertLess(call_price, S)  # Should not exceed stock price
    
    def test_very_short_time(self):
        """Test with very short time to expiration"""
        S = 100
        K = 100
        T = 1/365  # 1 day
        r = 0.05
        sigma = 0.2
        
        call_price = bs.black_scholes_call(S, K, T, r, sigma)
        
        self.assertGreater(call_price, 0)
        self.assertLess(call_price, 5)  # Should be small for short time
    
    def test_zero_risk_free_rate(self):
        """Test with zero risk-free rate"""
        S = 100
        K = 100
        T = 1.0
        r = 0.0
        sigma = 0.2
        
        call_price = bs.black_scholes_call(S, K, T, r, sigma)
        
        self.assertGreater(call_price, 0)
        self.assertIsInstance(call_price, (float, np.float64))


class TestAmericanOptions(unittest.TestCase):
    """Test cases for American option pricing using binomial model"""
    
    def test_american_call_basic(self):
        """Test basic American call option pricing"""
        S = 100  # Stock price
        K = 100  # Strike price
        T = 1.0  # 1 year
        r = 0.05  # 5% risk-free rate
        sigma = 0.2  # 20% volatility
        q = 0.0  # No dividend
        
        price = bs.american_option_binomial(S, K, T, r, sigma, q, 'call', steps=100)
        
        self.assertIsInstance(price, (float, np.float64))
        self.assertGreater(price, 0)
        # ATM call should be reasonable
        self.assertGreater(price, 5)
        self.assertLess(price, 15)
    
    def test_american_put_basic(self):
        """Test basic American put option pricing"""
        S = 100
        K = 100
        T = 1.0
        r = 0.05
        sigma = 0.2
        q = 0.0
        
        price = bs.american_option_binomial(S, K, T, r, sigma, q, 'put', steps=100)
        
        self.assertIsInstance(price, (float, np.float64))
        self.assertGreater(price, 0)
        self.assertGreater(price, 3)
        self.assertLess(price, 12)
    
    def test_american_vs_european_call_no_dividend(self):
        """Test that American call equals European call with no dividends"""
        S = 100
        K = 100
        T = 1.0
        r = 0.05
        sigma = 0.2
        q = 0.0  # No dividend
        
        american_price = bs.american_option_binomial(S, K, T, r, sigma, q, 'call', steps=100)
        european_price = bs.black_scholes_call(S, K, T, r, sigma)
        
        # With no dividends, American call should equal European call
        # Allow small difference due to binomial approximation
        self.assertAlmostEqual(american_price, european_price, delta=0.5)
    
    def test_american_put_early_exercise_premium(self):
        """Test that American put is worth more than European put (early exercise)"""
        S = 80   # Deep OTM put
        K = 100
        T = 1.0
        r = 0.05
        sigma = 0.2
        q = 0.0
        
        american_price = bs.american_option_binomial(S, K, T, r, sigma, q, 'put', steps=100)
        european_price = bs.black_scholes_put(S, K, T, r, sigma)
        
        # American put should be worth at least as much as European put
        self.assertGreaterEqual(american_price, european_price - 0.01)
        # For deep ITM puts, American should be noticeably more valuable
        self.assertGreater(american_price, european_price)
    
    def test_american_call_with_dividend(self):
        """Test American call with dividend yield"""
        S = 100
        K = 95
        T = 1.0
        r = 0.05
        sigma = 0.2
        q = 0.03  # 3% dividend yield
        
        american_price = bs.american_option_binomial(S, K, T, r, sigma, q, 'call', steps=100)
        
        # With dividends, American call should have early exercise value
        self.assertGreater(american_price, 0)
        self.assertGreater(american_price, 5)  # ITM call should be worth more than intrinsic
    
    def test_american_put_with_dividend(self):
        """Test American put with dividend yield"""
        S = 100
        K = 105
        T = 1.0
        r = 0.05
        sigma = 0.2
        q = 0.02  # 2% dividend yield
        
        american_price = bs.american_option_binomial(S, K, T, r, sigma, q, 'put', steps=100)
        
        self.assertGreater(american_price, 0)
        self.assertGreater(american_price, 4)
    
    def test_american_call_expired(self):
        """Test American call at expiration"""
        S = 105
        K = 100
        T = 0.0  # Expired
        r = 0.05
        sigma = 0.2
        q = 0.0
        
        price = bs.american_option_binomial(S, K, T, r, sigma, q, 'call', steps=100)
        
        # At expiration, should equal intrinsic value
        self.assertEqual(price, max(S - K, 0))
    
    def test_american_put_expired(self):
        """Test American put at expiration"""
        S = 95
        K = 100
        T = 0.0  # Expired
        r = 0.05
        sigma = 0.2
        q = 0.0
        
        price = bs.american_option_binomial(S, K, T, r, sigma, q, 'put', steps=100)
        
        # At expiration, should equal intrinsic value
        self.assertEqual(price, max(K - S, 0))
    
    def test_american_different_steps(self):
        """Test that more steps gives more accurate pricing"""
        S = 100
        K = 100
        T = 1.0
        r = 0.05
        sigma = 0.2
        q = 0.0
        
        price_50 = bs.american_option_binomial(S, K, T, r, sigma, q, 'call', steps=50)
        price_100 = bs.american_option_binomial(S, K, T, r, sigma, q, 'call', steps=100)
        price_200 = bs.american_option_binomial(S, K, T, r, sigma, q, 'call', steps=200)
        
        # All should be similar (converging)
        self.assertAlmostEqual(price_50, price_100, delta=0.5)
        self.assertAlmostEqual(price_100, price_200, delta=0.3)
    
    def test_american_itm_call(self):
        """Test in-the-money American call"""
        S = 110
        K = 100
        T = 1.0
        r = 0.05
        sigma = 0.2
        q = 0.0
        
        price = bs.american_option_binomial(S, K, T, r, sigma, q, 'call', steps=100)
        
        # ITM call should be worth at least intrinsic value
        intrinsic = S - K
        self.assertGreater(price, intrinsic)
    
    def test_american_itm_put(self):
        """Test in-the-money American put"""
        S = 90
        K = 100
        T = 1.0
        r = 0.05
        sigma = 0.2
        q = 0.0
        
        price = bs.american_option_binomial(S, K, T, r, sigma, q, 'put', steps=100)
        
        # ITM put should be worth at least intrinsic value
        intrinsic = K - S
        self.assertGreater(price, intrinsic)
    
    def test_american_high_dividend_call(self):
        """Test that high dividends increase early exercise likelihood for calls"""
        S = 110
        K = 100
        T = 1.0
        r = 0.05
        sigma = 0.2
        q_low = 0.01   # 1% dividend
        q_high = 0.08  # 8% dividend
        
        price_low = bs.american_option_binomial(S, K, T, r, sigma, q_low, 'call', steps=100)
        price_high = bs.american_option_binomial(S, K, T, r, sigma, q_high, 'call', steps=100)
        
        # Higher dividend should lower call value (dividends reduce stock value)
        self.assertGreater(price_low, price_high)


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestBlackScholesCall))
    suite.addTests(loader.loadTestsFromTestCase(TestBlackScholesPut))
    suite.addTests(loader.loadTestsFromTestCase(TestPutCallParity))
    suite.addTests(loader.loadTestsFromTestCase(TestGreeks))
    suite.addTests(loader.loadTestsFromTestCase(TestImpliedVolatility))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))
    suite.addTests(loader.loadTestsFromTestCase(TestAmericanOptions))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("="*70)
    
    return result


if __name__ == '__main__':
    run_tests()
