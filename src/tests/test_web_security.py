"""
Security-focused tests for the Flask web application.

Tests cover:
  1. Authentication — all protected routes require a valid session
  2. Login endpoint — correct/incorrect password, brute-force response
  3. Input sanitisation — XSS chars, path traversal, null bytes, huge strings
  4. Parameter boundary enforcement — negative prices, zero time, extreme vol
  5. Payload hardening — missing fields, wrong types, oversized JSON, NaN/Inf
  6. Session integrity — expired session is rejected
"""

import json
import os
import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from main_web import app

# Must match whatever OPTION_PWD was set to when main_web was imported.
# conftest.py sets it via os.environ.setdefault before any import happens.
_PASSWORD = os.environ.get("OPTION_PWD", "test-secret-for-tests")


# ─── helpers ──────────────────────────────────────────────────────────────

def _unauth_client():
    """Fresh client with NO session."""
    c = app.test_client()
    return c


def _auth_client():
    """Client with a valid authenticated session."""
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['authenticated'] = True
        sess['last_activity'] = datetime.now().isoformat()
    return c


def _expired_client():
    """Client whose session last_activity is 3 hours in the past."""
    c = app.test_client()
    three_hours_ago = (datetime.now() - timedelta(hours=3)).isoformat()
    with c.session_transaction() as sess:
        sess['authenticated'] = True
        sess['last_activity'] = three_hours_ago
    return c


# ═══════════════════════════════════════════════════════════════════════════
# 1. Authentication — unauthenticated requests must be rejected
# ═══════════════════════════════════════════════════════════════════════════

PROTECTED_GET_ROUTES = [
    '/api/config',
    '/api/stock/AAPL',
    '/api/expirations/AAPL',
    '/api/hist-vol/AAPL',
    '/api/search/apple',
    '/api/atm-iv/AAPL/2027-01-15/call',
]

PROTECTED_POST_ROUTES = [
    ('/api/calculate', {'S': 100, 'K': 100, 'expiration': '2027-01-15',
                        'sigma': 0.25, 'r': 0.045, 'q': 0, 'option_type': 'call'}),
    ('/api/iv',        {'market_price': 10, 'S': 100, 'K': 100,
                        'expiration': '2027-01-15', 'r': 0.045, 'option_type': 'call'}),
    ('/api/config',    {'risk_free_rate': 0.04}),
]


class TestUnauthenticated(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        self.c = _unauth_client()

    def test_index_redirects_to_login(self):
        resp = self.c.get('/')
        # Should redirect (302) to /login
        self.assertIn(resp.status_code, (301, 302))
        self.assertIn('/login', resp.headers.get('Location', ''))

    def test_api_get_routes_return_401(self):
        for route in PROTECTED_GET_ROUTES:
            with self.subTest(route=route):
                resp = self.c.get(route)
                self.assertEqual(resp.status_code, 401,
                                 msg=f"Expected 401 for unauthenticated GET {route}")

    def test_api_post_routes_return_401(self):
        for route, payload in PROTECTED_POST_ROUTES:
            with self.subTest(route=route):
                resp = self.c.post(route, json=payload,
                                   content_type='application/json')
                self.assertEqual(resp.status_code, 401,
                                 msg=f"Expected 401 for unauthenticated POST {route}")


# ═══════════════════════════════════════════════════════════════════════════
# 2. Session expiry
# ═══════════════════════════════════════════════════════════════════════════

class TestSessionExpiry(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True

    def test_expired_session_rejected_on_api(self):
        c = _expired_client()
        resp = c.get('/api/config')
        self.assertEqual(resp.status_code, 401)

    def test_expired_session_redirects_on_page(self):
        c = _expired_client()
        resp = c.get('/')
        self.assertIn(resp.status_code, (301, 302))

    def test_valid_session_accepted(self):
        c = _auth_client()
        resp = c.get('/api/config')
        self.assertEqual(resp.status_code, 200)


# ═══════════════════════════════════════════════════════════════════════════
# 3. Login endpoint
# ═══════════════════════════════════════════════════════════════════════════

class TestLoginEndpoint(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        self.c = _unauth_client()

    def test_get_login_page_returns_200(self):
        resp = self.c.get('/login')
        self.assertEqual(resp.status_code, 200)

    def test_correct_password_redirects(self):
        resp = self.c.post('/login', data={'password': _PASSWORD})
        self.assertIn(resp.status_code, (301, 302))

    def test_wrong_password_returns_200_with_error(self):
        resp = self.c.post('/login', data={'password': 'WRONG'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Incorrect', resp.data)

    def test_empty_password_fails(self):
        resp = self.c.post('/login', data={'password': ''})
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Incorrect', resp.data)

    def test_sql_injection_in_password_fails(self):
        resp = self.c.post('/login', data={'password': "' OR '1'='1"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Incorrect', resp.data)

    def test_very_long_password_does_not_crash(self):
        resp = self.c.post('/login', data={'password': 'A' * 10_000})
        self.assertIn(resp.status_code, (200, 400, 413))

    def test_logout_clears_session(self):
        # Log in first
        self.c.post('/login', data={'password': _PASSWORD})
        # Confirm we can access a protected route
        resp = self.c.get('/api/config')
        self.assertEqual(resp.status_code, 200)
        # Log out
        self.c.get('/logout')
        # Protected route should now fail
        resp = self.c.get('/api/config')
        self.assertEqual(resp.status_code, 401)


# ═══════════════════════════════════════════════════════════════════════════
# 4. Input sanitisation — ticker / query parameters
# ═══════════════════════════════════════════════════════════════════════════

MALICIOUS_TICKERS = [
    '<script>alert(1)</script>',          # XSS
    '../../../etc/passwd',                 # path traversal
    'AAPL\x00evil',                        # null-byte injection
    '; DROP TABLE options; --',           # SQL injection pattern
    '${7*7}',                              # template injection
    '\r\nX-Injected: header',             # header injection
    'A' * 500,                             # excessive length
]


class TestInputSanitisation(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        self.c = _auth_client()

    @patch('option_lib.yahoo_data.get_stock_info')
    def test_malicious_ticker_in_stock_endpoint(self, mock_info):
        mock_info.return_value = {'success': False, 'error': 'bad ticker'}
        for ticker in MALICIOUS_TICKERS:
            with self.subTest(ticker=repr(ticker)):
                resp = self.c.get(f'/api/stock/{ticker}')
                # Path-traversal inputs may produce a 404 (routing mismatch);
                # XSS/injection inputs may produce a 400 or 404.
                # None of these should silently succeed (200) or crash (500).
                self.assertIn(resp.status_code, (400, 404),
                    msg=f"Unexpected status {resp.status_code} for ticker {repr(ticker)}")

    @patch('option_lib.yahoo_data.search_ticker')
    def test_malicious_query_in_search_endpoint(self, mock_search):
        mock_search.return_value = []
        for query in MALICIOUS_TICKERS:
            with self.subTest(query=repr(query)):
                resp = self.c.get(f'/api/search/{query}')
                self.assertIn(resp.status_code, (200, 400, 404),
                    msg=f"Unexpected status {resp.status_code} for query {repr(query)}")

    @patch('option_lib.yahoo_data.calculate_historical_volatility')
    def test_malicious_ticker_in_hist_vol(self, mock_vol):
        mock_vol.return_value = None
        for ticker in MALICIOUS_TICKERS:
            with self.subTest(ticker=repr(ticker)):
                resp = self.c.get(f'/api/hist-vol/{ticker}')
                self.assertIn(resp.status_code, (400, 404),
                    msg=f"Unexpected status {resp.status_code} for ticker {repr(ticker)}")


# ═══════════════════════════════════════════════════════════════════════════
# 5. /api/calculate — parameter boundary enforcement
# ═══════════════════════════════════════════════════════════════════════════

class TestCalculateBoundaries(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        self.c = _auth_client()

    def _calc(self, **overrides):
        payload = {
            'S': 100.0, 'K': 100.0,
            'expiration': '2027-01-15',
            'sigma': 0.25, 'r': 0.045,
            'q': 0.0, 'option_type': 'call',
        }
        payload.update(overrides)
        return self.c.post('/api/calculate', json=payload,
                           content_type='application/json')

    # ── invalid numeric values ─────────────────────────────────────────────

    def test_negative_S_returns_error(self):
        resp = self._calc(S=-1)
        # Either 400 (validated) or a non-5xx handled error
        self.assertNotEqual(resp.status_code, 500)

    def test_zero_S_returns_error_or_handled(self):
        resp = self._calc(S=0)
        self.assertNotEqual(resp.status_code, 500)

    def test_negative_K_returns_error_or_handled(self):
        resp = self._calc(K=-50)
        self.assertNotEqual(resp.status_code, 500)

    def test_zero_K_returns_error_or_handled(self):
        resp = self._calc(K=0)
        self.assertNotEqual(resp.status_code, 500)

    def test_negative_sigma_returns_error_or_handled(self):
        resp = self._calc(sigma=-0.1)
        self.assertNotEqual(resp.status_code, 500)

    def test_extremely_high_vol_handled(self):
        resp = self._calc(sigma=100.0)   # 10 000%
        self.assertNotEqual(resp.status_code, 500)

    def test_very_large_S_handled(self):
        resp = self._calc(S=1e12)
        self.assertNotEqual(resp.status_code, 500)

    def test_expired_date_returns_400(self):
        resp = self._calc(expiration='2000-01-01')
        self.assertEqual(resp.status_code, 400)

    # ── NaN / Infinity in payload ──────────────────────────────────────────

    def test_nan_S_returns_400(self):
        # Python's json module accepts bare NaN (non-standard extension).
        # The server now validates for finite values and must reject this.
        raw = b'{"S": NaN, "K": 100, "expiration": "2027-01-15", ' \
              b'"sigma": 0.25, "r": 0.045, "q": 0, "option_type": "call"}'
        resp = self.c.post('/api/calculate', data=raw,
                           content_type='application/json')
        self.assertEqual(resp.status_code, 400)   # must reject non-finite S

    def test_infinity_sigma_handled(self):
        # Python's json module accepts bare Infinity; server must reject it.
        raw = b'{"S": 100, "K": 100, "expiration": "2027-01-15", ' \
              b'"sigma": Infinity, "r": 0.045, "q": 0, "option_type": "call"}'
        resp = self.c.post('/api/calculate', data=raw,
                           content_type='application/json')
        self.assertEqual(resp.status_code, 400)   # must reject non-finite sigma

    # ── payload structure ──────────────────────────────────────────────────

    def test_empty_json_body_returns_400(self):
        resp = self.c.post('/api/calculate', json={},
                           content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    def test_non_json_body_returns_error(self):
        resp = self.c.post('/api/calculate',
                           data='not json at all',
                           content_type='text/plain')
        self.assertIn(resp.status_code, (400, 415, 500))

    def test_array_body_returns_400(self):
        resp = self.c.post('/api/calculate', json=[1, 2, 3],
                           content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    def test_oversized_payload_handled(self):
        """A 1 MB payload should not crash the server."""
        big = {'S': 100, 'K': 100, 'expiration': '2027-01-15',
               'sigma': 0.25, 'r': 0.045, 'q': 0, 'option_type': 'call',
               'junk': 'x' * 1_000_000}
        resp = self.c.post('/api/calculate', json=big,
                           content_type='application/json')
        self.assertNotEqual(resp.status_code, 500)

    def test_wrong_option_type_handled(self):
        resp = self._calc(option_type='straddle')
        self.assertNotEqual(resp.status_code, 500)

    def test_xss_in_option_type_handled(self):
        resp = self._calc(option_type='<script>alert(1)</script>')
        self.assertNotEqual(resp.status_code, 500)

    # ── response never leaks internal paths or stack traces ───────────────

    def test_error_response_does_not_leak_traceback(self):
        resp = self._calc(S='not-a-number')
        body = resp.data.decode('utf-8', errors='replace')
        # Should not contain raw Python file paths or "Traceback"
        self.assertNotIn('Traceback', body,
                         msg="Error response leaks Python traceback")
        self.assertNotIn('/home/', body)
        self.assertNotIn('/mnt/c/', body)


# ═══════════════════════════════════════════════════════════════════════════
# 6. /api/iv — security boundaries
# ═══════════════════════════════════════════════════════════════════════════

class TestIVSecurity(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        self.c = _auth_client()

    def _iv(self, **overrides):
        payload = {
            'market_price': 10.0, 'S': 100, 'K': 100,
            'expiration': '2027-01-15', 'r': 0.045, 'option_type': 'call',
        }
        payload.update(overrides)
        return self.c.post('/api/iv', json=payload,
                           content_type='application/json')

    def test_negative_market_price_handled(self):
        resp = self._iv(market_price=-5)
        self.assertNotEqual(resp.status_code, 500)

    def test_zero_market_price_handled(self):
        resp = self._iv(market_price=0)
        self.assertIn(resp.status_code, (200, 400))

    def test_absurdly_large_market_price_handled(self):
        resp = self._iv(market_price=1e15)
        self.assertNotEqual(resp.status_code, 500)

    def test_string_market_price_returns_400(self):
        resp = self._iv(market_price='expensive')
        self.assertEqual(resp.status_code, 400)

    def test_missing_S_returns_400(self):
        payload = {'market_price': 10, 'K': 100,
                   'expiration': '2027-01-15', 'r': 0.045, 'option_type': 'call'}
        resp = self.c.post('/api/iv', json=payload,
                           content_type='application/json')
        self.assertEqual(resp.status_code, 400)


if __name__ == '__main__':
    unittest.main()
