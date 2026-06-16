"""
Configuration and Window Geometry Management Utilities

App settings (risk_free_rate etc.) are delegated to config.py / optioncalculator.cfg.
This module adds Tkinter window-geometry management on top.
"""

import re

import config as _cfg


# GUI-only defaults not stored in the .cfg file
_GUI_DEFAULTS = {
    'font_size': 14,
}


class ConfigManager:
    """Manages Tkinter window geometry; delegates app config to config.py."""

    @staticmethod
    def load_config():
        """Return merged app config + GUI defaults."""
        cfg = _cfg.load_config()
        return {**_GUI_DEFAULTS, **cfg}

    @staticmethod
    def save_config(config):
        """Persist app settings (non-GUI keys) via config.py."""
        _cfg.save_config({k: v for k, v in config.items() if k in _cfg.DEFAULTS})
    
    @staticmethod
    def is_geometry_valid(x, y, width, height):
        """Check if window geometry is within reasonable bounds (supports multi-monitor)"""
        try:
            # Be lenient for multi-monitor setups
            # Negative coordinates are valid (monitors to the left/above)
            # Large coordinates are valid (monitors to the right/below)
            
            # Just check for reasonable window size
            if width < 100 or width > 10000:
                return False
            if height < 100 or height > 10000:
                return False
            
            # Check for extremely unreasonable positions (likely corrupted data)
            if abs(x) > 20000 or abs(y) > 20000:
                return False
            
            return True
        except:
            return False
    
    @staticmethod
    def parse_geometry(geometry_string):
        """Parse geometry string (e.g., '500x450+100+100' or '500x450+-100+50')
        
        Returns:
            tuple: (width, height, x, y) or None if parsing fails
        """
        try:
            # Use regex to handle negative coordinates
            match = re.match(r'(\d+)x(\d+)([+-]\d+)([+-]\d+)', geometry_string)
            if match:
                width = int(match.group(1))
                height = int(match.group(2))
                x = int(match.group(3))
                y = int(match.group(4))
                return (width, height, x, y)
        except Exception:
            pass
        return None
    
    @staticmethod
    def clamp_window_to_screen(window, min_visible=100):
        """Move window back on-screen if it has drifted off after being shown.

        Must be called AFTER the window is mapped so winfo_x/y/width/height
        reflect the actual on-screen position rather than pre-show defaults.
        Typically scheduled via window.after_idle(...).
        """
        try:
            window.update_idletasks()
            x = window.winfo_x()
            y = window.winfo_y()
            w = window.winfo_width()
            h = window.winfo_height()
            sw = window.winfo_screenwidth()
            sh = window.winfo_screenheight()

            new_x = max(-w + min_visible, min(x, sw - min_visible))
            new_y = max(0, min(y, sh - min_visible))  # title bar must stay on screen

            if new_x != x or new_y != y:
                window.geometry(f"+{new_x}+{new_y}")
        except Exception:
            pass

    @staticmethod
    def load_window_geometry(window, config, window_key='calculator_window_geometry', window_index=0):
        """Load and apply saved window geometry.

        Geometry is applied as-saved; a post-show clamp is scheduled via
        after_idle so the live screen dimensions are used, not the init-time ones.

        Args:
            window: The tkinter window to apply geometry to
            config: Configuration dictionary
            window_key: Key in config for this window's geometry (e.g., 'calculator_window_0')
            window_index: Index of this window (0-9), used for default cascading if no saved geometry
        """
        try:
            saved_geometry = config.get(window_key)
            if saved_geometry:
                # Check if screen geometry matches
                saved_screen_width = saved_geometry.get('screen_width')
                saved_screen_height = saved_geometry.get('screen_height')
                current_screen_width = window.winfo_screenwidth()
                current_screen_height = window.winfo_screenheight()

                # Only apply saved position if screen geometry matches
                if (saved_screen_width == current_screen_width and
                        saved_screen_height == current_screen_height):
                    x = saved_geometry.get('x')
                    y = saved_geometry.get('y')
                    width = saved_geometry.get('width', 900)
                    height = saved_geometry.get('height', 900)

                    if ConfigManager.is_geometry_valid(x, y, width, height):
                        window.geometry(f"{width}x{height}+{x}+{y}")
                        # Clamp after the window is actually shown
                        window.after_idle(lambda: ConfigManager.clamp_window_to_screen(window))
                        return

            # If no saved geometry or screen mismatch, cascade from window 0's position
            if window_index > 0:
                window_0_geometry = config.get('calculator_window_0')
                if window_0_geometry:
                    base_x = window_0_geometry.get('x', 100)
                    base_y = window_0_geometry.get('y', 100)
                    base_width = window_0_geometry.get('width', 900)
                    base_height = window_0_geometry.get('height', 900)
                else:
                    base_x = 100
                    base_y = 100
                    base_width = 900
                    base_height = 900

                offset = window_index * 30
                window.geometry(f"{base_width}x{base_height}+{base_x + offset}+{base_y + offset}")
                window.after_idle(lambda: ConfigManager.clamp_window_to_screen(window))
        except Exception:
            pass  # Use default geometry if loading fails
    
    @staticmethod
    def save_window_geometry(window, config, window_key='calculator_window_geometry'):
        """Save current window geometry
        
        Args:
            window: The tkinter window to save geometry from
            config: Configuration dictionary to update
            window_key: Key in config for this window's geometry
            
        Returns:
            dict: Updated configuration dictionary
        """
        try:
            # Get current geometry
            geometry = window.geometry()
            parsed = ConfigManager.parse_geometry(geometry)
            
            if parsed:
                width, height, x, y = parsed
                
                # Get screen dimensions
                screen_width = window.winfo_screenwidth()
                screen_height = window.winfo_screenheight()
                
                # Update config
                config[window_key] = {
                    'x': x,
                    'y': y,
                    'width': width,
                    'height': height,
                    'screen_width': screen_width,
                    'screen_height': screen_height
                }
        except Exception:
            pass  # Ignore errors when saving geometry
        
        return config
