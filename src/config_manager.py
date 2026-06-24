"""
Configuration and Window Geometry Management Utilities

App settings (risk_free_rate, font_size, …) are stored in
``../data/config.json`` as a plain JSON object.  All keys are preserved
on round-trip so callers may store arbitrary extra state.

Window-geometry helpers live here because they require Tkinter; they are
desktop-only and are never imported by the web server.
"""

import json
import re
import threading
from pathlib import Path
from typing import Any


# Thread-safety: all file writes go through this lock so concurrent saves
# from multiple calculator windows cannot produce corrupted JSON.
_write_lock = threading.Lock()


class ConfigManager:

    CONFIG_FILE: Path = Path("../data/config.json")

    DEFAULT_CONFIG: dict[str, Any] = {
        "risk_free_rate": 0.045,
        "font_size":      14,
    }

    # ── Persistence ───────────────────────────────────────────────────────────

    @staticmethod
    def load_config() -> dict:
        """Return config merged with defaults.

        Reads ``CONFIG_FILE`` as JSON and deep-merges over ``DEFAULT_CONFIG``
        so unknown/extra keys stored by callers are preserved.  Returns a
        copy of defaults when the file does not exist or is invalid JSON.
        """
        cfg = ConfigManager.DEFAULT_CONFIG.copy()
        try:
            cfg_path = Path(ConfigManager.CONFIG_FILE)
            if cfg_path.exists():
                with open(cfg_path, "r", encoding="utf-8") as fh:
                    loaded = json.load(fh)
                if isinstance(loaded, dict):
                    cfg.update(loaded)
        except (json.JSONDecodeError, OSError):
            pass
        return cfg

    @staticmethod
    def save_config(config: dict) -> None:
        """Persist *config* to ``CONFIG_FILE``.

        Existing keys not present in *config* are preserved (merge, not
        replace).  Writes atomically under ``_write_lock``.
        """
        cfg_path = Path(ConfigManager.CONFIG_FILE)
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        with _write_lock:
            existing: dict = {}
            try:
                if cfg_path.exists():
                    with open(cfg_path, "r", encoding="utf-8") as fh:
                        existing = json.load(fh) or {}
            except (json.JSONDecodeError, OSError):
                pass
            existing.update(config)
            with open(cfg_path, "w", encoding="utf-8") as fh:
                json.dump(existing, fh, indent=2)

    # ── Window geometry ───────────────────────────────────────────────────────

    @staticmethod
    def is_geometry_valid(x, y, width, height):
        """Return True if window geometry is within reasonable bounds (multi-monitor safe)."""
        try:
            if width < 100 or width > 10000:
                return False
            if height < 100 or height > 10000:
                return False
            if abs(x) > 20000 or abs(y) > 20000:
                return False
            return True
        except Exception:
            return False

    @staticmethod
    def parse_geometry(geometry_string):
        """Parse a Tkinter geometry string (e.g. ``'500x450+100+100'``).

        Returns ``(width, height, x, y)`` or ``None`` on failure.
        Negative coordinates (multi-monitor) are handled correctly.
        """
        try:
            match = re.match(r'(\d+)x(\d+)([+-]\d+)([+-]\d+)', geometry_string)
            if match:
                return (
                    int(match.group(1)),
                    int(match.group(2)),
                    int(match.group(3)),
                    int(match.group(4)),
                )
        except Exception:
            pass
        return None

    @staticmethod
    def clamp_window_to_screen(window, min_visible=100):
        """Move *window* back on-screen if it has drifted off.

        Must be called **after** the window is mapped so winfo_x/y/width/height
        reflect the actual on-screen position.  Typically scheduled with
        ``window.after_idle(...)``.
        """
        try:
            window.update_idletasks()
            x  = window.winfo_x()
            y  = window.winfo_y()
            w  = window.winfo_width()
            h  = window.winfo_height()
            sw = window.winfo_screenwidth()
            sh = window.winfo_screenheight()

            new_x = max(-w + min_visible, min(x, sw - min_visible))
            new_y = max(0, min(y, sh - min_visible))

            if new_x != x or new_y != y:
                window.geometry(f"+{new_x}+{new_y}")
        except Exception:
            pass

    @staticmethod
    def load_window_geometry(window, config, window_key='calculator_window_geometry',
                             window_index=0):
        """Apply saved window geometry from *config* to *window*.

        Geometry is applied as-saved; a post-show clamp is scheduled via
        ``after_idle`` so live screen dimensions are used.  Falls back to a
        cascaded default position for windows beyond index 0.
        """
        try:
            saved = config.get(window_key)
            if saved:
                if (saved.get('screen_width')  == window.winfo_screenwidth() and
                        saved.get('screen_height') == window.winfo_screenheight()):
                    x      = saved.get('x')
                    y      = saved.get('y')
                    width  = saved.get('width',  900)
                    height = saved.get('height', 900)
                    if ConfigManager.is_geometry_valid(x, y, width, height):
                        window.geometry(f"{width}x{height}+{x}+{y}")
                        window.after_idle(
                            lambda: ConfigManager.clamp_window_to_screen(window)
                        )
                        return

            if window_index > 0:
                base = config.get('calculator_window_0') or {}
                bx = base.get('x', 100)
                by = base.get('y', 100)
                bw = base.get('width',  900)
                bh = base.get('height', 900)
                off = window_index * 30
                window.geometry(f"{bw}x{bh}+{bx + off}+{by + off}")
                window.after_idle(lambda: ConfigManager.clamp_window_to_screen(window))
        except Exception:
            pass

    @staticmethod
    def save_window_geometry(window, config, window_key='calculator_window_geometry'):
        """Update *config* with the current geometry of *window* and return it."""
        try:
            parsed = ConfigManager.parse_geometry(window.geometry())
            if parsed:
                width, height, x, y = parsed
                config[window_key] = {
                    'x':             x,
                    'y':             y,
                    'width':         width,
                    'height':        height,
                    'screen_width':  window.winfo_screenwidth(),
                    'screen_height': window.winfo_screenheight(),
                }
        except Exception:
            pass
        return config
