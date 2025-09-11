"""
Configuration and Styling Module.

This module contains all configuration and styling variables for the application,
including color themes and the method for loading defect-specific styles.
"""

# --- Style Theme: Post-Etch AOI Panel ---
# This palette is designed to look like a copper-clad panel from the PCB/IC Substrate industry.

PANEL_COLOR = '#B87333'      # A metallic, classic copper color for the panels.
GRID_COLOR = '#000000'       # Black for the main grid lines for high contrast.
BACKGROUND_COLOR = '#212121' # A dark charcoal grey for the app background, mimicking an inspection machine.
PLOT_AREA_COLOR = '#333333'  # A slightly lighter grey for the plot area to create subtle depth.
TEXT_COLOR = '#FFFFFF'       # White text for readability on the dark background.

# --- Defect Styling (Loaded from JSON) ---
import json
from pathlib import Path
from typing import Dict

def load_defect_styles() -> Dict[str, str]:
    """
    Loads the defect style mapping from an external JSON file.

    This function looks for 'assets/defect_styles.json' relative to the project root.
    If the file is not found or is corrupted, it prints a warning and returns a
    default, hardcoded color map to ensure the application can still run.

    Returns:
        Dict[str, str]: A dictionary mapping defect types to their corresponding colors.
    """
    style_path = Path(__file__).parent.parent / "assets/defect_styles.json"
    try:
        with open(style_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        # Fallback to a default map if the file is missing or corrupt
        print(f"Warning: Could not load 'defect_styles.json' ({e}). Using default colors.")
        return {
            'Nick': '#9B59B6', 'Short': '#E74C3C', 'Missing Feature': '#2ECC71',
            'Cut': '#1ABC9C', 'Fine Short': '#BE90D4', 'Pad Violation': '#BDC3C7',
            'Island': '#F39C12', 'Cut/Short': '#3498DB', 'Nick/Protrusion': '#F1C40F'
        }

defect_style_map: Dict[str, str] = load_defect_styles()

