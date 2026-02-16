
import pandas as pd
import numpy as np
from src.plotting.renderers.maps import create_animated_spatial_heatmap
from src.core.geometry import GeometryContext

def test_animation_structure():
    # Mock Data
    df = pd.DataFrame({
        'plot_x': np.random.uniform(0, 500, 10),
        'plot_y': np.random.uniform(0, 500, 10),
        'Verification': ['T'] * 10
    })
    
    layer_dfs = [("Layer 1", df), ("Layer 2", df)]
    ctx = GeometryContext()
    
    fig = create_animated_spatial_heatmap(
        layer_dfs=layer_dfs,
        ctx=ctx,
        panel_rows=2,
        panel_cols=2
    )
    
    # Check layout
    print("Updatemenus:", len(fig.layout.updatemenus))
    print("Sliders:", len(fig.layout.sliders))
    
    if fig.layout.updatemenus:
        print("Buttons in Updatemenu 0:", [b.label for b in fig.layout.updatemenus[0].buttons])

if __name__ == "__main__":
    test_animation_structure()
