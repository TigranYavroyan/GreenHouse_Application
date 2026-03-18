from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class ColorPalette:
    """Modern color palette for the greenhouse application"""
    primary: str = "#49F28A"
    primary_light: str = "#73F8A4"
    primary_dark: str = "#2BC96A"
    secondary: str = "#6ECBFF"
    secondary_light: str = "#9FDEFF"
    secondary_dark: str = "#43B7FF"
    background: str = "#0B1020"
    surface: str = "#131A2E"
    error: str = "#FF6B6B"
    warning: str = "#FFE3A1"
    success: str = "#B9FFCC"
    info: str = "#9BD3FF"
    
    # Text colors
    text_primary: str = "#E7E9EE"
    text_secondary: str = "#A3ADC2"
    text_light: str = "#FFFFFF"
    
    # Neutral colors
    grey_50: str = "#1A2238"
    grey_100: str = "#202A44"
    grey_200: str = "#2A3554"
    grey_300: str = "#344266"
    grey_400: str = "#4B5C84"
    grey_500: str = "#6B7DA3"
    grey_600: str = "#8F9FBE"
    grey_700: str = "#A7B5CE"
    grey_800: str = "#C6D0E2"
    grey_900: str = "#E7E9EE"

@dataclass
class Typography:
    """Typography settings"""
    font_family: str = "Segoe UI, Roboto, Arial, sans-serif"
    font_family_mono: str = "Consolas, Monaco, Courier New, monospace"
    
    # Font sizes
    h1: str = "18px"
    h2: str = "16px"
    h3: str = "14px"
    body: str = "12px"
    caption: str = "11px"
    small: str = "10px"
    
    # Font weights
    light: str = "300"
    regular: str = "400"
    medium: str = "500"
    bold: str = "600"

@dataclass
class Spacing:
    """Spacing system"""
    xs: str = "4px"
    sm: str = "6px"
    md: str = "8px"
    lg: str = "12px"
    xl: str = "16px"
    xxl: str = "20px"
    xxxl: str = "24px"

@dataclass
class BorderRadius:
    """Border radius values"""
    sm: str = "3px"
    md: str = "5px"
    lg: str = "8px"
    xl: str = "10px"
    round: str = "50%"

@dataclass
class GreenhouseTheme:
    """Complete theme configuration for the greenhouse application"""
    colors: ColorPalette
    typography: Typography
    spacing: Spacing
    borderRadius: BorderRadius
    
    def __init__(self):
        self.colors = ColorPalette()
        self.typography = Typography()
        self.spacing = Spacing()
        self.borderRadius = BorderRadius()

class StyleSheetGenerator:
    """Generates PyQt5-compatible CSS stylesheets"""
    
    def __init__(self, theme: GreenhouseTheme):
        self.theme = theme
        self.colors = theme.colors
        self.typography = theme.typography
        self.spacing = theme.spacing
        self.borderRadius = theme.borderRadius
    
    def generate_main_window_style(self) -> str:
        """Generate style for the main window"""
        return f"""
            QMainWindow {{
                background-color: {self.colors.background};
                color: {self.colors.text_primary};
                font-family: {self.typography.font_family};
                font-size: {self.typography.body};
            }}
        """
    
    def generate_button_style(self, variant: str = "primary") -> str:
        """Generate button styles based on variant"""
        if variant == "primary":
            return f"""
                QPushButton {{
                    background-color: {self.colors.primary};
                    color: #0B1020;
                    border: none;
                    border-radius: {self.borderRadius.md};
                    padding: {self.spacing.sm} {self.spacing.lg};
                    font-weight: {self.typography.medium};
                    font-size: {self.typography.body};
                    min-height: 20px;
                }}
                QPushButton:hover {{
                    background-color: {self.colors.primary_light};
                }}
                QPushButton:pressed {{
                    background-color: {self.colors.primary_dark};
                }}
                QPushButton:disabled {{
                    background-color: {self.colors.grey_200};
                    color: {self.colors.grey_500};
                }}
            """
        elif variant == "secondary":
            return f"""
                QPushButton {{
                    background-color: {self.colors.secondary};
                    color: #0B1020;
                    border: none;
                    border-radius: {self.borderRadius.md};
                    padding: {self.spacing.sm} {self.spacing.lg};
                    font-weight: {self.typography.medium};
                    font-size: {self.typography.body};
                    min-height: 20px;
                }}
                QPushButton:hover {{
                    background-color: {self.colors.secondary_light};
                }}
                QPushButton:pressed {{
                    background-color: {self.colors.secondary_dark};
                }}
            """
        elif variant == "outline":
            return f"""
                QPushButton {{
                    background-color: rgba(255,255,255,0.08);
                    color: {self.colors.text_primary};
                    border: 1px solid rgba(255,255,255,0.14);
                    border-radius: {self.borderRadius.md};
                    padding: {self.spacing.sm} {self.spacing.lg};
                    font-weight: {self.typography.medium};
                    font-size: {self.typography.body};
                    min-height: 20px;
                }}
                QPushButton:hover {{
                    background-color: rgba(255,255,255,0.12);
                }}
                QPushButton:pressed {{
                    background-color: rgba(255,255,255,0.18);
                }}
            """
        else:  # default
            return f"""
                QPushButton {{
                    background-color: rgba(255,255,255,0.08);
                    color: {self.colors.text_primary};
                    border: 1px solid rgba(255,255,255,0.14);
                    border-radius: {self.borderRadius.md};
                    padding: {self.spacing.sm} {self.spacing.lg};
                    font-weight: {self.typography.medium};
                    font-size: {self.typography.body};
                    min-height: 20px;
                }}
                QPushButton:hover {{
                    background-color: rgba(255,255,255,0.12);
                }}
                QPushButton:pressed {{
                    background-color: rgba(255,255,255,0.18);
                }}
            """
    
    def generate_group_box_style(self) -> str:
        """Generate style for group boxes"""
        return f"""
            QGroupBox {{
                background-color: rgba(255,255,255,0.06);
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: {self.borderRadius.lg};
                margin-top: {self.spacing.xl};
                padding-top: {self.spacing.md};
                font-weight: {self.typography.medium};
                color: {self.colors.text_primary};
                font-size: {self.typography.h3};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: {self.spacing.lg};
                padding: {self.spacing.xs} {self.spacing.lg};
                background-color: rgba(255,255,255,0.10);
                color: {self.colors.text_primary};
                border-radius: {self.borderRadius.md};
            }}
        """
    
    def generate_text_edit_style(self) -> str:
        """Generate style for text edit widgets"""
        return f"""
            QTextEdit {{
                background-color: {self.colors.surface};
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: {self.borderRadius.md};
                padding: {self.spacing.sm};
                font-family: {self.typography.font_family_mono};
                font-size: {self.typography.caption};
                color: {self.colors.text_primary};
                selection-background-color: rgba(73,242,138,0.35);
            }}
            QTextEdit:focus {{
                border: 1px solid rgba(110,203,255,0.80);
            }}
        """
    
    def generate_line_edit_style(self) -> str:
        """Generate style for line edit widgets"""
        return f"""
            QLineEdit {{
                background-color: {self.colors.surface};
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: {self.borderRadius.md};
                padding: {self.spacing.sm} {self.spacing.md};
                font-size: {self.typography.body};
                color: {self.colors.text_primary};
                min-height: 20px;
            }}
            QLineEdit:focus {{
                border: 1px solid rgba(110,203,255,0.80);
            }}
        """
    
    def generate_label_style(self, variant: str = "body") -> str:
        """Generate label styles based on variant"""
        if variant == "title":
            return f"""
                QLabel {{
                    font-size: {self.typography.h1};
                    font-weight: {self.typography.bold};
                    color: {self.colors.text_primary};
                    padding: {self.spacing.sm} 0;
                }}
            """
        elif variant == "subtitle":
            return f"""
                QLabel {{
                    font-size: {self.typography.h2};
                    font-weight: {self.typography.medium};
                    color: {self.colors.text_primary};
                    padding: {self.spacing.xs} 0;
                }}
            """
        elif variant == "caption":
            return f"""
                QLabel {{
                    font-size: {self.typography.caption};
                    color: {self.colors.text_secondary};
                    padding: {self.spacing.xs} 0;
                }}
            """
        elif variant == "success":
            return f"""
                QLabel {{
                    font-size: {self.typography.body};
                    color: {self.colors.success};
                    font-weight: {self.typography.medium};
                }}
            """
        elif variant == "error":
            return f"""
                QLabel {{
                    font-size: {self.typography.body};
                    color: {self.colors.error};
                    font-weight: {self.typography.medium};
                }}
            """
        else:  # body
            return f"""
                QLabel {{
                    font-size: {self.typography.body};
                    color: {self.colors.text_primary};
                    padding: {self.spacing.xs} 0;
                }}
            """
    
    def generate_tab_widget_style(self) -> str:
        """Generate style for tab widgets"""
        return f"""
            QTabWidget::pane {{
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: {self.borderRadius.lg};
                background-color: rgba(255,255,255,0.06);
                margin-top: -1px;
            }}
            QTabWidget::tab-bar {{
                alignment: center;
            }}
            QTabBar::tab {{
                background-color: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.12);
                border-bottom: none;
                border-top-left-radius: {self.borderRadius.md};
                border-top-right-radius: {self.borderRadius.md};
                padding: {self.spacing.sm} {self.spacing.lg};
                margin-right: {self.spacing.xs};
                font-weight: {self.typography.medium};
                color: {self.colors.text_secondary};
                min-width: 80px;
            }}
            QTabBar::tab:selected {{
                background-color: rgba(255,255,255,0.12);
                color: {self.colors.text_primary};
                border-color: rgba(255,255,255,0.20);
                border-bottom: 1px solid rgba(255,255,255,0.12);
            }}
            QTabBar::tab:hover:!selected {{
                background-color: rgba(255,255,255,0.10);
                color: {self.colors.text_primary};
            }}
        """
    
    def generate_checkbox_style(self) -> str:
        """Generate style for checkboxes"""
        return f"""
            QCheckBox {{
                spacing: {self.spacing.sm};
                color: {self.colors.text_primary};
                font-size: {self.typography.body};
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {self.colors.grey_400};
                border-radius: {self.borderRadius.sm};
                background-color: {self.colors.surface};
            }}
            QCheckBox::indicator:checked {{
                background-color: {self.colors.primary};
                border-color: {self.colors.primary};
            }}
            QCheckBox::indicator:checked:hover {{
                background-color: {self.colors.primary_light};
                border-color: {self.colors.primary_light};
            }}
            QCheckBox::indicator:hover {{
                border-color: {self.colors.primary};
            }}
        """

    def generate_dialog_style(self) -> str:
        """Generate style for modal dialogs and form labels."""
        return f"""
            QDialog {{
                background-color: {self.colors.background};
                color: {self.colors.text_primary};
            }}
            QLabel {{
                color: {self.colors.text_primary};
            }}
            QLabel[role="caption"] {{
                color: {self.colors.text_secondary};
            }}
        """