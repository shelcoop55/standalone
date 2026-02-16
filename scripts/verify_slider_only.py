
import sys
import os
import pandas as pd
import numpy as np
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.getcwd())

from src.plotting.renderers.maps import create_animated_spatial_heatmap
from src.core.geometry import GeometryContext

def verify_slider_only():
    print("Verifying 'show_play_button' functionality...")
    
    # Mock Data
    df = pd.DataFrame({
        'plot_x': np.random.uniform(0, 500, 10),
        'plot_y': np.random.uniform(0, 500, 10),
        'Verification': ['T'] * 10
    })
    
    layer_dfs = [("Layer 1", df), ("Layer 2", df)]
    
    # Mock Context with necessary attributes
    ctx = MagicMock(spec=GeometryContext)
    ctx.offset_x = 0
    ctx.offset_y = 0
    ctx.visual_origin_x = 0
    ctx.visual_origin_y = 0
    # Add other required atts if needed, or rely on defaults if mock works enough for this test
    
    # Test 1: Default (True) - Should have updatemenus
    print("\nTest 1: Default (show_play_button=True)")
    fig_default = create_animated_spatial_heatmap(
        layer_dfs=layer_dfs,
        ctx=ctx,
        panel_rows=2,
        panel_cols=2
    )
    
    has_menus = hasattr(fig_default.layout, 'updatemenus') and len(fig_default.layout.updatemenus) > 0
    print(f"  Has updatemenus: {has_menus}")
    if not has_menus:
        print("  FAIL: Expected updatemenus to be present.")
        sys.exit(1)
        
    # Test 2: False - Should NOT have updatemenus
    print("\nTest 2: Slider Only (show_play_button=False)")
    fig_no_play = create_animated_spatial_heatmap(
        layer_dfs=layer_dfs,
        ctx=ctx,
        panel_rows=2,
        panel_cols=2,
        show_play_button=False
    )
    
    # Plotly might initialize updatemenus as empty tuple or None
    has_menus_2 = False
    if hasattr(fig_no_play.layout, 'updatemenus') and fig_no_play.layout.updatemenus:
        # Check if it's not empty
        if len(fig_no_play.layout.updatemenus) > 0:
            has_menus_2 = True
            
    print(f"  Has updatemenus: {has_menus_2}")
    
    if has_menus_2:
        print("  FAIL: Expected updatemenus to be ABSENT.")
        sys.exit(1)
        
    # Check sliders are still there
    has_sliders = hasattr(fig_no_play.layout, 'sliders') and len(fig_no_play.layout.sliders) > 0
    print(f"  Has sliders: {has_sliders}")
    if not has_sliders:
        print("  FAIL: Expected sliders to be present.")
        sys.exit(1)
        
    print("\nSUCCESS: 'show_play_button' toggle works as expected.")

if __name__ == "__main__":
    verify_slider_only()
