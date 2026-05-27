"""
Configuration and Window Geometry Management Utilities
"""

import json
import os
import re
import threading


class ConfigManager:
    """Manages application configuration and window geometry"""

    CONFIG_FILE = "config.json"
    _write_lock = threading.Lock()

    DEFAULT_CONFIG = {
        'risk_free_rate': 0.045,
        'font_size': 14,
    }
    
    @staticmethod
    def load_config():
        """Load configuration from JSON file"""
        if os.path.exists(ConfigManager.CONFIG_FILE):
            with open(ConfigManager.CONFIG_FILE, 'r') as f:
                loaded_config = json.load(f)
            return {**ConfigManager.DEFAULT_CONFIG, **loaded_config}
        return dict(ConfigManager.DEFAULT_CONFIG)
    
    @staticmethod
    def save_config(config):
        """Save configuration to JSON file"""
        with ConfigManager._write_lock:
            with open(ConfigManager.CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
    
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
    def load_window_geometry(window, config, window_key='calculator_window_geometry', window_index=0):
        """Load and apply saved window geometry
        
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
                    
                    # Validate geometry
                    if ConfigManager.is_geometry_valid(x, y, width, height):
                        window.geometry(f"{width}x{height}+{x}+{y}")
                        return
            
            # If no saved geometry or screen mismatch, try to cascade from window 0's position
            if window_index > 0:
                # Try to get window 0's saved position to cascade from
                window_0_geometry = config.get('calculator_window_0')
                if window_0_geometry:
                    base_x = window_0_geometry.get('x', 100)
                    base_y = window_0_geometry.get('y', 100)
                    base_width = window_0_geometry.get('width', 900)
                    base_height = window_0_geometry.get('height', 900)
                else:
                    # Default starting position if window 0 hasn't been saved yet
                    base_x = 100
                    base_y = 100
                    base_width = 900
                    base_height = 900
                
                # Cascade from base position
                offset = window_index * 30
                window.geometry(f"{base_width}x{base_height}+{base_x + offset}+{base_y + offset}")
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
