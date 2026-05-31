"""
Threading Helper Utility
Provides utilities for running functions in background threads with UI updates
"""

import threading
from typing import Callable, Optional, Any


class ThreadingHelper:
    """Helper class for managing background threading operations"""
    
    @staticmethod
    def run_async(func: Callable, daemon: bool = True) -> threading.Thread:
        """
        Run a function in a background thread
        
        Args:
            func: Function to run in background
            daemon: Whether thread should be daemon (default True)
            
        Returns:
            The created Thread object
        """
        thread = threading.Thread(target=func, daemon=daemon)
        thread.start()
        return thread
    
    @staticmethod
    def run_async_with_ui_update(
        fetch_func: Callable[[], Any],
        update_func: Callable[[Any], None],
        window,
        daemon: bool = True
    ) -> threading.Thread:
        """
        Run a fetch function in background, then update UI with result
        
        Args:
            fetch_func: Function to run in background (returns data)
            update_func: Function to call in main thread with fetched data
            window: Tkinter window object (for after() method)
            daemon: Whether thread should be daemon (default True)
            
        Returns:
            The created Thread object
        """
        def wrapper():
            try:
                result = fetch_func()
                # Schedule UI update in main thread - with error handling
                try:
                    window.after(0, lambda: update_func(result))
                except RuntimeError:
                    # Window may have been destroyed or main loop not running
                    pass
            except Exception:
                # Silently ignore errors in background thread
                pass
        
        return ThreadingHelper.run_async(wrapper, daemon=daemon)
    
    @staticmethod
    def run_async_simple(
        func: Callable,
        window,
        daemon: bool = True
    ) -> threading.Thread:
        """
        Simplified async runner for functions that handle their own UI updates
        
        Args:
            func: Function to run in background
            window: Tkinter window object (passed for consistency)
            daemon: Whether thread should be daemon (default True)
            
        Returns:
            The created Thread object
        """
        return ThreadingHelper.run_async(func, daemon=daemon)
