"""
Calculator Window UI Module
Contains the OptionCalculatorWindow class with UI setup and event handlers
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
import threading
import os

import yahoo_data as yd
import option_service as svc
from config_manager import ConfigManager
from calculator_operations import CalculatorOperations
from utils import ThreadingHelper, FontManager, InputValidator, SuggestionWidget


class OptionCalculatorWindow(CalculatorOperations):
    """Individual window for a specific stock's option calculations"""
    
    def __init__(self, parent, ticker=None, window_index=0):
        # First window is Tk, subsequent windows are Toplevel
        if parent is None:
            self.window = tk.Tk()  # Root window
            self.root_window = self.window  # Store root reference
        else:
            self.window = tk.Toplevel(parent)  # Child window
            self.root_window = parent  # Store root reference for threading
        
        self.window.title("American Option Calculator")
        self.window.geometry("900x900")
        icon_dir = os.path.dirname(os.path.abspath(__file__))
        self._icon_imgs = []
        for size in (256, 48, 32, 16):
            fname = "app_icon.png" if size == 256 else f"app_icon_{size}.png"
            path = os.path.join(icon_dir, fname)
            if os.path.exists(path):
                self._icon_imgs.append(tk.PhotoImage(file=path))
        if self._icon_imgs:
            self.window.iconphoto(True, *self._icon_imgs)
        self.window_index = window_index  # Track which window this is (0-9)
        
        # Create menu bar
        self.create_menu()
        
        # Load configuration (always reload from disk to get latest values)
        self.config = ConfigManager.load_config()
        
        # Variables - explicitly pass self.window as master to avoid default root issues
        self.ticker = tk.StringVar(master=self.window, value=ticker if ticker else "")
        self.current_price = tk.StringVar(master=self.window, value="")
        self.strike_price = tk.StringVar(master=self.window, value="")
        self.expiration_date = tk.StringVar(master=self.window, value="")
        self.volatility = tk.StringVar(master=self.window, value="")
        self.risk_free_rate = tk.StringVar(master=self.window, value=str(self.config.get('risk_free_rate', 0.045)))
        self.option_type = tk.StringVar(master=self.window, value="call")
        self.calculated_price = tk.StringVar(master=self.window, value="--")
        self.dividend_yield = 0.0  # Store dividend yield as decimal (e.g., 0.02 for 2%)
        self.dividend_rate = tk.StringVar(master=self.window, value="0.00")  # Display variable for dividend rate %
        self.earnings_date = tk.StringVar(master=self.window, value="--")  # Display variable for earnings date
        self.all_dates_var = tk.BooleanVar(master=self.window, value=False)  # Show all expirations vs 6-month window
        
        # Radio button references for bold styling
        self.call_radio = None
        self.put_radio = None
        
        # Add trace to option_type to update bold styling
        self.option_type.trace('w', self.on_option_type_change)
        
        # Add trace to strike_price to update quick dates
        self.strike_price.trace('w', self.on_strike_price_change)
        
        # Add trace to expiration_date to auto-load data
        self.expiration_date.trace('w', self.on_expiration_date_change)
        
        # Add traces to auto-update calculated price when parameters change
        self.current_price.trace('w', lambda *args: self.update_calculated_price())
        self.volatility.trace('w', lambda *args: self.update_calculated_price())
        self.risk_free_rate.trace('w', lambda *args: self.update_calculated_price())
        self.dividend_rate.trace('w', lambda *args: self.update_calculated_price())
        
        # Search and suggestions
        self.search_timer = None
        self.suggestion_widget = None  # Will be initialized in create_widgets
        self._selecting_suggestion = False  # Flag to prevent search when clicking suggestion
        self._window_ready = False  # Flag to ensure window is ready before searches
        
        # Font size management
        self.font_size = self.config.get('font_size', 14)
        self.min_font_size = 6
        self.max_font_size = 36
        
        # Create GUI
        self.create_widgets()
        
        # Apply initial font sizes
        self.update_fonts()
        
        # Bind mouse wheel for font size adjustment AFTER widgets are created
        # Use after_idle to ensure all widgets are fully initialized
        self.window.after_idle(self.setup_mouse_wheel_binding)
        
        # If ticker provided, load data and dates
        if ticker:
            self.load_stock_data()
            self.load_expiration_dates()
        
        # Load and apply window geometry if this is the first window
        self.load_window_geometry()
        
        # Save geometry on window close
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Save geometry when window is moved or resized
        self.window.bind('<Configure>', self.on_window_configure)
        self._save_geometry_after_id = None  # For debouncing saves
        
        # Mark window as ready for searches
        self._window_ready = True
    
    def create_menu(self):
        """Create menu bar"""
        menubar = tk.Menu(self.window)
        self.window.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Window", command=self.create_new_window)
        file_menu.add_separator()
        file_menu.add_command(label="Close", command=self.on_closing)
        file_menu.add_command(label="Quit", command=self.quit_all)
    
    def create_new_window(self):
        """Create a new calculator window"""
        # Import here to avoid circular import
        from main import MainApplication
        MainApplication.create_new_window()
    
    def quit_all(self):
        """Quit the application - close all windows"""
        from main import MainApplication
        MainApplication.quit_all()
    
    def load_window_geometry(self):
        """Load and apply saved window geometry for this specific window"""
        ConfigManager.load_window_geometry(
            self.window, 
            self.config, 
            f'calculator_window_{self.window_index}',
            self.window_index
        )
    
    def save_window_geometry(self):
        """Save current window geometry for this specific window (0-9)"""
        # Reload config from disk first to merge with any changes from other windows
        current_config = ConfigManager.load_config()
        
        # Merge our config changes into the loaded config
        current_config.update(self.config)
        
        # Add geometry information with window-specific key
        current_config = ConfigManager.save_window_geometry(
            self.window,
            current_config,
            f'calculator_window_{self.window_index}'
        )
        
        # Save merged config
        ConfigManager.save_config(current_config)
        
        # Update our local copy
        self.config = current_config
    
    def on_closing(self):
        """Handle window close event"""
        # Cancel any pending save
        if self._save_geometry_after_id:
            self.window.after_cancel(self._save_geometry_after_id)
        self.save_window_geometry()
        
        # Unregister from MainApplication
        from main import MainApplication
        MainApplication.unregister_window(self)
        
        self.window.destroy()
    
    def on_window_configure(self, event):
        """Handle window move/resize events"""
        # Only process events for the window itself, not child widgets
        if event.widget == self.window:
            # Debounce saves - wait 500ms after last move/resize before saving
            if self._save_geometry_after_id:
                self.window.after_cancel(self._save_geometry_after_id)
            self._save_geometry_after_id = self.window.after(500, self.save_window_geometry)
    
    def save_config(self):
        """Save configuration to config.json"""
        # Reload config from disk first to merge with any changes from other windows
        current_config = ConfigManager.load_config()
        # Update with our changes
        current_config.update(self.config)
        # Save merged config
        ConfigManager.save_config(current_config)
        # Update our local copy
        self.config = current_config
    
    def setup_mouse_wheel_binding(self):
        """Set up mouse wheel binding after all widgets are created"""
        # Try multiple event types for cross-platform compatibility
        for event_type in ['<MouseWheel>', '<Button-4>', '<Button-5>']:
            self.window.bind(event_type, self.on_mouse_wheel, add='+')
    
    def on_mouse_wheel(self, event):
        """Handle Ctrl+mouse wheel for font size adjustment"""
        # Check for Control key - state & 4 for Control
        if not (event.state & 0x0004):
            return
        
        # Determine scroll direction - works for both Windows (delta) and Linux (num)
        delta = None
        if hasattr(event, 'delta') and event.delta != 0:
            delta = 1 if event.delta > 0 else -1
        elif hasattr(event, 'num'):
            delta = 1 if event.num == 4 else -1  # Button-4 is scroll up, Button-5 is scroll down
        
        if delta is None:
            return
        
        # Adjust font size using FontManager
        self.font_size = FontManager.adjust_font_size(
            self.font_size, delta, self.min_font_size, self.max_font_size
        )
        
        self.update_fonts()
        
        # Save font size to config
        self.config['font_size'] = self.font_size
        self.save_config()
    
    def on_mouse_wheel_with_scroll(self, event):
        """Handle mouse wheel on ScrolledText - either scroll or resize font"""
        # If Ctrl is pressed, adjust font size instead of scrolling
        if event.state & 0x0004:
            self.on_mouse_wheel(event)
            return "break"  # Prevent default scrolling
        # Let the default scrolling happen
        return

    
    def update_fonts(self):
        """Update all widget fonts"""
        # Update default fonts using FontManager
        FontManager.update_default_fonts(self.font_size)
        
        # Update bold font for headers
        bold_font = FontManager.get_bold_font(self.font_size)
        
        # Update results text
        if hasattr(self, 'results_text'):
            self.results_text.configure(font=FontManager.get_courier_font(self.font_size))
        
        # Update quick dates header labels
        if hasattr(self, 'quick_date_headers'):
            for header in self.quick_date_headers:
                header.configure(font=bold_font)
        
        # Update calculated price label
        if hasattr(self, 'calculated_price_label'):
            self.calculated_price_label.configure(font=bold_font)
        
        # Update option type radio buttons
        if hasattr(self, 'call_radio') and hasattr(self, 'put_radio'):
            if self.option_type.get() == "call":
                self.call_radio.config(font=('Arial', self.font_size, 'bold'))
                self.put_radio.config(font=('Arial', self.font_size))
            else:
                self.call_radio.config(font=('Arial', self.font_size))
                self.put_radio.config(font=('Arial', self.font_size, 'bold'))
        
        # Update suggestion widget fonts
        if self.suggestion_widget:
            self.suggestion_widget.update_font_size(self.font_size)
    
    def create_widgets(self):
        """Create all GUI widgets"""
        
        # Main frame
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Stock Information Section
        stock_frame = ttk.LabelFrame(main_frame, text="Stock Information", padding="10")
        stock_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(stock_frame, text="Ticker Symbol:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.ticker.trace('w', self.on_ticker_change)
        ticker_entry = ttk.Entry(stock_frame, textvariable=self.ticker, width=15)
        ticker_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        ticker_entry.bind('<Return>', lambda e: self.load_stock_data())
        
        # Suggestions frame for ticker autocomplete
        self.suggestions_frame = ttk.Frame(stock_frame)
        self.suggestions_frame.grid(row=2, column=0, columnspan=5, sticky=(tk.W, tk.E), pady=2)
        self.suggestions_frame.grid_remove()  # Hide initially
        
        # Initialize suggestion widget helper
        self.suggestion_widget = SuggestionWidget(
            self.suggestions_frame,
            font_size=self.font_size,
            max_name_length=50
        )
        
        ttk.Button(stock_frame, text="Load Stock Data", command=self.load_stock_data).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(stock_frame, text="Calculate Historical Vol", command=self.calculate_hist_vol).grid(row=0, column=3, padx=5, pady=5)
        
        ttk.Label(stock_frame, text="Current Stock Price:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(stock_frame, textvariable=self.current_price, width=15).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(stock_frame, text="Next Earnings:").grid(row=1, column=2, sticky=tk.W, padx=5, pady=5)
        ttk.Label(stock_frame, textvariable=self.earnings_date, width=15).grid(row=1, column=3, sticky=tk.W, padx=5, pady=5)
        
        # Option Parameters Section
        params_frame = ttk.LabelFrame(main_frame, text="Option Parameters", padding="10")
        params_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(params_frame, text="Option Type:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.call_radio = tk.Radiobutton(params_frame, text="Call", variable=self.option_type, value="call", indicatoron=1)
        self.call_radio.grid(row=0, column=1, sticky=tk.W, padx=5)
        self.put_radio = tk.Radiobutton(params_frame, text="Put", variable=self.option_type, value="put", indicatoron=1)
        self.put_radio.grid(row=0, column=2, sticky=tk.W, padx=5)
        
        ttk.Label(params_frame, text="Expiration Date (YYYY-MM-DD):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.expiration_combo = ttk.Combobox(params_frame, textvariable=self.expiration_date, width=13)
        self.expiration_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Checkbutton(params_frame, text="All", variable=self.all_dates_var,
                        command=self.load_expiration_dates).grid(row=1, column=2, sticky=tk.W, padx=5)
        ttk.Button(params_frame, text="Load Dates", command=self.load_expiration_dates).grid(row=1, column=3, padx=5, pady=5)
        
        ttk.Label(params_frame, text="Strike Price:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.strike_combo = ttk.Combobox(params_frame, textvariable=self.strike_price, width=13)
        self.strike_combo.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        self.strike_combo.bind('<<ComboboxSelected>>', lambda e: self.on_strike_change())
        
        ttk.Label(params_frame, text="Volatility (σ) %:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        volatility_entry = ttk.Entry(params_frame, textvariable=self.volatility, width=15)
        volatility_entry.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        volatility_entry.bind('<Return>', lambda e: self.on_volatility_change())
        volatility_entry.bind('<FocusOut>', lambda e: self.on_volatility_change())
        ttk.Label(params_frame, text="(e.g., 25.5 = 25.5%)").grid(row=3, column=2, sticky=tk.W, padx=5, pady=5)
        ttk.Button(params_frame, text="Get Implied Vol", command=self.get_implied_volatility).grid(row=3, column=3, padx=5, pady=5)
        
        ttk.Label(params_frame, text="Risk-Free Rate (r):").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        risk_free_entry = ttk.Entry(params_frame, textvariable=self.risk_free_rate, width=15)
        risk_free_entry.grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)
        risk_free_entry.bind('<Return>', lambda e: self.on_risk_free_rate_change())
        ttk.Button(params_frame, text="Save to Config", command=self.save_risk_free_rate).grid(row=4, column=2, padx=5, pady=5)
        
        ttk.Label(params_frame, text="Dividend Yield (q) %:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        dividend_entry = ttk.Entry(params_frame, textvariable=self.dividend_rate, width=15)
        dividend_entry.grid(row=5, column=1, sticky=tk.W, padx=5, pady=5)
        dividend_entry.bind('<Return>', lambda e: self.on_dividend_rate_change())
        dividend_entry.bind('<FocusOut>', lambda _: self.on_dividend_rate_change())
        ttk.Label(params_frame, text="(e.g., 2.5 = 2.5%)").grid(row=5, column=2, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(params_frame, text="Calculated Price:").grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        price_label = ttk.Label(
            params_frame,
            textvariable=self.calculated_price,
            font=FontManager.get_bold_font(self.font_size)
        )
        price_label.grid(row=6, column=1, sticky=tk.W, padx=5, pady=5)
        self.calculated_price_label = price_label
        
        # Quick Dates Section - Show 3 closest expiration dates
        quick_dates_frame = ttk.LabelFrame(main_frame, text="Quick View - Next 3 Expirations", padding="10")
        quick_dates_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Headers - store references for font updates
        self.quick_date_headers = []
        header1 = ttk.Label(
            quick_dates_frame,
            text="Expiry",
            font=FontManager.get_bold_font(self.font_size)
        )
        header1.grid(row=0, column=0, padx=10, pady=2)
        self.quick_date_headers.append(header1)
        
        header2 = ttk.Label(
            quick_dates_frame,
            text="Strike",
            font=FontManager.get_bold_font(self.font_size)
        )
        header2.grid(row=0, column=1, padx=10, pady=2)
        self.quick_date_headers.append(header2)
        
        header3 = ttk.Label(
            quick_dates_frame,
            text="IV",
            font=FontManager.get_bold_font(self.font_size)
        )
        header3.grid(row=0, column=2, padx=10, pady=2)
        self.quick_date_headers.append(header3)
        
        header4 = ttk.Label(
            quick_dates_frame,
            text="Fair Price",
            font=FontManager.get_bold_font(self.font_size)
        )
        header4.grid(row=0, column=3, padx=10, pady=2)
        self.quick_date_headers.append(header4)
        
        # Create variables and labels for 3 dates
        self.quick_date_vars = []
        for i in range(3):
            row_num = i + 1
            date_var = tk.StringVar(value="--")
            strike_var = tk.StringVar(value="--")
            iv_var = tk.StringVar(value="--")
            price_var = tk.StringVar(value="--")
            
            ttk.Label(quick_dates_frame, textvariable=date_var, width=10).grid(row=row_num, column=0, padx=10, pady=2)
            strike_entry = ttk.Entry(quick_dates_frame, textvariable=strike_var, width=10)
            strike_entry.grid(row=row_num, column=1, padx=10, pady=2)
            ttk.Label(quick_dates_frame, textvariable=iv_var, width=10).grid(row=row_num, column=2, padx=10, pady=2)
            ttk.Label(quick_dates_frame, textvariable=price_var, width=10).grid(row=row_num, column=3, padx=10, pady=2)
            
            # Bind strike entry to update price when changed
            strike_entry.bind('<FocusOut>', lambda e, idx=i: self.update_quick_date_price(idx))
            strike_entry.bind('<Return>', lambda e, idx=i: self.update_quick_date_price(idx))
            
            self.quick_date_vars.append({
                'date': date_var,
                'strike': strike_var,
                'iv_display': iv_var,
                'price': price_var,
                'full_date': ''  # Store full date for calculations
            })
        
        # Calculate Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=10)
        
        ttk.Button(button_frame, text="Calculate Option Price", command=self.calculate_option, 
                  style="Accent.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Calculate First 3 Dates", command=self.calculate_first_three_dates).pack(side=tk.LEFT, padx=5)
        
        # Results Section
        results_frame = ttk.LabelFrame(main_frame, text="Results", padding="10")
        results_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.results_text = scrolledtext.ScrolledText(
            results_frame,
            width=80,
            height=20,
            wrap=tk.WORD,
            font=FontManager.get_courier_font(self.font_size)
        )
        self.results_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Bind mouse wheel to results_text BEFORE general binding to intercept events
        self.results_text.bind('<MouseWheel>', self.on_mouse_wheel_with_scroll, add='+')
        
        # Configure grid weights
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(4, weight=1)
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
    
    def on_ticker_change(self, *args):
        """Called when ticker input changes - implements debouncing with autocomplete"""
        # Skip search if we're selecting a suggestion
        if self._selecting_suggestion:
            return
        
        # Skip if suggestion_widget not initialized yet
        if not hasattr(self, 'suggestion_widget') or self.suggestion_widget is None:
            return
        
        # Cancel previous timer if exists
        if self.search_timer:
            self.window.after_cancel(self.search_timer)
        
        query = self.ticker.get().strip()
        
        # Hide suggestions if input is empty or too short
        if len(query) < 1:
            self.hide_suggestions()
            return
        
        # Set new timer to search after 500ms pause
        self.search_timer = self.window.after(500, lambda: self.search_and_display_suggestions(query))
    
    def search_and_display_suggestions(self, query):
        """Search for tickers and display suggestions"""
        if not query:
            return
        
        def fetch_suggestions():
            return yd.search_ticker(query, max_results=10)
        
        # Use ThreadingHelper for async operation - use root window for callbacks
        ThreadingHelper.run_async_with_ui_update(
            fetch_suggestions,
            self.display_ticker_suggestions,
            self.root_window
        )
    
    def display_ticker_suggestions(self, results):
        """Display ticker suggestions using SuggestionWidget"""
        self.suggestion_widget.display_suggestions(results, self.select_suggestion)
    
    def select_suggestion(self, symbol):
        """Select a suggestion and load data"""
        self._selecting_suggestion = True
        self.ticker.set(symbol)
        self.suggestion_widget.hide_suggestions()
        self.load_stock_data()
        # Clear flag after a short delay to allow load_stock_data to complete
        self.window.after(100, lambda: setattr(self, '_selecting_suggestion', False))
        self.load_expiration_dates()
    
    def hide_suggestions(self):
        """Hide the suggestions frame"""
        self.suggestion_widget.hide_suggestions()
    
    def on_strike_price_change(self, *args):
        """Update quick dates strikes when main strike price changes"""
        strike_str = self.strike_price.get().strip()
        if not strike_str or not hasattr(self, 'quick_date_vars'):
            return
        
        try:
            strike = float(strike_str)
            # Update all 3 quick date strikes and recalculate prices
            for i in range(len(self.quick_date_vars)):
                self.quick_date_vars[i]['strike'].set(f"{strike:.2f}")
                self.update_quick_date_price(i)
            
            # Also update the calculated price
            self.update_calculated_price()
        except ValueError:
            pass  # Ignore invalid strike values
    
    def on_option_type_change(self, *args):
        """Update radio button fonts when option type changes"""
        if not self.call_radio or not self.put_radio:
            return
        
        if self.option_type.get() == "call":
            self.call_radio.config(font=('Arial', self.font_size, 'bold'))
            self.put_radio.config(font=('Arial', self.font_size))
        else:
            self.call_radio.config(font=('Arial', self.font_size))
            self.put_radio.config(font=('Arial', self.font_size, 'bold'))
        
        # Update calculated price when option type changes
        self.update_calculated_price()

        # Reload quick view using the new option type's IV/prices
        if self.ticker.get().strip() and self.current_price.get().strip():
            self.load_expiration_dates_silent()
    
    def on_volatility_change(self):
        """Recalculate the option price when volatility is manually changed"""
        self.update_calculated_price()
    
    def on_risk_free_rate_change(self):
        """Update prices when risk-free rate is manually changed"""
        if not hasattr(self, 'quick_date_vars'):
            return
        
        # Recalculate all quick date prices with new risk-free rate
        for i in range(len(self.quick_date_vars)):
            self.update_quick_date_price(i)
        
        # Update calculated price with new risk-free rate
        self.update_calculated_price()
    
    def on_dividend_rate_change(self):
        """Handle dividend rate change from user input"""
        try:
            # Get dividend rate as percentage and convert to decimal
            div_rate_pct = float(self.dividend_rate.get())
            self.dividend_yield = div_rate_pct / 100
        except ValueError:
            # If invalid, keep current value
            pass
        
        # Recalculate all quick date prices with new dividend rate
        for i in range(len(self.quick_date_vars)):
            self.update_quick_date_price(i)
        
        # Update calculated price with new dividend rate
        self.update_calculated_price()
    
    def update_calculated_price(self):
        """Calculate and update the price display"""
        try:
            # Get all required parameters
            S = float(self.current_price.get())
            K = float(self.strike_price.get())
            exp_date = self.expiration_date.get().strip()
            sigma = float(self.volatility.get()) / 100
            r = float(self.risk_free_rate.get())
            opt_type = self.option_type.get()
            
            # Get dividend yield from field (in case user edited it)
            try:
                q = float(self.dividend_rate.get()) / 100
            except ValueError:
                q = self.dividend_yield
            
            price = svc.price_option(S, K, exp_date, sigma, r, q, opt_type)['price']
            self.calculated_price.set(f"${price:.2f}")
            
        except (ValueError, TypeError):
            self.calculated_price.set("--")
    
    def on_expiration_date_change(self, *args):
        """Handle expiration date change - auto-load strike and IV"""
        ticker = self.ticker.get().strip().upper()
        exp_date = self.expiration_date.get().strip()
        current_price_str = self.current_price.get().strip()
        
        # Only proceed if we have all required data
        if not ticker or not exp_date or not current_price_str:
            return
        
        try:
            current_price = float(current_price_str)
        except ValueError:
            return
        
        # Clear fields
        self.volatility.set("")
        self.results_text.delete(1.0, tk.END)
        
        # Clear quick view
        if hasattr(self, 'quick_date_vars'):
            for i in range(len(self.quick_date_vars)):
                self.quick_date_vars[i]['strike'].set("--")
                self.quick_date_vars[i]['price'].set("--")
        
        self.results_text.insert(tk.END, f"Loading option data for {exp_date}...\n")
        
        def fetch_and_populate():
            # Get options for the selected expiration
            options = yd.get_options_for_expiration(ticker, exp_date)
            
            if options['success']:
                opt_type = self.option_type.get()
                chain_data = options['calls'] if opt_type == 'call' else options['puts']

                # Find best strike (at/above ATM) + its IV, and ±10 strike window
                r_val = float(self.risk_free_rate.get())
                T_exp = yd.get_years_to_expiration(exp_date)
                best_strike, best_iv, strikes = svc.find_atm_strike_with_iv(
                    chain_data, current_price, T_exp, r_val, opt_type
                )
                nearby_strikes, _ = svc.atm_strikes_window(strikes, current_price)

                if best_strike:
                    # Update strike price - this will trigger on_strike_price_change
                    self.strike_price.set(str(best_strike))
                    self.strike_combo['values'] = nearby_strikes

                    # Set IV
                    if best_iv and best_iv > 0:
                        iv_pct = best_iv * 100
                        self.volatility.set(f"{iv_pct:.2f}")
                        self.results_text.insert(tk.END, f"Strike: ${best_strike:.2f}\n")
                        self.results_text.insert(tk.END, f"Implied Volatility: {iv_pct:.2f}%\n")
                    else:
                        self.results_text.insert(tk.END, f"Strike: ${best_strike:.2f}\n")
                        self.results_text.insert(tk.END, "No implied volatility available\n")
                    
                    # Reload quick view with new dates
                    self.load_expiration_dates_silent()
                else:
                    self.results_text.insert(tk.END, "No strikes available for this expiration\n")
            else:
                self.results_text.insert(tk.END, f"Error loading options: {options.get('error', 'Unknown error')}\n")
        
        threading.Thread(target=fetch_and_populate, daemon=True).start()
