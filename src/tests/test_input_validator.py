"""
Tests for utils/input_validator.py.

InputValidator uses tkinter.messagebox for error dialogs; all tests call
with show_error=False so no display is needed.
"""

import sys
import unittest
from unittest.mock import patch, MagicMock

# Stub tkinter before importing the module — handles headless environments
_tk_mock = MagicMock()
sys.modules.setdefault('tkinter', _tk_mock)
sys.modules.setdefault('tkinter.messagebox', _tk_mock.messagebox)

from utils.input_validator import InputValidator


# ═══════════════════════════════════════════════════════════════════════════
# validate_ticker
# ═══════════════════════════════════════════════════════════════════════════

class TestValidateTicker(unittest.TestCase):

    def _v(self, s):
        return InputValidator.validate_ticker(s, show_error=False)

    def test_valid_ticker_returned_uppercase(self):
        self.assertEqual(self._v('aapl'), 'AAPL')

    def test_already_uppercase_unchanged(self):
        self.assertEqual(self._v('MSFT'), 'MSFT')

    def test_leading_trailing_whitespace_stripped(self):
        self.assertEqual(self._v('  TSLA  '), 'TSLA')

    def test_empty_string_returns_none(self):
        self.assertIsNone(self._v(''))

    def test_whitespace_only_returns_none(self):
        self.assertIsNone(self._v('   '))

    def test_mixed_case_normalised(self):
        self.assertEqual(self._v('crDo'), 'CRDO')

    def test_ticker_with_dot(self):
        # Some tickers have dots (BRK.B)
        result = self._v('BRK.B')
        self.assertEqual(result, 'BRK.B')

    def test_ticker_with_hyphen(self):
        result = self._v('BF-B')
        self.assertEqual(result, 'BF-B')


# ═══════════════════════════════════════════════════════════════════════════
# validate_float
# ═══════════════════════════════════════════════════════════════════════════

class TestValidateFloat(unittest.TestCase):

    def _v(self, s, field='Value', min_val=None, max_val=None):
        return InputValidator.validate_float(
            s, field, show_error=False, min_value=min_val, max_value=max_val)

    def test_valid_integer_string(self):
        self.assertAlmostEqual(self._v('42'), 42.0, places=6)

    def test_valid_float_string(self):
        self.assertAlmostEqual(self._v('3.14'), 3.14, places=6)

    def test_negative_float(self):
        self.assertAlmostEqual(self._v('-1.5'), -1.5, places=6)

    def test_scientific_notation(self):
        result = self._v('1e-3')
        self.assertAlmostEqual(result, 0.001, places=6)

    def test_invalid_string_returns_none(self):
        self.assertIsNone(self._v('abc'))

    def test_empty_string_returns_none(self):
        self.assertIsNone(self._v(''))

    def test_whitespace_trimmed_before_parse(self):
        self.assertAlmostEqual(self._v('  2.5  '), 2.5, places=6)

    # ── min_value ─────────────────────────────────────────────────────────

    def test_value_at_min_allowed(self):
        self.assertAlmostEqual(self._v('0', min_val=0), 0.0, places=6)

    def test_value_above_min_allowed(self):
        self.assertAlmostEqual(self._v('1', min_val=0), 1.0, places=6)

    def test_value_below_min_returns_none(self):
        self.assertIsNone(self._v('-1', min_val=0))

    # ── max_value ─────────────────────────────────────────────────────────

    def test_value_at_max_allowed(self):
        self.assertAlmostEqual(self._v('100', max_val=100), 100.0, places=6)

    def test_value_below_max_allowed(self):
        self.assertAlmostEqual(self._v('99', max_val=100), 99.0, places=6)

    def test_value_above_max_returns_none(self):
        self.assertIsNone(self._v('101', max_val=100))

    # ── combined bounds ───────────────────────────────────────────────────

    def test_within_range(self):
        self.assertAlmostEqual(self._v('50', min_val=0, max_val=100), 50.0)

    def test_below_range_returns_none(self):
        self.assertIsNone(self._v('-1', min_val=0, max_val=100))

    def test_above_range_returns_none(self):
        self.assertIsNone(self._v('101', min_val=0, max_val=100))


# ═══════════════════════════════════════════════════════════════════════════
# validate_date
# ═══════════════════════════════════════════════════════════════════════════

class TestValidateDate(unittest.TestCase):

    def _v(self, s):
        return InputValidator.validate_date(s, show_error=False)

    def test_valid_date_string_returned(self):
        self.assertEqual(self._v('2025-12-19'), '2025-12-19')

    def test_whitespace_stripped(self):
        self.assertEqual(self._v('  2025-06-01  '), '2025-06-01')

    def test_empty_string_returns_none(self):
        self.assertIsNone(self._v(''))

    def test_whitespace_only_returns_none(self):
        self.assertIsNone(self._v('   '))

    def test_arbitrary_non_empty_string_accepted(self):
        # validate_date only checks non-empty; format is not validated here
        result = self._v('not-a-real-date')
        self.assertIsNotNone(result)


# ═══════════════════════════════════════════════════════════════════════════
# validate_required_fields
# ═══════════════════════════════════════════════════════════════════════════

class TestValidateRequiredFields(unittest.TestCase):

    def _v(self, fields):
        return InputValidator.validate_required_fields(fields, show_error=False)

    def test_all_present_returns_true_none(self):
        valid, missing = self._v({'Ticker': 'AAPL', 'Strike': '100'})
        self.assertTrue(valid)
        self.assertIsNone(missing)

    def test_empty_string_value_fails(self):
        valid, missing = self._v({'Ticker': '', 'Strike': '100'})
        self.assertFalse(valid)
        self.assertEqual(missing, 'Ticker')

    def test_whitespace_only_value_fails(self):
        valid, missing = self._v({'Ticker': 'AAPL', 'Strike': '   '})
        self.assertFalse(valid)
        self.assertEqual(missing, 'Strike')

    def test_none_value_fails(self):
        valid, missing = self._v({'Ticker': None})
        self.assertFalse(valid)

    def test_zero_numeric_string_passes(self):
        # '0' is non-empty — should pass
        valid, missing = self._v({'Rate': '0'})
        self.assertTrue(valid)

    def test_empty_dict_passes(self):
        valid, missing = self._v({})
        self.assertTrue(valid)
        self.assertIsNone(missing)


# ═══════════════════════════════════════════════════════════════════════════
# get_dividend_yield
# ═══════════════════════════════════════════════════════════════════════════

class TestGetDividendYield(unittest.TestCase):

    def _g(self, s, fallback=0.0):
        return InputValidator.get_dividend_yield(s, fallback)

    def test_percent_string_converted_to_decimal(self):
        # '2.5' percent → 0.025 decimal
        self.assertAlmostEqual(self._g('2.5'), 0.025, places=6)

    def test_zero_percent(self):
        self.assertAlmostEqual(self._g('0'), 0.0, places=6)

    def test_invalid_string_uses_fallback(self):
        self.assertAlmostEqual(self._g('abc', fallback=0.03), 0.03, places=6)

    def test_empty_string_uses_fallback(self):
        self.assertAlmostEqual(self._g('', fallback=0.01), 0.01, places=6)

    def test_none_uses_fallback(self):
        self.assertAlmostEqual(self._g(None, fallback=0.02), 0.02, places=6)

    def test_large_percent_string(self):
        # 5% dividend
        self.assertAlmostEqual(self._g('5.0'), 0.05, places=6)


if __name__ == '__main__':
    unittest.main()
