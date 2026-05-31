"""
Input Validator Utility
Provides validation methods for common input types
"""

from tkinter import messagebox
from typing import Optional, Tuple


class InputValidator:
    """Helper class for validating user inputs"""
    
    @staticmethod
    def validate_ticker(ticker_str: str, show_error: bool = True) -> Optional[str]:
        """
        Validate and normalize ticker symbol
        
        Args:
            ticker_str: Raw ticker input
            show_error: Whether to show error dialog (default True)
            
        Returns:
            Normalized ticker (uppercase, stripped) or None if invalid
        """
        ticker = ticker_str.strip().upper()
        if not ticker:
            if show_error:
                messagebox.showwarning("Input Error", "Please enter a ticker symbol")
            return None
        return ticker
    
    @staticmethod
    def validate_float(
        value_str: str,
        field_name: str,
        show_error: bool = True,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None
    ) -> Optional[float]:
        """
        Validate and convert string to float
        
        Args:
            value_str: String to convert
            field_name: Name of field for error messages
            show_error: Whether to show error dialog (default True)
            min_value: Optional minimum allowed value
            max_value: Optional maximum allowed value
            
        Returns:
            Float value or None if invalid
        """
        try:
            value = float(value_str.strip())
            
            if min_value is not None and value < min_value:
                if show_error:
                    messagebox.showerror(
                        "Input Error",
                        f"{field_name} must be at least {min_value}"
                    )
                return None
            
            if max_value is not None and value > max_value:
                if show_error:
                    messagebox.showerror(
                        "Input Error",
                        f"{field_name} must be at most {max_value}"
                    )
                return None
            
            return value
            
        except ValueError:
            if show_error:
                messagebox.showerror("Input Error", f"Invalid {field_name}")
            return None
    
    @staticmethod
    def validate_date(date_str: str, show_error: bool = True) -> Optional[str]:
        """
        Validate date string (basic check for non-empty)
        
        Args:
            date_str: Date string to validate
            show_error: Whether to show error dialog (default True)
            
        Returns:
            Stripped date string or None if invalid
        """
        date = date_str.strip()
        if not date:
            if show_error:
                messagebox.showwarning("Input Error", "Please enter an expiration date")
            return None
        return date
    
    @staticmethod
    def validate_required_fields(
        fields: dict,
        show_error: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that all required fields are non-empty
        
        Args:
            fields: Dictionary of {field_name: field_value}
            show_error: Whether to show error dialog (default True)
            
        Returns:
            Tuple of (is_valid, first_missing_field_name)
        """
        for field_name, field_value in fields.items():
            if not field_value or not str(field_value).strip():
                if show_error:
                    messagebox.showwarning(
                        "Input Error",
                        f"Please enter {field_name}"
                    )
                return False, field_name
        
        return True, None
    
    @staticmethod
    def get_dividend_yield(
        dividend_rate_str: str,
        fallback_value: float = 0.0
    ) -> float:
        """
        Get dividend yield as decimal from percentage string
        
        Args:
            dividend_rate_str: Dividend rate as percentage string
            fallback_value: Value to return if conversion fails
            
        Returns:
            Dividend yield as decimal (e.g., 0.025 for 2.5%)
        """
        try:
            return float(dividend_rate_str) / 100
        except (ValueError, TypeError):
            return fallback_value
