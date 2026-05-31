"""
Font Manager Utility
Provides utilities for managing fonts across the application
"""

from tkinter import font as tkfont
from typing import Tuple, Optional


class FontManager:
    """Helper class for managing application fonts"""
    
    @staticmethod
    def update_default_fonts(font_size: int):
        """
        Update all default tkinter fonts to specified size
        
        Args:
            font_size: Font size to apply
        """
        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(size=font_size)
        
        text_font = tkfont.nametofont("TkTextFont")
        text_font.configure(size=font_size)
        
        fixed_font = tkfont.nametofont("TkFixedFont")
        fixed_font.configure(size=font_size)
    
    @staticmethod
    def get_bold_font(font_size: int, family: str = 'Arial') -> Tuple[str, int, str]:
        """
        Get a bold font tuple
        
        Args:
            font_size: Font size
            family: Font family (default 'Arial')
            
        Returns:
            Font tuple (family, size, 'bold')
        """
        return (family, font_size, 'bold')
    
    @staticmethod
    def get_font(
        font_size: int,
        family: str = 'Arial',
        weight: str = 'normal'
    ) -> Tuple[str, int, str]:
        """
        Get a font tuple with specified parameters
        
        Args:
            font_size: Font size
            family: Font family (default 'Arial')
            weight: Font weight - 'normal' or 'bold' (default 'normal')
            
        Returns:
            Font tuple (family, size, weight)
        """
        return (family, font_size, weight)
    
    @staticmethod
    def get_courier_font(font_size: int) -> Tuple[str, int]:
        """
        Get a Courier font tuple (for monospace text)
        
        Args:
            font_size: Font size
            
        Returns:
            Font tuple ('Courier', size)
        """
        return ('Courier', font_size)
    
    @staticmethod
    def adjust_font_size(
        current_size: int,
        delta: int,
        min_size: int = 6,
        max_size: int = 36
    ) -> int:
        """
        Adjust font size within bounds
        
        Args:
            current_size: Current font size
            delta: Amount to change (positive or negative)
            min_size: Minimum allowed size (default 6)
            max_size: Maximum allowed size (default 36)
            
        Returns:
            New font size within bounds
        """
        new_size = current_size + delta
        return max(min_size, min(new_size, max_size))
