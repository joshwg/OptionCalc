"""
Suggestion Widget Helper
Provides utilities for displaying ticker suggestions
"""

from tkinter import ttk
from typing import List, Dict, Callable, Optional


class SuggestionWidget:
    """Helper class for managing ticker suggestion display"""
    
    def __init__(
        self,
        suggestions_frame: ttk.Frame,
        font_size: int = 14,
        max_name_length: int = 50
    ):
        """
        Initialize suggestion widget helper
        
        Args:
            suggestions_frame: Frame to display suggestions in
            font_size: Font size for suggestions (default 14)
            max_name_length: Maximum length for company names (default 50)
        """
        self.suggestions_frame = suggestions_frame
        self.font_size = font_size
        self.max_name_length = max_name_length
        self.suggestion_labels = []
    
    def display_suggestions(
        self,
        results: List[Dict],
        on_select: Callable[[str], None]
    ):
        """
        Display ticker suggestions
        
        Args:
            results: List of dicts with 'symbol' and 'name' keys
            on_select: Callback function when suggestion is clicked (receives symbol)
        """
        # Clear previous suggestions
        self.clear_suggestions()
        
        if not results:
            self.hide_suggestions()
            return
        
        # Show suggestions frame
        self.suggestions_frame.grid()
        
        # Create clickable labels for each suggestion
        for i, result in enumerate(results):
            symbol = result['symbol']
            name = result['name']
            
            # Truncate long names
            if len(name) > self.max_name_length:
                name = name[:self.max_name_length - 3] + "..."
            
            label_text = f"{symbol} - {name}"
            
            label = ttk.Label(
                self.suggestions_frame,
                text=label_text,
                foreground='blue',
                cursor='hand2',
                font=("TkDefaultFont", self.font_size)
            )
            label.grid(row=i, column=0, sticky='w', padx=5, pady=1)
            
            # Bind click event to select this ticker
            label.bind('<Button-1>', lambda e, s=symbol: on_select(s))
            
            self.suggestion_labels.append(label)
    
    def clear_suggestions(self):
        """Clear all suggestion labels"""
        for label in self.suggestion_labels:
            label.destroy()
        self.suggestion_labels.clear()
    
    def hide_suggestions(self):
        """Hide the suggestions frame"""
        self.clear_suggestions()
        self.suggestions_frame.grid_remove()
    
    def update_font_size(self, font_size: int):
        """
        Update font size for all suggestion labels
        
        Args:
            font_size: New font size
        """
        self.font_size = font_size
        for label in self.suggestion_labels:
            label.configure(font=("TkDefaultFont", self.font_size))
