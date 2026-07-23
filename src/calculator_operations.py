"""
Calculator Operations Module
Contains all calculation and data fetching methods for the Option Calculator
"""

import tkinter as tk
from tkinter import messagebox
from datetime import datetime

import option_pricing as bs  # noqa: F401 (re-exported for callers that import via this module)
import option_service as svc
from option_lib.data_provider import get_provider
from option_lib.math_util import get_days_to_expiration, get_years_to_expiration
from utils import ThreadingHelper, InputValidator


class CalculatorOperations:
    """Mixin class containing all calculation and data operations"""

    def _fetch_expirations(self, ticker: str) -> dict:
        """Return expiration dates, respecting the 'All dates' checkbox."""
        all_dates = getattr(self, 'all_dates_var', None) and self.all_dates_var.get()
        return svc.fetch_expirations(ticker, all_dates=bool(all_dates))

    def load_stock_data(self):
        """Load stock data from Yahoo Finance"""
        ticker = InputValidator.validate_ticker(self.ticker.get())
        if not ticker:
            return
        
        # Hide suggestions when loading data
        self.hide_suggestions()
        self.set_status(f"Loading {ticker}…")

        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, f"Loading data for {ticker}...\n")

        def fetch_data():
            try:
                provider = get_provider()
                info = provider.get_stock_info(ticker)

                if info['success']:
                    current_price = info['current_price']
                    self.current_price.set(str(current_price))
                    self.dividend_yield = info.get('dividend_yield', 0) or 0
                    div_yield_pct = self.dividend_yield * 100
                    self.dividend_rate.set(f"{div_yield_pct:.2f}")
                    # Update earnings date display
                    earnings_date = info.get('earnings_date') or "unavailable"
                    self.earnings_date.set(earnings_date)
                    self.window.title(f"Option Calculator - {info['company_name']} ({ticker})")
                    self.set_status(f"{info['company_name']}  •  ${current_price:.2f}")

                    self.results_text.delete(1.0, tk.END)
                    self.results_text.insert(tk.END, f"Company: {info['company_name']}\n")
                    self.results_text.insert(tk.END, f"Current Price: ${current_price:.2f}\n")
                    self.results_text.insert(tk.END, f"Previous Close: ${info.get('previous_close', 'N/A')}\n")
                    self.results_text.insert(tk.END, f"Volume: {info.get('volume', 'N/A')}\n")
                    div_yield_pct = self.dividend_yield * 100
                    self.results_text.insert(tk.END, f"Dividend Yield: {div_yield_pct:.2f}%\n")
                    # Display earnings date (always show, use "unavailable" if not found)
                    earnings_date = info.get('earnings_date') or "unavailable"
                    self.results_text.insert(tk.END, f"Next Earnings: {earnings_date}\n")
                    self.results_text.insert(tk.END, "\n")

                    # Auto-fill expiration date, strike, and implied volatility
                    self.results_text.insert(tk.END, "Loading option data...\n")

                    # Get first available expiration date (filtered to exclude today after market close)
                    chain = self._fetch_expirations(ticker)
                    if chain['success'] and chain['expirations']:
                        first_exp = chain['expirations'][0]
                        self.expiration_date.set(first_exp)
                        self.results_text.insert(tk.END, f"First expiration: {first_exp}\n")

                        # Get options for that expiration
                        options = provider.get_options_for_expiration(ticker, first_exp)
                        if options['success']:
                            # Find strike closest to but above current price
                            opt_type = self.option_type.get()
                            chain_data = options['calls'] if opt_type == 'call' else options['puts']

                            # Find best strike (at/above ATM) + its IV, and ±10 strike window
                            r_val = float(self.risk_free_rate.get())
                            T_first = get_years_to_expiration(first_exp)
                            best_strike, best_iv, all_strikes = svc.find_atm_strike_with_iv(
                                chain_data, current_price, T_first, r_val, opt_type
                            )
                            selected_strikes, _ = svc.atm_strikes_window(all_strikes, current_price)

                            # Populate strike combobox
                            self.strike_combo['values'] = selected_strikes
                            self.results_text.insert(tk.END, f"Loaded {len(selected_strikes)} strike prices\n")

                            if best_strike:
                                self.strike_price.set(str(best_strike))
                                self.results_text.insert(tk.END, f"Strike price: ${best_strike:.2f}\n")

                                if best_iv and best_iv > 0:
                                    iv_pct = best_iv * 100
                                    self.volatility.set(f"{iv_pct:.2f}")
                                    self.results_text.insert(tk.END, f"Implied Volatility: {iv_pct:.2f}%\n")
                                else:
                                    self.results_text.insert(tk.END, "No implied volatility available\n")

                            # Update calculated price after loading all parameters
                            self.window.after(200, lambda: self.update_calculated_price())

                            self.results_text.insert(tk.END, "\nReady to calculate option price!\n")
                        else:
                            self.results_text.insert(tk.END, "Could not load option chain data\n")

                        # Also load available dates for 6 months
                        self.window.after(100, lambda: self.load_expiration_dates_silent())
                    else:
                        self.results_text.insert(tk.END, "No option expirations available\n")
                else:
                    messagebox.showerror("Error", f"Failed to load stock data: {info.get('error', 'Unknown error')}")
            except Exception as e:
                self.set_status(f"Error loading {ticker}: {e}")

        ThreadingHelper.run_async_simple(fetch_data, self.root_window)
    
    def load_expiration_dates_silent(self):
        """Load expiration dates silently without displaying messages"""
        ticker = InputValidator.validate_ticker(self.ticker.get(), show_error=False)
        if not ticker:
            return
        
        def fetch_dates():
            try:
                self.set_status("Loading expiration dates…")
                chain = self._fetch_expirations(ticker)

                if chain['success']:
                    dates = chain['expirations']
                    if dates:
                        self.expiration_combo['values'] = dates
                        self.set_status(f"{len(dates)} expiration dates loaded")

                        # Populate quick dates section with first 3 expirations
                        # Only populate if a strike price has been selected
                        strike_str = self.strike_price.get().strip()
                        strike_to_use = None
                        if strike_str:
                            try:
                                strike_to_use = float(strike_str)
                            except ValueError:
                                pass

                        # Get current price for ATM IV lookup
                        try:
                            current_price = float(self.current_price.get())
                        except ValueError:
                            current_price = None

                        opt_type = self.option_type.get()

                        # Get earnings date for marking closest expiration after earnings
                        earnings_date_str = self.earnings_date.get()
                        earnings_date_obj = None
                        if earnings_date_str and earnings_date_str != "--" and earnings_date_str != "unavailable":
                            try:
                                earnings_date_obj = datetime.strptime(earnings_date_str, '%Y-%m-%d')
                            except ValueError:
                                pass

                        closest_after_earnings_idx = svc.find_post_earnings_expiration(
                            dates, earnings_date_obj
                        )

                        type_suffix = 'c' if opt_type == 'call' else 'p'
                        provider = get_provider()

                        for i, exp_date in enumerate(dates[:3]):  # Take first 3 dates
                            if i < len(self.quick_date_vars):
                                # Format date as MM/DD/YY + c/p suffix
                                try:
                                    date_obj = datetime.strptime(exp_date, '%Y-%m-%d')
                                    formatted_date = date_obj.strftime('%m/%d/%y') + type_suffix
                                    # Add asterisk prefix if this is the closest expiration after earnings
                                    if closest_after_earnings_idx is not None and i == closest_after_earnings_idx:
                                        formatted_date = "*" + formatted_date
                                except ValueError:
                                    formatted_date = exp_date

                                # Set the date
                                self.quick_date_vars[i]['date'].set(formatted_date)
                                self.quick_date_vars[i]['full_date'] = exp_date

                                # Fetch ATM IV; fall back to main volatility field if unavailable or too low
                                iv = None
                                if current_price:
                                    try:
                                        r_val = float(self.risk_free_rate.get())
                                    except (ValueError, AttributeError):
                                        r_val = 0.045
                                    fetched = provider.get_atm_implied_volatility(ticker, exp_date, current_price, opt_type, r=r_val)
                                    if fetched and fetched > 0.05:
                                        iv = fetched
                                if iv is None:
                                    try:
                                        main_vol = float(self.volatility.get()) / 100
                                        iv = main_vol if main_vol > 0 else None
                                    except (ValueError, AttributeError):
                                        iv = None
                                if iv:
                                    self.quick_date_vars[i]['iv'] = iv
                                    self.quick_date_vars[i]['iv_display'].set(f"{iv*100:.2f}%")
                                else:
                                    self.quick_date_vars[i]['iv'] = None
                                    self.quick_date_vars[i]['iv_display'].set("--")

                                # Set strike only if strike price is selected
                                if strike_to_use:
                                    self.quick_date_vars[i]['strike'].set(f"{strike_to_use:.2f}")
                                    # Calculate theoretical price
                                    self.update_quick_date_price(i)
                                else:
                                    self.quick_date_vars[i]['strike'].set("--")
                                    self.quick_date_vars[i]['iv_display'].set("--")
                                    self.quick_date_vars[i]['price'].set("--")
            except Exception as e:
                self.set_status(f"Error: {e}")

        ThreadingHelper.run_async_simple(fetch_dates, self.root_window)
    
    def calculate_hist_vol(self):
        """Calculate historical volatility"""
        ticker = InputValidator.validate_ticker(self.ticker.get())
        if not ticker:
            return
        
        self.results_text.insert(tk.END, "\nCalculating historical volatility...\n")
        
        def fetch_vol():
            try:
                vol = get_provider().calculate_historical_volatility(ticker, period='1y')
                if vol:
                    vol_pct = vol * 100
                    self.volatility.set(f"{vol_pct:.2f}")
                    self.results_text.insert(tk.END, f"Historical Volatility (1 year): {vol_pct:.2f}%\n")
                else:
                    messagebox.showerror("Error", "Failed to calculate historical volatility")
            except Exception as e:
                self.set_status(f"Error: {e}")

        ThreadingHelper.run_async_simple(fetch_vol, self.root_window)
    
    def get_implied_volatility(self):
        """Get implied volatility from market option prices"""
        ticker = InputValidator.validate_ticker(self.ticker.get())
        exp_date = InputValidator.validate_date(self.expiration_date.get().strip())
        strike_str = self.strike_price.get().strip()
        current_price_str = self.current_price.get().strip()
        opt_type = self.option_type.get()
        
        # Validate inputs
        if not ticker or not exp_date:
            return
        
        # If strike is provided, get IV for that specific strike
        if strike_str:
            strike = InputValidator.validate_float(strike_str, "strike price")
            if strike is None:
                return
            
            self.results_text.insert(tk.END, f"\nGetting implied volatility for {ticker} ${strike} {opt_type}...\n")
            
            def fetch_iv_strike():
                try:
                    iv = get_provider().get_implied_volatility_for_strike(ticker, exp_date, strike, opt_type)
                    if iv:
                        iv_pct = iv * 100
                        self.volatility.set(f"{iv_pct:.2f}")
                        self.results_text.insert(tk.END, f"Implied Volatility (${strike} {opt_type}): {iv_pct:.2f}%\n")
                    else:
                        messagebox.showerror("Error", "Failed to get implied volatility. Check ticker, date, and strike.")
                except Exception as e:
                    self.set_status(f"Error: {e}")

            ThreadingHelper.run_async_simple(fetch_iv_strike, self.root_window)
        
        # If no strike but have current price, get ATM implied vol
        elif current_price_str:
            current_price = InputValidator.validate_float(current_price_str, "current price")
            if current_price is None:
                return
            
            self.results_text.insert(tk.END, f"\nGetting ATM implied volatility for {ticker}...\n")
            
            def fetch_iv_atm():
                try:
                    iv = get_provider().get_atm_implied_volatility(ticker, exp_date, current_price, opt_type)
                    if iv:
                        avg_iv = iv * 100
                        self.volatility.set(f"{avg_iv:.2f}")
                        self.results_text.insert(tk.END, f"ATM Implied Volatility: {avg_iv:.2f}%\n")
                    else:
                        messagebox.showerror("Error", "Failed to get implied volatility. Check ticker and expiration date.")
                except Exception as e:
                    self.set_status(f"Error: {e}")

            ThreadingHelper.run_async_simple(fetch_iv_atm, self.root_window)
        
        else:
            messagebox.showwarning("Input Error", "Please enter either a strike price or load current stock price first")
    
    def load_expiration_dates(self):
        """Load expiration dates for next 6 months into combobox"""
        ticker = InputValidator.validate_ticker(self.ticker.get())
        if not ticker:
            return
        
        self.results_text.insert(tk.END, f"\nLoading expiration dates for {ticker}...\n")
        
        def fetch_dates():
            self.set_status("Loading expiration dates…")
            chain = self._fetch_expirations(ticker)

            if chain['success']:
                dates = chain['expirations']
                if dates:
                    self.expiration_combo['values'] = dates
                    self.set_status(f"{len(dates)} expiration dates loaded")
                    self.results_text.insert(tk.END, f"Loaded {len(dates)} expiration dates.\n")
                    self.results_text.insert(tk.END, "Select from dropdown or type a date manually.\n")
                else:
                    self.results_text.insert(tk.END, "No expirations found in next 6 months.\n")
            else:
                messagebox.showerror("Error", f"Failed to get option dates: {chain.get('error', 'Unknown error')}")
        
        ThreadingHelper.run_async_simple(fetch_dates, self.root_window)
    
    def show_expiration_dates(self):
        """Show available option expiration dates"""
        ticker = InputValidator.validate_ticker(self.ticker.get())
        if not ticker:
            return
        
        def fetch_dates():
            try:
                chain = get_provider().get_option_chain(ticker)
                if chain['success']:
                    dates_str = "\n".join(chain['expirations'])
                    self.results_text.delete(1.0, tk.END)
                    self.results_text.insert(tk.END, f"Available expiration dates for {ticker}:\n\n{dates_str}\n")
                else:
                    messagebox.showerror("Error", f"Failed to get option chain: {chain.get('error', 'Unknown error')}")
            except Exception as e:
                self.set_status(f"Error: {e}")

        ThreadingHelper.run_async_simple(fetch_dates, self.root_window)
    
    def on_strike_change(self):
        """Automatically load implied volatility when strike price changes"""
        ticker = self.ticker.get().strip().upper()
        exp_date = self.expiration_date.get().strip()
        strike_str = self.strike_price.get().strip()
        opt_type = self.option_type.get()
        current_price_str = self.current_price.get().strip()
        
        # Only proceed if we have all required fields
        if not ticker or not exp_date or not strike_str or not current_price_str:
            return
        
        try:
            strike = float(strike_str)
            current_price = float(current_price_str)
            
            # Clear results
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, f"Loading data for {ticker} ${strike} {opt_type}...\n")
            
            def fetch_and_calculate():
                try:
                    # Get IV for this strike computed from bid/ask mid
                    iv = get_provider().get_implied_volatility_for_strike(
                        ticker, exp_date, strike, opt_type,
                        S=current_price, r=float(self.risk_free_rate.get())
                    )

                    if iv:
                        iv_pct = iv * 100
                        self.volatility.set(f"{iv_pct:.2f}")
                        self.results_text.insert(tk.END, f"Implied Volatility: {iv_pct:.2f}%\n\n")

                        # Calculate option price for selected expiration/strike
                        try:
                            S = current_price
                            K = strike
                            r = float(self.risk_free_rate.get())

                            # Get dividend yield from field
                            q = InputValidator.get_dividend_yield(self.dividend_rate.get(), self.dividend_yield)

                            result = svc.price_option(S, K, exp_date, iv, r, q, opt_type)
                            price  = result['price']
                            T      = result['T']
                            greeks = result['greeks']

                            # Display results
                            self.results_text.insert(tk.END, f"Selected Option: {ticker} ${K:.2f} {opt_type.upper()}\n")
                            self.results_text.insert(tk.END, f"Expiration: {exp_date}\n")
                            self.results_text.insert(tk.END, f"Days to Expiration: {get_days_to_expiration(exp_date)}\n\n")
                            self.results_text.insert(tk.END, f"Theoretical Price: ${price:.2f}\n\n")
                            self.results_text.insert(tk.END, "Greeks:\n")
                            self.results_text.insert(tk.END, f"  Delta: {greeks['delta']:.4f}\n")
                            self.results_text.insert(tk.END, f"  Gamma: {greeks['gamma']:.4f}\n")
                            self.results_text.insert(tk.END, f"  Theta: {greeks['theta']:.4f}\n")
                            self.results_text.insert(tk.END, f"  Vega: {greeks['vega']:.4f}\n")
                            self.results_text.insert(tk.END, f"  Rho: {greeks['rho']:.4f}\n")

                            # Update calculated price display
                            self.calculated_price.set(f"${price:.2f}")

                        except Exception as e:
                            self.results_text.insert(tk.END, f"Error calculating option price: {e}\n")
                            self.calculated_price.set("Error")

                        # Update quick view (reload dates with current strike)
                        self.load_expiration_dates_silent()
                    else:
                        self.results_text.insert(tk.END, "No implied volatility available for this strike\n")
                        self.calculated_price.set("No IV")
                except Exception as e:
                    self.set_status(f"Error: {e}")

            ThreadingHelper.run_async_simple(fetch_and_calculate, self.root_window)
            
        except ValueError:
            pass  # Silently ignore invalid strike price
    
    def update_quick_date_price(self, row_idx):
        """Calculate and update the option price for a quick date row"""
        try:
            # Get current stock price
            S = float(self.current_price.get())
            
            # Get strike from the quick date row
            strike_str = self.quick_date_vars[row_idx]['strike'].get().strip()
            if not strike_str or strike_str == "--":
                self.quick_date_vars[row_idx]['price'].set("--")
                return
            K = float(strike_str)
            
            # Get expiration date
            exp_date = self.quick_date_vars[row_idx]['full_date']
            if not exp_date:
                self.quick_date_vars[row_idx]['price'].set("--")
                return
            
            # Get volatility - use expiration-specific IV if available
            if 'iv' in self.quick_date_vars[row_idx] and self.quick_date_vars[row_idx]['iv'] is not None:
                sigma = self.quick_date_vars[row_idx]['iv']
            else:
                # Fall back to the main volatility field
                sigma = float(self.volatility.get()) / 100
            
            # Get risk-free rate
            r = float(self.risk_free_rate.get())
            
            # Get option type
            opt_type = self.option_type.get()

            # Get dividend yield from field
            q = InputValidator.get_dividend_yield(self.dividend_rate.get(), self.dividend_yield)

            price = svc.price_option(S, K, exp_date, sigma, r, q, opt_type)['price']

            # Update the price display
            self.quick_date_vars[row_idx]['price'].set(f"${price:.2f}")
            
        except (ValueError, TypeError):
            self.quick_date_vars[row_idx]['price'].set("--")
    
    def calculate_option(self):
        """Calculate option price using American binomial model"""
        try:
            # Get parameters
            S = float(self.current_price.get())
            K = float(self.strike_price.get())
            exp_date = self.expiration_date.get().strip()
            sigma = float(self.volatility.get()) / 100  # Convert percentage to decimal
            r = float(self.risk_free_rate.get())
            opt_type = self.option_type.get()
            
            T = get_years_to_expiration(exp_date)
            if T <= 0:
                messagebox.showwarning("Warning", "Option has expired or expiration date is invalid")
                return

            # Get dividend yield from field
            q = InputValidator.get_dividend_yield(self.dividend_rate.get(), self.dividend_yield)

            result = svc.price_option(S, K, exp_date, sigma, r, q, opt_type)
            T      = result['T']
            days   = result['days']
            price  = result['price']
            greeks = result['greeks']

            # Display results
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, "=" * 60 + "\n")
            self.results_text.insert(tk.END, "AMERICAN OPTION VALUATION (Binomial Model)\n")
            self.results_text.insert(tk.END, "=" * 60 + "\n\n")
            
            self.results_text.insert(tk.END, "INPUT PARAMETERS:\n")
            self.results_text.insert(tk.END, f"  Ticker:              {self.ticker.get().upper()}\n")
            self.results_text.insert(tk.END, f"  Option Type:         {opt_type.upper()}\n")
            self.results_text.insert(tk.END, f"  Stock Price (S):     ${S:.2f}\n")
            self.results_text.insert(tk.END, f"  Strike Price (K):    ${K:.2f}\n")
            self.results_text.insert(tk.END, f"  Expiration Date:     {exp_date} ({days} days)\n")
            self.results_text.insert(tk.END, f"  Time to Expiration:  {T:.4f} years\n")
            self.results_text.insert(tk.END, f"  Volatility (σ):      {sigma*100:.2f}%\n")
            self.results_text.insert(tk.END, f"  Risk-Free Rate (r):  {r:.4f} ({r*100:.2f}%)\n")
            q_pct = q * 100
            self.results_text.insert(tk.END, f"  Dividend Yield (q):  {q_pct:.2f}%\n\n")
            
            self.results_text.insert(tk.END, "VALUATION RESULTS:\n")
            self.results_text.insert(tk.END, f"  Option Price:        ${price:.4f}\n\n")
            
            self.results_text.insert(tk.END, "THE GREEKS:\n")
            self.results_text.insert(tk.END, f"  Delta (Δ):           {greeks['delta']:.4f}\n")
            self.results_text.insert(tk.END, f"  Gamma (Γ):           {greeks['gamma']:.4f}\n")
            self.results_text.insert(tk.END, f"  Theta (Θ):           {greeks['theta']:.4f} (per day)\n")
            self.results_text.insert(tk.END, f"  Vega (ν):            {greeks['vega']:.4f} (per 1% change)\n")
            self.results_text.insert(tk.END, f"  Rho (ρ):             {greeks['rho']:.4f} (per 1% change)\n\n")
            
            self.results_text.insert(tk.END, "=" * 60 + "\n")
            
        except ValueError as e:
            messagebox.showerror("Input Error", "Please ensure all numeric fields are filled with valid numbers")
        except Exception as e:
            messagebox.showerror("Calculation Error", f"An error occurred: {str(e)}")
    
    def calculate_first_three_dates(self):
        """Calculate option prices for first 3 available expiration dates"""
        try:
            # Get parameters
            S = float(self.current_price.get())
            K = float(self.strike_price.get())
            sigma = float(self.volatility.get()) / 100  # Convert percentage to decimal (fallback)
            r = float(self.risk_free_rate.get())
            ticker = InputValidator.validate_ticker(self.ticker.get())
            if not ticker:
                return
            opt_type = self.option_type.get()
            
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, f"Calculating {opt_type} option prices for first 3 expiration dates...\n\n")
            
            def calculate_multi():
                try:
                    # Get expiration dates
                    chain = self._fetch_expirations(ticker)

                    if not chain['success']:
                        messagebox.showerror("Error", f"Failed to get option dates: {chain.get('error', 'Unknown error')}")
                        return

                    dates = chain['expirations'][:3]  # First 3 dates

                    if not dates:
                        messagebox.showerror("Error", "No expiration dates available")
                        return

                    self.results_text.delete(1.0, tk.END)
                    self.results_text.insert(tk.END, "=" * 70 + "\n")
                    self.results_text.insert(tk.END, "FAIR PRICE VALUATION - FIRST 3 EXPIRATION DATES\n")
                    self.results_text.insert(tk.END, "=" * 70 + "\n\n")

                    self.results_text.insert(tk.END, "COMMON PARAMETERS:\n")
                    self.results_text.insert(tk.END, f"  Ticker:              {ticker}\n")
                    self.results_text.insert(tk.END, f"  Option Type:         {opt_type.upper()}\n")
                    self.results_text.insert(tk.END, f"  Stock Price (S):     ${S:.2f}\n")
                    self.results_text.insert(tk.END, f"  Strike Price (K):    ${K:.2f}\n")
                    self.results_text.insert(tk.END, f"  Risk-Free Rate (r):  {r:.4f} ({r*100:.2f}%)\n\n")
                    self.results_text.insert(tk.END, "=" * 70 + "\n\n")

                    # Get dividend yield from field
                    try:
                        q = InputValidator.get_dividend_yield(self.dividend_rate.get(), self.dividend_yield)
                    except ValueError:
                        q = self.dividend_yield

                    provider = get_provider()
                    for i, exp_date in enumerate(dates, 1):
                        # Fetch expiration-specific IV
                        exp_sigma = provider.get_atm_implied_volatility(ticker, exp_date, S, opt_type)
                        if exp_sigma is None:
                            exp_sigma = sigma
                            iv_source = "main field (fallback)"
                        else:
                            iv_source = f"market ATM IV for {exp_date}"

                        result = svc.price_option(S, K, exp_date, exp_sigma, r, q, opt_type)
                        T      = result['T']
                        days   = result['days']
                        price  = result['price']
                        greeks = result['greeks']

                        if T <= 0:
                            continue

                        # Display results
                        self.results_text.insert(tk.END, f"EXPIRATION #{i}: {exp_date} ({days} days)\n")
                        self.results_text.insert(tk.END, f"{'─' * 70}\n")
                        self.results_text.insert(tk.END, f"  Time to Expiration:  {T:.4f} years\n")
                        self.results_text.insert(tk.END, f"  Volatility (σ):      {exp_sigma*100:.2f}% ({iv_source})\n")
                        self.results_text.insert(tk.END, f"  Option Price:        ${price:.4f}\n")
                        self.results_text.insert(tk.END, f"  Delta (Δ):           {greeks['delta']:.4f}\n")
                        self.results_text.insert(tk.END, f"  Gamma (Γ):           {greeks['gamma']:.4f}\n")
                        self.results_text.insert(tk.END, f"  Theta (Θ):           {greeks['theta']:.4f} (per day)\n")
                        self.results_text.insert(tk.END, f"  Vega (ν):            {greeks['vega']:.4f} (per 1% change)\n")
                        self.results_text.insert(tk.END, f"  Rho (ρ):             {greeks['rho']:.4f} (per 1% change)\n\n")

                    self.results_text.insert(tk.END, "=" * 70 + "\n")
                except Exception as e:
                    self.set_status(f"Error: {e}")

            ThreadingHelper.run_async_simple(calculate_multi, self.root_window)
            
        except ValueError as e:
            messagebox.showerror("Input Error", "Please ensure all numeric fields are filled with valid numbers")
        except Exception as e:
            messagebox.showerror("Calculation Error", f"An error occurred: {str(e)}")
    
    def save_risk_free_rate(self):
        """Save risk-free rate to configuration file"""
        try:
            r = float(self.risk_free_rate.get())
            self.config['risk_free_rate'] = r
            self.save_config()
            messagebox.showinfo("Success", f"Risk-free rate ({r:.4f}) saved to config.json")
        except ValueError:
            messagebox.showerror("Input Error", "Please enter a valid number for risk-free rate")
