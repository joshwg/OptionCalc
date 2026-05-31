"""
Black-Scholes Option Calculator - Main Application
Supports multiple windows for different stocks
"""

import os
import sys
import tkinter as tk


def configure_client_mode(argv=None):
    """Default to remote services; allow opting into local services via --local."""
    if argv is None:
        argv = sys.argv[1:]

    use_local = "--local" in argv
    os.environ["OPTIONCALC_CLIENT_MODE"] = "local" if use_local else "remote"

    if use_local:
        sys.argv = [sys.argv[0], *[arg for arg in argv if arg != "--local"]]


configure_client_mode()

from calculator_window import OptionCalculatorWindow


class MainApplication:
    """Main application - starts directly with a calculator window"""
    
    # Class variable to track all open windows
    all_windows = []
    root_window = None  # Track the root Tk window
    
    @classmethod
    def get_next_window_index(cls):
        """Get the next available window index (0-9)"""
        # Find the first available index
        used_indices = set(w.window_index for w in cls.all_windows if hasattr(w, 'window_index'))
        for i in range(10):
            if i not in used_indices:
                return i
        # If all 10 slots are used, cycle back to 0
        return 0
    
    @classmethod
    def register_window(cls, window):
        """Register a new window"""
        cls.all_windows.append(window)
    
    @classmethod
    def unregister_window(cls, window):
        """Unregister a closed window"""
        if window in cls.all_windows:
            cls.all_windows.remove(window)
        
        # If the root window is being closed, reset the reference
        if cls.root_window and hasattr(window, 'window'):
            try:
                if window.window == cls.root_window:
                    cls.root_window = None
            except:
                pass
    
    @classmethod
    def create_new_window(cls, ticker=None):
        """Create a new calculator window"""
        window_index = cls.get_next_window_index()
        
        # Check if root window is still valid
        parent = None
        if cls.root_window:
            try:
                # Try to access the window to see if it's still alive
                cls.root_window.winfo_exists()
                parent = cls.root_window
            except:
                # Root window has been destroyed, reset it
                cls.root_window = None
                parent = None
        
        window = OptionCalculatorWindow(parent=parent, ticker=ticker, window_index=window_index)
        cls.register_window(window)
        
        # If this is the first window or root was destroyed, store new window as root
        if cls.root_window is None:
            cls.root_window = window.window
        
        return window
    
    @classmethod
    def quit_all(cls):
        """Quit the application - close all windows"""
        # Save the root window reference before clearing
        root = cls.root_window
        
        # Close all windows (except we'll quit the root separately)
        windows_to_close = list(cls.all_windows)
        for window in windows_to_close:
            try:
                # Save geometry before destroying
                if hasattr(window, 'save_window_geometry'):
                    window.save_window_geometry()
            except:
                pass
        
        cls.all_windows.clear()
        cls.root_window = None
        
        # Quit the main loop - this will close all windows
        if root:
            try:
                root.quit()
            except:
                pass
    
    @classmethod
    def run(cls):
        """Start the application with the first calculator window"""
        # Create first window
        first_window = cls.create_new_window()
        # Start main loop
        first_window.window.mainloop()


if __name__ == "__main__":
    MainApplication.run()
