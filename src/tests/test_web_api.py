"""
Tests for the Flask web API endpoints (main_web.py).

Uses Flask's built-in test client with a pre-authenticated session.
External network calls (yahoo_data, option_service) are mocked so these
tests run offline and deterministically.
"""

import json
import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock


# conftest.py already sets OPTION_PWD and adds src/ to sys.path
from main_web import app


def _auth_client():
    """Return a test client with an active session."""
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['authenticated'] = True
        sess['last_activity'] = datetime.now().isoformat()
    return client


# ═══════════════════════════════════════════════════════════════════════════
# /api/config  GET / POST
# ═══════════════════════════════════════════════════════════════════════════

class TestConfigEndpoint(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        self.client = _auth_client()

    def test_get_config_returns_200(self):
        resp = self.client.get('/api/config')
        self.assertEqual(resp.status_code, 200)

    def test_get_config_contains_risk_free_rate(self):
        resp = self.client.get('/api/config')
        data = resp.get_json()
        self.assertIn('risk_free_rate', data)

    def test_post_config_valid(self):
        resp = self.client.post('/api/config',
                                json={'risk_free_rate': 0.042},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json().get('ok'))

    def test_post_config_invalid_value_returns_400(self):
        resp = self.client.post('/api/config',
                                json={'risk_free_rate': 'not-a-number'},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    def test_post_config_missing_key_returns_400(self):
        resp = self.client.post('/api/config',
                                json={},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 400)


# ═══════════════════════════════════════════════════════════════════════════
# /api/calculate  (pure math — no mocking needed)
# ═══════════════════════════════════════════════════════════════════════════

class TestCalculateEndpoint(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        self.client = _auth_client()

    def _calc(self, payload):
        return self.client.post('/api/calculate',
                                json=payload,
                                content_type='application/json')

    def _valid_payload(self, **overrides):
        base = {
            'S': 100.0, 'K': 100.0,
            'expiration': '2027-01-15',
            'sigma': 0.25, 'r': 0.045,
            'q': 0.0, 'option_type': 'call',
        }
        base.update(overrides)
        return base

    def test_valid_call_returns_200(self):
        resp = self._calc(self._valid_payload())
        self.assertEqual(resp.status_code, 200)

    def test_valid_put_returns_200(self):
        resp = self._calc(self._valid_payload(option_type='put'))
        self.assertEqual(resp.status_code, 200)

    def test_response_has_price_and_greeks(self):
        data = self._calc(self._valid_payload()).get_json()
        self.assertIn('price', data)
        self.assertIn('greeks', data)
        for g in ('delta', 'gamma', 'theta', 'vega', 'rho'):
            self.assertIn(g, data['greeks'])

    def test_call_price_positive(self):
        data = self._calc(self._valid_payload()).get_json()
        self.assertGreater(data['price'], 0)

    def test_put_price_positive(self):
        data = self._calc(self._valid_payload(option_type='put')).get_json()
        self.assertGreater(data['price'], 0)

    def test_missing_S_returns_400(self):
        payload = self._valid_payload()
        del payload['S']
        resp = self._calc(payload)
        self.assertEqual(resp.status_code, 400)

    def test_missing_K_returns_400(self):
        payload = self._valid_payload()
        del payload['K']
        resp = self._calc(payload)
        self.assertEqual(resp.status_code, 400)

    def test_missing_sigma_returns_400(self):
        payload = self._valid_payload()
        del payload['sigma']
        resp = self._calc(payload)
        self.assertEqual(resp.status_code, 400)

    def test_string_S_returns_400(self):
        resp = self._calc(self._valid_payload(S='one-hundred'))
        self.assertEqual(resp.status_code, 400)

    def test_string_sigma_returns_400(self):
        resp = self._calc(self._valid_payload(sigma='high'))
        self.assertEqual(resp.status_code, 400)

    def test_expired_option_returns_400(self):
        resp = self._calc(self._valid_payload(expiration='2000-01-01'))
        self.assertEqual(resp.status_code, 400)

    def test_itm_call_price_exceeds_intrinsic(self):
        data = self._calc(self._valid_payload(S=120, K=100)).get_json()
        self.assertGreater(data['price'], 20)

    def test_high_vol_long_dated_put(self):
        """CRDO-style: $229 stock, $190 strike, 1.37yr, 99.86% vol."""
        payload = self._valid_payload(
            S=229, K=190, expiration='2027-10-15',
            sigma=0.9986, option_type='put',
        )
        data = self._calc(payload).get_json()
        self.assertEqual(self._calc(payload).status_code, 200)
        self.assertGreater(data['price'], 10)
        self.assertLess(data['price'], 229)


# ═══════════════════════════════════════════════════════════════════════════
# /api/iv  (implied volatility from market price)
# ═══════════════════════════════════════════════════════════════════════════

class TestIVEndpoint(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        self.client = _auth_client()

    def _iv(self, payload):
        return self.client.post('/api/iv',
                                json=payload,
                                content_type='application/json')

    def test_valid_iv_request(self):
        resp = self._iv({
            'market_price': 10.0, 'S': 100, 'K': 100,
            'expiration': '2027-01-15', 'r': 0.045,
            'option_type': 'call',
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('iv', data)

    def test_iv_is_float_or_null(self):
        resp = self._iv({
            'market_price': 10.0, 'S': 100, 'K': 100,
            'expiration': '2027-01-15', 'r': 0.045,
            'option_type': 'call',
        })
        iv = resp.get_json()['iv']
        if iv is not None:
            self.assertIsInstance(iv, float)

    def test_missing_market_price_returns_400(self):
        resp = self._iv({'S': 100, 'K': 100, 'T': 1.0, 'r': 0.045,
                         'option_type': 'call'})
        self.assertEqual(resp.status_code, 400)

    def test_expired_option_returns_null_iv(self):
        resp = self._iv({
            'market_price': 10.0, 'S': 100, 'K': 100,
            'expiration': '2000-01-01', 'r': 0.045,
            'option_type': 'call',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.get_json()['iv'])


# ═══════════════════════════════════════════════════════════════════════════
# /api/stock/<ticker>  (mocked)
# ═══════════════════════════════════════════════════════════════════════════

class TestStockEndpoint(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        self.client = _auth_client()

    @patch('main_web.yd.get_stock_info')
    def test_valid_ticker_returns_200(self, mock_info):
        mock_info.return_value = {
            'success': True, 'ticker': 'AAPL',
            'company_name': 'Apple Inc.', 'current_price': 213.50,
            'previous_close': 211.00, 'volume': 55_000_000,
            'dividend_yield': 0.0044, 'earnings_date': '2025-07-31',
        }
        resp = self.client.get('/api/stock/AAPL')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['ticker'], 'AAPL')
        self.assertIn('current_price', data)

    @patch('main_web.yd.get_stock_info')
    def test_failed_lookup_returns_400(self, mock_info):
        mock_info.return_value = {'success': False, 'error': 'Not found'}
        resp = self.client.get('/api/stock/INVALIDXYZ')
        self.assertEqual(resp.status_code, 400)

    @patch('main_web.yd.get_stock_info')
    def test_ticker_uppercased(self, mock_info):
        mock_info.return_value = {
            'success': True, 'ticker': 'AAPL',
            'company_name': 'Apple', 'current_price': 200.0,
            'previous_close': 199.0, 'volume': 1000,
            'dividend_yield': 0.0, 'earnings_date': None,
        }
        self.client.get('/api/stock/aapl')   # lowercase input
        # Should have been called with uppercase
        mock_info.assert_called_once_with('AAPL')


# ═══════════════════════════════════════════════════════════════════════════
# /api/expirations/<ticker>  (mocked)
# ═══════════════════════════════════════════════════════════════════════════

class TestExpirationsEndpoint(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        self.client = _auth_client()

    @patch('main_web.svc.fetch_expirations')
    def test_returns_list_of_expirations(self, mock_exp):
        mock_exp.return_value = {
            'success': True,
            'expirations': ['2025-07-18', '2025-08-15', '2025-09-19'],
        }
        resp = self.client.get('/api/expirations/AAPL')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('expirations', data)
        self.assertEqual(len(data['expirations']), 3)

    @patch('main_web.svc.fetch_expirations')
    def test_failure_returns_400(self, mock_exp):
        mock_exp.return_value = {'success': False, 'error': 'no chain'}
        resp = self.client.get('/api/expirations/BADTICKER')
        self.assertEqual(resp.status_code, 400)

    @patch('main_web.svc.fetch_expirations')
    def test_all_dates_param_forwarded(self, mock_exp):
        mock_exp.return_value = {'success': True, 'expirations': []}
        self.client.get('/api/expirations/AAPL?all=true')
        mock_exp.assert_called_once_with('AAPL', all_dates=True)


# ═══════════════════════════════════════════════════════════════════════════
# /api/search/<query>
# ═══════════════════════════════════════════════════════════════════════════

class TestSearchEndpoint(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        self.client = _auth_client()

    @patch('main_web.yd.search_ticker')
    def test_returns_list(self, mock_search):
        mock_search.return_value = [
            {'symbol': 'AAPL', 'name': 'Apple Inc.', 'exchange': 'NMS', 'type': 'EQUITY'}
        ]
        resp = self.client.get('/api/search/apple')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIsInstance(data, list)

    @patch('main_web.yd.search_ticker')
    def test_empty_results_returns_empty_list(self, mock_search):
        mock_search.return_value = []
        resp = self.client.get('/api/search/xyzxyz')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), [])


if __name__ == '__main__':
    unittest.main()
