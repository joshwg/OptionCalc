"""
Test Ticker Search in Multiple Windows
Tests that ticker autocomplete search works in both the first window and secondary windows
"""

import tkinter as tk
import time
from main import MainApplication

def test_ticker_search():
    """Test ticker search functionality in multiple windows"""
    
    print("Starting ticker search test...")
    
    # Create first window
    print("\n1. Creating first window (root)...")
    window1 = MainApplication.create_new_window()
    
    # Give window time to initialize
    window1.window.update()
    time.sleep(0.5)
    
    # Test search in first window
    print("2. Testing ticker search in first window...")
    print(f"   - Window index: {window1.window_index}")
    print(f"   - Window type: {type(window1.window).__name__}")
    print(f"   - Root window: {type(window1.root_window).__name__}")
    print(f"   - Has suggestion_widget: {hasattr(window1, 'suggestion_widget')}")
    print(f"   - Suggestion widget initialized: {window1.suggestion_widget is not None}")
    
    # Simulate typing in first window
    print("3. Simulating typing 'AAPL' in first window...")
    window1.ticker.set("AAPL")
    window1.window.update()
    time.sleep(1)  # Wait for debounce timer and async search
    
    # Create second window
    print("\n4. Creating second window...")
    window2 = MainApplication.create_new_window()
    window2.window.update()
    time.sleep(0.5)
    
    # Test search in second window
    print("5. Testing ticker search in second window...")
    print(f"   - Window index: {window2.window_index}")
    print(f"   - Window type: {type(window2.window).__name__}")
    print(f"   - Root window: {type(window2.root_window).__name__}")
    print(f"   - Root window same as first? {window2.root_window == window1.root_window}")
    print(f"   - Has suggestion_widget: {hasattr(window2, 'suggestion_widget')}")
    print(f"   - Suggestion widget initialized: {window2.suggestion_widget is not None}")
    
    # Simulate typing in second window
    print("6. Simulating typing 'MSFT' in second window...")
    window2.ticker.set("MSFT")
    window2.window.update()
    time.sleep(1)  # Wait for debounce timer and async search
    
    # Create third window
    print("\n7. Creating third window...")
    window3 = MainApplication.create_new_window()
    window3.window.update()
    time.sleep(0.5)
    
    # Test search in third window
    print("8. Testing ticker search in third window...")
    print(f"   - Window index: {window3.window_index}")
    print(f"   - Window type: {type(window3.window).__name__}")
    print(f"   - Root window: {type(window3.root_window).__name__}")
    print(f"   - Has suggestion_widget: {hasattr(window3, 'suggestion_widget')}")
    print(f"   - Suggestion widget initialized: {window3.suggestion_widget is not None}")
    
    # Simulate typing in third window
    print("9. Simulating typing 'TSLA' in third window...")
    window3.ticker.set("TSLA")
    window3.window.update()
    time.sleep(1)  # Wait for debounce timer and async search
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Total windows created: {len(MainApplication.all_windows)}")
    print(f"Window 1 (root): {window1.window_index}, Type: {type(window1.window).__name__}")
    print(f"Window 2: {window2.window_index}, Type: {type(window2.window).__name__}")
    print(f"Window 3: {window3.window_index}, Type: {type(window3.window).__name__}")
    print(f"\nAll windows share same root: {window1.root_window == window2.root_window == window3.root_window}")
    
    print("\n" + "="*60)
    print("MANUAL TEST INSTRUCTIONS")
    print("="*60)
    print("1. Type in the ticker field of each window")
    print("2. Verify suggestions appear below the ticker field")
    print("3. Try typing 'AA' or 'MS' to see multiple suggestions")
    print("4. Verify you can click suggestions to select them")
    print("5. Close this message and test manually")
    print("\nPress Ctrl+C in terminal to stop the test")
    print("="*60)
    
    # Keep windows open for manual testing
    try:
        window1.window.mainloop()
    except KeyboardInterrupt:
        print("\nTest interrupted by user")

if __name__ == "__main__":
    test_ticker_search()
