"""
Calculator Operations Module
Contains all calculation and data fetching methods for the Option Calculator
"""

import tkinter as tk
from tkinter import messagebox
from datetime import datetime

import yahoo_data as yd
import option_pricing as bs
from utils import ThreadingHelper, InputValidator


class CalculatorOperations:
    """Mixin class containing all calculation and data operations"""
    
    def load_stock_data(self):
        """Load stock data from Yahoo Finance"""
        ticker = InputValidator.validate_ticker(self.ticker.get())
        if not ticker:
            return
        
        # Hide suggestions when loading data
        self.hide_suggestions()
        
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, f"Loading data for {ticker}...\n")
        
        def fetch_data():
            info = yd.get_stock_info(ticker)
            
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
                chain = yd.get_option_chain_next_months(ticker, months=6)
                if chain['success'] and chain['expirations']:
                    first_exp = chain['expirations'][0]
                    self.expiration_date.set(first_exp)
                    self.results_text.insert(tk.END, f"First expiration: {first_exp}\n")
                    
                    # Get options for that expiration
                    options = yd.get_options_for_expiration(ticker, first_exp)
                    if options['success']:
                        # Find strike closest to but above current price
                        opt_type = self.option_type.get()
                        chain_data = options['calls'] if opt_type == 'call' else options['puts']
                        
                        # Get all strikes and sort them
                        all_strikes = sorted([opt['strike'] for opt in chain_data])
                        
                        # Find strikes within range (10 above and below current price)
                        strikes_in_range = []
                        for strike in all_strikes:
                            strikes_in_range.append(strike)
                        
                        # Sort and find the one closest to current price
                        strikes_in_range.sort()
                        
                        # Find index of strike closest to current price
                        closest_idx = 0
                        min_diff = float('inf')
                        for i, strike in enumerate(strikes_in_range):
                            diff = abs(strike - current_price)
                            if diff < min_diff:
                                min_diff = diff
                                closest_idx = i
                        
                        # Get 10 strikes above and below the closest one
                        start_idx = max(0, closest_idx - 10)
                        end_idx = min(len(strikes_in_range), closest_idx + 11)
                        selected_strikes = strikes_in_range[start_idx:end_idx]
                        
                        # Populate strike combobox
                        self.strike_combo['values'] = selected_strikes
                        self.results_text.insert(tk.END, f"Loaded {len(selected_strikes)} strike prices\n")
                        
                        # Find best strike (closest above current price)
                        best_strike = None
                        best_iv = None
                        r_val = float(self.risk_free_rate.get())
                        T_first = yd.get_years_to_expiration(first_exp)

                        for strike in selected_strikes:
                            if strike >= current_price:
                                best_strike = strike
                                for opt in chain_data:
                                    if opt['strike'] == strike:
                                        best_iv = bs.implied_volatility(
                                            (opt['bid'] + opt['ask']) / 2,
                                            current_price, strike, T_first, r_val,
                                            option_type=opt_type
                                        ) if opt['bid'] > 0 and opt['ask'] > 0 else None
                                        if not best_iv:
                                            best_iv = opt['implied_volatility'] or None
                                        break
                                break

                        # If no strike above, use closest
                        if best_strike is None and selected_strikes:
                            best_strike = selected_strikes[closest_idx] if closest_idx < len(selected_strikes) else selected_strikes[-1]
                            for opt in chain_data:
                                if opt['strike'] == best_strike:
                                    best_iv = bs.implied_volatility(
                                        (opt['bid'] + opt['ask']) / 2,
                                        current_price, best_strike, T_first, r_val,
                                        option_type=opt_type
                                    ) if opt['bid'] > 0 and opt['ask'] > 0 else None
                                    if not best_iv:
                                        best_iv = opt['implied_volatility'] or None
                                    break
                        
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
                        self.results_text.insert(tk.END, f"Could not load option chain data\n")
                    
                    # Also load available dates for 6 months
                    self.window.after(100, lambda: self.load_expiration_dates_silent())
                else:
                    self.results_text.insert(tk.END, "No option expirations available\n")
            else:
                messagebox.showerror("Error", f"Failed to load stock data: {info.get('error', 'Unknown error')}")
        
        ThreadingHelper.run_async_simple(fetch_data, self.root_window)
    
    def load_expiration_dates_silent(self):
        """Load expiration dates silently without displaying messages"""
        ticker = InputValidator.validate_ticker(self.ticker.get(), show_error=False)
        if not ticker:
            return
        
        def fetch_dates():
            chain = yd.get_option_chain_next_months(ticker, months=6)
            
            if chain['success']:
                dates = chain['expirations']
                if dates:
                    self.expiration_combo['values'] = dates
                    
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
                        except:
                            pass
                    
                    # Determine if this stock offers weekly or monthly options
                    # Weekly options: multiple expirations in same month
                    # Monthly options: typically one per month (3rd Friday)
                    has_weekly_options = False
                    if len(dates) >= 2:
                        try:
                            date1 = datetime.strptime(dates[0], '%Y-%m-%d')
                            date2 = datetime.strptime(dates[1], '%Y-%m-%d')
                            # If first two expirations are in same month, stock has weekly options
                            if date1.month == date2.month and date1.year == date2.year:
                                has_weekly_options = True
                        except:
                            pass
                    
                    # Set threshold based on option type available
                    threshold = 7 if has_weekly_options else 30
                    
                    # Find first available expiration after earnings date within threshold
                    closest_after_earnings_idx = None
                    if earnings_date_obj:
                        for i, exp_date in enumerate(dates[:3]):
                            try:
                                exp_date_obj = datetime.strptime(exp_date, '%Y-%m-%d')
                                if exp_date_obj > earnings_date_obj:
                                    days_after = (exp_date_obj - earnings_date_obj).days
                                    if days_after <= threshold:
                                        closest_after_earnings_idx = i
                                        break  # Mark first one that meets criteria
                            except:
                                pass
                    
                    type_suffix = 'c' if opt_type == 'call' else 'p'

                    for i, exp_date in enumerate(dates[:3]):  # Take first 3 dates
                        if i < len(self.quick_date_vars):
                            # Format date as MM/DD/YY + c/p suffix
                            try:
                                date_obj = datetime.strptime(exp_date, '%Y-%m-%d')
                                formatted_date = date_obj.strftime('%m/%d/%y') + type_suffix
                                # Add asterisk prefix if this is the closest expiration after earnings
                                if closest_after_earnings_idx is not None and i == closest_after_earnings_idx:
                                    formatted_date = "*" + formatted_date
                            except:
                                formatted_date = exp_date
                            
                            # Set the date
                            self.quick_date_vars[i]['date'].set(formatted_date)
                            self.quick_date_vars[i]['full_date'] = exp_date
                            
                            # Fetch and store IV for this expiration
                            if current_price:
                                try:
                                    r_val = float(self.risk_free_rate.get())
                                except (ValueError, AttributeError):
                                    r_val = 0.045
                                iv = yd.get_atm_implied_volatility(ticker, exp_date, current_price, opt_type, r=r_val)
                                # Only use ATM IV if it's reasonable (> 5% / 0.05)
                                # If IV is too low, it likely means no good ATM option was found
                                if iv and iv > 0.05:
                                    self.quick_date_vars[i]['iv'] = iv
                                    self.quick_date_vars[i]['iv_display'].set(f"{iv*100:.2f}%")
                                else:
                                    # Fall back to main volatility field if no ATM IV available or too low
                                    try:
                                        main_vol = float(self.volatility.get()) / 100
                                        if main_vol > 0:
                                            self.quick_date_vars[i]['iv'] = main_vol
                                            self.quick_date_vars[i]['iv_display'].set(f"{main_vol*100:.2f}%")
                                        else:
                                            self.quick_date_vars[i]['iv'] = None
                                            self.quick_date_vars[i]['iv_display'].set("--")
                                    except (ValueError, AttributeError):
                                        self.quick_date_vars[i]['iv'] = None
                                        self.quick_date_vars[i]['iv_display'].set("--")
                            else:
                                # Try to use main volatility field
                                try:
                                    main_vol = float(self.volatility.get()) / 100
                                    if main_vol > 0:
                                        self.quick_date_vars[i]['iv'] = main_vol
                                        self.quick_date_vars[i]['iv_display'].set(f"{main_vol*100:.2f}%")
                                    else:
                                        self.quick_date_vars[i]['iv'] = None
                                        self.quick_date_vars[i]['iv_display'].set("--")
                                except (ValueError, AttributeError):
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
        
        ThreadingHelper.run_async_simple(fetch_dates, self.root_window)
    
    def calculate_hist_vol(self):
        """Calculate historical volatility"""
        ticker = InputValidator.validate_ticker(self.ticker.get())
        if not ticker:
            return
        
        self.results_text.insert(tk.END, "\nCalculating historical volatility...\n")
        
        def fetch_vol():
            vol = yd.calculate_historical_volatility(ticker, period='1y')
            
            if vol:
                vol_pct = vol * 100
                self.volatility.set(f"{vol_pct:.2f}")
                self.results_text.insert(tk.END, f"Historical Volatility (1 year): {vol_pct:.2f}%\n")
            else:
                messagebox.showerror("Error", "Failed to calculate historical volatility")
        
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
                iv = yd.get_implied_volatility_for_strike(ticker, exp_date, strike, opt_type)
                
                if iv:
                    iv_pct = iv * 100
                    self.volatility.set(f"{iv_pct:.2f}")
                    self.results_text.insert(tk.END, f"Implied Volatility (${strike} {opt_type}): {iv_pct:.2f}%\n")
                else:
                    messagebox.showerror("Error", "Failed to get implied volatility. Check ticker, date, and strike.")
            
            ThreadingHelper.run_async_simple(fetch_iv_strike, self.root_window)
        
        # If no strike but have current price, get ATM implied vol
        elif current_price_str:
            current_price = InputValidator.validate_float(current_price_str, "current price")
            if current_price is None:
                return
            
            self.results_text.insert(tk.END, f"\nGetting ATM implied volatility for {ticker}...\n")
            
            def fetch_iv_atm():
                iv = yd.get_atm_implied_volatility(ticker, exp_date, current_price, opt_type)
                
                if iv:
                    avg_iv = iv * 100
                    self.volatility.set(f"{avg_iv:.2f}")
                    self.results_text.insert(tk.END, f"ATM Implied Volatility: {avg_iv:.2f}%\n")
                else:
                    messagebox.showerror("Error", "Failed to get implied volatility. Check ticker and expiration date.")
            
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
            chain = yd.get_option_chain_next_months(ticker, months=6)
            
            if chain['success']:
                dates = chain['expirations']
                if dates:
                    self.expiration_combo['values'] = dates
                    self.results_text.insert(tk.END, f"Loaded {len(dates)} expiration dates for next 6 months.\n")
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
            chain = yd.get_option_chain(ticker)
            
            if chain['success']:
                dates_str = "\n".join(chain['expirations'])
                self.results_text.delete(1.0, tk.END)
                self.results_text.insert(tk.END, f"Available expiration dates for {ticker}:\n\n{dates_str}\n")
            else:
                messagebox.showerror("Error", f"Failed to get option chain: {chain.get('error', 'Unknown error')}")
        
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
                # Get IV for this strike computed from bid/ask mid
                iv = yd.get_implied_volatility_for_strike(
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
                        T = yd.get_years_to_expiration(exp_date)
                        sigma = iv
                        r = float(self.risk_free_rate.get())
                        
                        # Get dividend yield from field
                        q = InputValidator.get_dividend_yield(self.dividend_rate.get(), self.dividend_yield)
                        
                        # Calculate option price using American binomial model
                        price = bs.american_option_binomial(S, K, T, r, sigma, q=q, option_type=opt_type, steps=100)
                        
                        # Calculate Greeks
                        greeks = bs.calculate_greeks(S, K, T, r, sigma, opt_type)
                        
                        # Display results
                        self.results_text.insert(tk.END, f"Selected Option: {ticker} ${K:.2f} {opt_type.upper()}\n")
                        self.results_text.insert(tk.END, f"Expiration: {exp_date}\n")
                        self.results_text.insert(tk.END, f"Days to Expiration: {yd.get_days_to_expiration(exp_date)}\n\n")
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
            
            # Calculate time to expiration
            T = yd.get_years_to_expiration(exp_date)
            
            # Get option type
            opt_type = self.option_type.get()
            
            # Get dividend yield from field
            q = InputValidator.get_dividend_yield(self.dividend_rate.get(), self.dividend_yield)
            
            # Calculate option price using American binomial model
            price = bs.american_option_binomial(S, K, T, r, sigma, q=q, option_type=opt_type, steps=100)
            
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
            
            # Calculate time to expiration
            T = yd.get_years_to_expiration(exp_date)
            days = yd.get_days_to_expiration(exp_date)
            
            if T <= 0:
                messagebox.showwarning("Warning", "Option has expired or expiration date is invalid")
                return
            
            # Get dividend yield from field
            q = InputValidator.get_dividend_yield(self.dividend_rate.get(), self.dividend_yield)
            
            # Calculate option price using American binomial model
            price = bs.american_option_binomial(S, K, T, r, sigma, q=q, option_type=opt_type, steps=100)
            
            # Calculate Greeks
            greeks = bs.calculate_greeks(S, K, T, r, sigma, opt_type)
            
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
            
            if not ticker:
                messagebox.showwarning("Input Error", "Please enter a ticker symbol")
                return
            
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, f"Calculating {opt_type} option prices for first 3 expiration dates...\n\n")
            
            def calculate_multi():
                # Get expiration dates
                chain = yd.get_option_chain_next_months(ticker, months=6)
                
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
                
                for i, exp_date in enumerate(dates, 1):
                    # Calculate time to expiration
                    T = yd.get_years_to_expiration(exp_date)
                    days = yd.get_days_to_expiration(exp_date)
                    
                    if T <= 0:
                        continue
                    
                    # Fetch expiration-specific IV
                    exp_sigma = yd.get_atm_implied_volatility(ticker, exp_date, S, opt_type)
                    if exp_sigma is None:
                        # Fall back to the main volatility field
                        exp_sigma = sigma
                        iv_source = "main field (fallback)"
                    else:
                        iv_source = f"market ATM IV for {exp_date}"
                    
                    # Calculate option price using American binomial model
                    price = bs.american_option_binomial(S, K, T, r, exp_sigma, q=q, option_type=opt_type, steps=100)
                    
                    # Calculate Greeks using expiration-specific IV
                    greeks = bs.calculate_greeks(S, K, T, r, exp_sigma, opt_type)
                    
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
