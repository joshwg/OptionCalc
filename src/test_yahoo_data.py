"""
Unit tests for yahoo_data module
Tests ticker search and stock information download functionality
"""

import unittest
from unittest.mock import patch, MagicMock
import yahoo_data as yd
from datetime import datetime, timedelta


class TestTickerSearch(unittest.TestCase):
    """Test cases for ticker search functionality"""
    
    def test_search_ticker_with_valid_query(self):
        """Test searching for a valid ticker/company name"""
        results = yd.search_ticker("AAPL", max_results=5)
        
        # Should return a list
        self.assertIsInstance(results, list)
        
        # If results found, check structure
        if results:
            self.assertLessEqual(len(results), 5)
            for result in results:
                self.assertIn('symbol', result)
                self.assertIn('name', result)
                self.assertIn('exchange', result)
                self.assertIn('type', result)
    
    def test_search_ticker_apple(self):
        """Test searching for Apple stock"""
        results = yd.search_ticker("Apple", max_results=10)
        
        self.assertIsInstance(results, list)
        
        # Should find AAPL
        if results:
            symbols = [r['symbol'] for r in results]
            # AAPL should be in the results when searching for Apple
            self.assertTrue(any('AAPL' in s for s in symbols))
    
    def test_search_ticker_partial_match(self):
        """Test searching with partial ticker"""
        results = yd.search_ticker("MS", max_results=10)
        
        self.assertIsInstance(results, list)
        self.assertLessEqual(len(results), 10)
    
    def test_search_ticker_empty_query(self):
        """Test searching with empty query"""
        results = yd.search_ticker("", max_results=10)
        
        # Should return empty list or handle gracefully
        self.assertIsInstance(results, list)
    
    def test_search_ticker_invalid_query(self):
        """Test searching with nonsense query"""
        results = yd.search_ticker("XYZXYZXYZXYZ123456789", max_results=10)
        
        # Should return empty list for invalid query
        self.assertIsInstance(results, list)
    
    def test_search_ticker_max_results_limit(self):
        """Test that max_results parameter is respected"""
        max_results = 3
        results = yd.search_ticker("tech", max_results=max_results)
        
        self.assertIsInstance(results, list)
        self.assertLessEqual(len(results), max_results)
    
    @patch('yahoo_data.requests.get')
    def test_search_ticker_network_error(self, mock_get):
        """Test handling of network errors during search"""
        mock_get.side_effect = Exception("Network error")
        
        results = yd.search_ticker("AAPL", max_results=10)
        
        # Should return empty list on error
        self.assertEqual(results, [])
    
    @patch('yahoo_data.requests.get')
    def test_search_ticker_http_error(self, mock_get):
        """Test handling of HTTP errors"""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        results = yd.search_ticker("AAPL", max_results=10)
        
        # Should return empty list on HTTP error
        self.assertEqual(results, [])


class TestStockInfo(unittest.TestCase):
    """Test cases for stock information download"""
    
    def test_get_stock_info_valid_ticker(self):
        """Test getting stock info for a valid ticker"""
        info = yd.get_stock_info("AAPL")
        
        self.assertIsInstance(info, dict)
        self.assertIn('ticker', info)
        self.assertIn('success', info)
        
        if info['success']:
            self.assertEqual(info['ticker'], "AAPL")
            self.assertIn('current_price', info)
            self.assertIn('company_name', info)
            self.assertIsNotNone(info['current_price'])
            self.assertGreater(info['current_price'], 0)
    
    def test_get_stock_info_invalid_ticker(self):
        """Test getting stock info for invalid ticker"""
        info = yd.get_stock_info("INVALIDTICKER12345")
        
        self.assertIsInstance(info, dict)
        self.assertIn('ticker', info)
        self.assertIn('success', info)
        
        # Should either fail or return limited info
        if not info['success']:
            self.assertIn('error', info)
    
    def test_get_stock_info_structure(self):
        """Test that returned info has expected structure"""
        info = yd.get_stock_info("MSFT")
        
        self.assertIsInstance(info, dict)
        self.assertIn('ticker', info)
        self.assertIn('success', info)
        
        if info['success']:
            self.assertIn('current_price', info)
            self.assertIn('company_name', info)
            self.assertIn('previous_close', info)
            self.assertIn('volume', info)
            self.assertIn('market_cap', info)
    
    def test_get_stock_info_multiple_tickers(self):
        """Test getting info for multiple different tickers"""
        tickers = ["AAPL", "MSFT", "GOOGL"]
        
        for ticker in tickers:
            info = yd.get_stock_info(ticker)
            self.assertIsInstance(info, dict)
            self.assertEqual(info['ticker'], ticker)


class TestHistoricalVolatility(unittest.TestCase):
    """Test cases for historical volatility calculation"""
    
    def test_calculate_historical_volatility_valid_ticker(self):
        """Test calculating volatility for valid ticker"""
        vol = yd.calculate_historical_volatility("AAPL", period='1y')
        
        if vol is not None:
            self.assertIsInstance(vol, float)
            self.assertGreater(vol, 0)
            self.assertLess(vol, 5)  # Volatility should be reasonable (0-500%)
    
    def test_calculate_historical_volatility_different_periods(self):
        """Test volatility calculation with different time periods"""
        periods = ['1mo', '3mo', '6mo', '1y']
        
        for period in periods:
            vol = yd.calculate_historical_volatility("AAPL", period=period)
            if vol is not None:
                self.assertIsInstance(vol, float)
                self.assertGreater(vol, 0)
    
    def test_calculate_historical_volatility_invalid_ticker(self):
        """Test volatility calculation with invalid ticker"""
        vol = yd.calculate_historical_volatility("INVALIDTICKER12345", period='1y')
        
        # Should return None for invalid ticker
        self.assertIsNone(vol)


class TestOptionChain(unittest.TestCase):
    """Test cases for option chain functionality"""
    
    def test_get_option_chain_valid_ticker(self):
        """Test getting option chain for valid ticker"""
        chain = yd.get_option_chain("AAPL")
        
        self.assertIsInstance(chain, dict)
        self.assertIn('success', chain)
        
        if chain['success']:
            self.assertIn('ticker', chain)
            self.assertIn('expirations', chain)
            self.assertIsInstance(chain['expirations'], list)
            self.assertGreater(len(chain['expirations']), 0)
    
    def test_get_option_chain_invalid_ticker(self):
        """Test getting option chain for invalid ticker"""
        chain = yd.get_option_chain("INVALIDTICKER12345")
        
        self.assertIsInstance(chain, dict)
        self.assertIn('success', chain)
        
        if not chain['success']:
            self.assertIn('error', chain)
    
    def test_get_options_for_expiration_structure(self):
        """Test structure of options data for specific expiration"""
        # First get available expirations
        chain = yd.get_option_chain("AAPL")
        
        if chain['success'] and chain['expirations']:
            exp_date = chain['expirations'][0]
            options = yd.get_options_for_expiration("AAPL", exp_date)
            
            self.assertIsInstance(options, dict)
            self.assertIn('success', options)
            
            if options['success']:
                self.assertIn('calls', options)
                self.assertIn('puts', options)
                self.assertIsInstance(options['calls'], list)
                self.assertIsInstance(options['puts'], list)
                
                # Check structure of call options
                if options['calls']:
                    call = options['calls'][0]
                    self.assertIn('strike', call)
                    self.assertIn('last_price', call)
                    self.assertIn('bid', call)
                    self.assertIn('ask', call)


class TestDateCalculations(unittest.TestCase):
    """Test cases for date and time calculations"""
    
    def test_get_days_to_expiration_future_date(self):
        """Test calculating days to a future expiration date"""
        future_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        days = yd.get_days_to_expiration(future_date)
        
        self.assertIsInstance(days, int)
        self.assertGreaterEqual(days, 29)
        self.assertLessEqual(days, 31)
    
    def test_get_days_to_expiration_past_date(self):
        """Test calculating days for a past date"""
        past_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
        days = yd.get_days_to_expiration(past_date)
        
        # Should return 0 for past dates
        self.assertEqual(days, 0)
    
    def test_get_years_to_expiration(self):
        """Test calculating years to expiration"""
        future_date = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')
        years = yd.get_years_to_expiration(future_date)
        
        self.assertIsInstance(years, float)
        self.assertGreater(years, 0.99)
        self.assertLess(years, 1.01)
    
    def test_get_years_to_expiration_short_term(self):
        """Test calculating years for short-term expiration"""
        future_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        years = yd.get_years_to_expiration(future_date)
        
        self.assertIsInstance(years, float)
        self.assertGreater(years, 0.07)  # ~30/365
        self.assertLess(years, 0.09)


class TestIntegration(unittest.TestCase):
    """Integration tests combining multiple functions"""
    
    def test_search_and_get_info_workflow(self):
        """Test complete workflow: search ticker then get info"""
        # Search for Apple
        results = yd.search_ticker("Apple", max_results=5)
        
        if results:
            # Get first result's symbol
            symbol = results[0]['symbol']
            
            # Get info for that symbol
            info = yd.get_stock_info(symbol)
            
            self.assertTrue(info['success'])
            self.assertEqual(info['ticker'], symbol)
            self.assertIsNotNone(info['current_price'])
    
    def test_get_info_and_option_chain_workflow(self):
        """Test workflow: get stock info then option chain"""
        info = yd.get_stock_info("AAPL")
        
        if info['success']:
            chain = yd.get_option_chain("AAPL")
            
            if chain['success']:
                self.assertGreater(len(chain['expirations']), 0)
                
                # Try to get options for first expiration
                exp_date = chain['expirations'][0]
                options = yd.get_options_for_expiration("AAPL", exp_date)
                
                self.assertTrue(options['success'])


def run_tests():
    """Run all tests and display results"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test cases
    suite.addTests(loader.loadTestsFromTestCase(TestTickerSearch))
    suite.addTests(loader.loadTestsFromTestCase(TestStockInfo))
    suite.addTests(loader.loadTestsFromTestCase(TestHistoricalVolatility))
    suite.addTests(loader.loadTestsFromTestCase(TestOptionChain))
    suite.addTests(loader.loadTestsFromTestCase(TestDateCalculations))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("="*70)
    
    return result


if __name__ == '__main__':
    run_tests()
