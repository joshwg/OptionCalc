"""
Tests for ConfigManager — load/save, geometry parsing, validation, defaults.

All tests are pure-unit; they use a temporary directory so they never touch
the real data/config.json file.
"""

import json
import os
import tempfile
import threading
import unittest
from unittest.mock import patch

from config_manager import ConfigManager


# ── Helper: redirect ConfigManager.CONFIG_FILE to a temp path ─────────────

class _WithTempConfig:
    """Mixin that points CONFIG_FILE at a fresh temp file for each test."""

    def setUp(self):
        self._tmpdir  = tempfile.mkdtemp()
        self._cfg_path = os.path.join(self._tmpdir, 'config.json')
        self._patcher = patch.object(ConfigManager, 'CONFIG_FILE', self._cfg_path)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        # Clean up temp files
        for f in os.listdir(self._tmpdir):
            try:
                os.remove(os.path.join(self._tmpdir, f))
            except OSError:
                pass
        try:
            os.rmdir(self._tmpdir)
        except OSError:
            pass


# ═══════════════════════════════════════════════════════════════════════════
# load_config
# ═══════════════════════════════════════════════════════════════════════════

class TestLoadConfig(_WithTempConfig, unittest.TestCase):

    def test_returns_defaults_when_no_file(self):
        cfg = ConfigManager.load_config()
        self.assertEqual(cfg['risk_free_rate'], ConfigManager.DEFAULT_CONFIG['risk_free_rate'])

    def test_merged_with_defaults_on_partial_file(self):
        # Write only one key
        with open(self._cfg_path, 'w') as f:
            json.dump({'risk_free_rate': 0.06}, f)
        cfg = ConfigManager.load_config()
        # Custom key preserved
        self.assertAlmostEqual(cfg['risk_free_rate'], 0.06, places=6)
        # Default key still present
        self.assertIn('font_size', cfg)

    def test_custom_values_override_defaults(self):
        with open(self._cfg_path, 'w') as f:
            json.dump({'risk_free_rate': 0.099, 'font_size': 18}, f)
        cfg = ConfigManager.load_config()
        self.assertAlmostEqual(cfg['risk_free_rate'], 0.099, places=6)
        self.assertEqual(cfg['font_size'], 18)

    def test_returns_dict(self):
        cfg = ConfigManager.load_config()
        self.assertIsInstance(cfg, dict)

    def test_extra_keys_in_file_are_preserved(self):
        with open(self._cfg_path, 'w') as f:
            json.dump({'my_custom_key': 'hello'}, f)
        cfg = ConfigManager.load_config()
        self.assertEqual(cfg.get('my_custom_key'), 'hello')


# ═══════════════════════════════════════════════════════════════════════════
# save_config / round-trip
# ═══════════════════════════════════════════════════════════════════════════

class TestSaveConfig(_WithTempConfig, unittest.TestCase):

    def test_saved_file_is_valid_json(self):
        ConfigManager.save_config({'risk_free_rate': 0.04})
        with open(self._cfg_path) as f:
            data = json.load(f)
        self.assertEqual(data['risk_free_rate'], 0.04)

    def test_roundtrip_preserves_all_keys(self):
        original = {'risk_free_rate': 0.042, 'font_size': 16, 'extra': 'x'}
        ConfigManager.save_config(original)
        loaded = ConfigManager.load_config()
        for k, v in original.items():
            self.assertEqual(loaded[k], v)

    def test_overwrite_existing_file(self):
        ConfigManager.save_config({'risk_free_rate': 0.04})
        ConfigManager.save_config({'risk_free_rate': 0.06})
        loaded = ConfigManager.load_config()
        self.assertAlmostEqual(loaded['risk_free_rate'], 0.06, places=6)

    def test_concurrent_writes_dont_corrupt(self):
        """Multiple threads saving concurrently must not corrupt the file."""
        errors = []

        def _write(r):
            try:
                ConfigManager.save_config({'risk_free_rate': r})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_write, args=(0.01 * i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], msg=f"Concurrent write errors: {errors}")
        # File must still be valid JSON
        with open(self._cfg_path) as f:
            data = json.load(f)
        self.assertIn('risk_free_rate', data)


# ═══════════════════════════════════════════════════════════════════════════
# is_geometry_valid
# ═══════════════════════════════════════════════════════════════════════════

class TestIsGeometryValid(unittest.TestCase):

    def _v(self, x, y, w, h):
        return ConfigManager.is_geometry_valid(x, y, w, h)

    def test_normal_geometry_valid(self):
        self.assertTrue(self._v(100, 100, 900, 900))

    def test_negative_x_valid_multimonitor(self):
        self.assertTrue(self._v(-200, 100, 900, 900))

    def test_zero_x_y_valid(self):
        self.assertTrue(self._v(0, 0, 800, 600))

    def test_too_small_width_invalid(self):
        self.assertFalse(self._v(100, 100, 50, 900))

    def test_too_small_height_invalid(self):
        self.assertFalse(self._v(100, 100, 900, 50))

    def test_too_large_width_invalid(self):
        self.assertFalse(self._v(100, 100, 20000, 900))

    def test_too_large_height_invalid(self):
        self.assertFalse(self._v(100, 100, 900, 20000))

    def test_extreme_x_invalid(self):
        self.assertFalse(self._v(99999, 100, 900, 900))

    def test_extreme_negative_x_invalid(self):
        self.assertFalse(self._v(-99999, 100, 900, 900))

    def test_extreme_y_invalid(self):
        self.assertFalse(self._v(100, 99999, 900, 900))


# ═══════════════════════════════════════════════════════════════════════════
# parse_geometry
# ═══════════════════════════════════════════════════════════════════════════

class TestParseGeometry(unittest.TestCase):

    def _p(self, s):
        return ConfigManager.parse_geometry(s)

    def test_standard_geometry_string(self):
        result = self._p('900x800+100+200')
        self.assertEqual(result, (900, 800, 100, 200))

    def test_negative_x_coordinate(self):
        result = self._p('900x800-50+200')
        self.assertEqual(result, (900, 800, -50, 200))

    def test_negative_y_coordinate(self):
        result = self._p('900x800+100-30')
        self.assertEqual(result, (900, 800, 100, -30))

    def test_both_negative(self):
        result = self._p('900x800-50-30')
        self.assertEqual(result, (900, 800, -50, -30))

    def test_zero_offsets(self):
        result = self._p('500x400+0+0')
        self.assertEqual(result, (500, 400, 0, 0))

    def test_invalid_string_returns_none(self):
        self.assertIsNone(self._p('garbage'))

    def test_empty_string_returns_none(self):
        self.assertIsNone(self._p(''))

    def test_partial_string_returns_none(self):
        self.assertIsNone(self._p('900x800'))

    def test_width_and_height_parsed_correctly(self):
        w, h, x, y = self._p('1200x900+0+0')
        self.assertEqual(w, 1200)
        self.assertEqual(h, 900)


if __name__ == '__main__':
    unittest.main()
