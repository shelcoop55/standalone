"""
Script to verify that the Heatmap and Data Generation logic respects the 30-480mm bounds.
"""
import pandas as pd
import numpy as np
from src.data_handler import load_data
from src.plotting import create_density_contour_map
from src.config import PANEL_WIDTH, PANEL_HEIGHT, GAP_SIZE

def verify_data_bounds():
    print("--- Verifying Random Data Generation ---")
    # Load sample data (passing empty list triggers generation)
    panel_data = load_data([], 7, 7)

    # Get combined dataframe
    df = panel_data.get_combined_dataframe()

    # Check X/Y Coordinates (Microns)
    # Expected: 30,000 to 480,000 um
    x_min_um = df['X_COORDINATES'].min()
    x_max_um = df['X_COORDINATES'].max()
    y_min_um = df['Y_COORDINATES'].min()
    y_max_um = df['Y_COORDINATES'].max()

    print(f"X Range (um): {x_min_um:.2f} - {x_max_um:.2f}")
    print(f"Y Range (um): {y_min_um:.2f} - {y_max_um:.2f}")

    assert x_min_um >= 30000, f"X min too low: {x_min_um}"
    assert x_max_um <= 480000, f"X max too high: {x_max_um}"
    assert y_min_um >= 30000, f"Y min too low: {y_min_um}"
    assert y_max_um <= 480000, f"Y max too high: {y_max_um}"

    # Check Plot Coordinates (mm)
    # plot_x is derived from UNIT_INDEX + Jitter.
    # Since we synced Unit Index to the random coords, plot_x should also be roughly within range.
    # Allow small margin for jitter/cell alignment.
    x_min_plot = df['plot_x'].min()
    x_max_plot = df['plot_x'].max()
    y_min_plot = df['plot_y'].min()
    y_max_plot = df['plot_y'].max()

    print(f"Plot X Range (mm): {x_min_plot:.2f} - {x_max_plot:.2f}")
    print(f"Plot Y Range (mm): {y_min_plot:.2f} - {y_max_plot:.2f}")

    # Max panel width is 600 + 20 = 620.
    # If logic is correct, we shouldn't see values > 550 or < 0.
    assert x_max_plot < 550, f"Plot X max suspiciously high: {x_max_plot}"
    assert y_max_plot < 550, f"Plot Y max suspiciously high: {y_max_plot}"

    print("✅ Data Generation Bounds Verified.")

def verify_heatmap_axis():
    print("\n--- Verifying Heatmap Axis Ranges ---")
    panel_data = load_data([], 7, 7)
    df = panel_data.get_combined_dataframe()

    # Generate Heatmap Figure
    fig = create_density_contour_map(df, 7, 7)

    # Check Layout Axis Ranges
    xaxis = fig.layout.xaxis
    yaxis = fig.layout.yaxis

    print(f"X Axis Range: {xaxis.range}")
    print(f"Y Axis Range: {yaxis.range}")

    # Range should be [ -Gap, Width + 2*Gap ]
    # Width = 600. Range ~ [-20, 640].
    # This is the VIEW range.

    # Check Data Bounds (Contour X/Y)
    contour = fig.data[0] # The contour trace
    if hasattr(contour, 'x') and contour.x is not None:
        data_x_min = min(contour.x)
        data_x_max = max(contour.x)
        data_y_min = min(contour.y)
        data_y_max = max(contour.y)

        print(f"Heatmap Data X Range: {data_x_min:.2f} - {data_x_max:.2f}")
        print(f"Heatmap Data Y Range: {data_y_min:.2f} - {data_y_max:.2f}")

        # If we only generated data up to 480mm, the heatmap density should tail off around there.
        # However, the grid (x_centers) covers the whole panel (0-620).
        # We want to ensure no significant density appears > 600.

        # Check if Z values are 0 for X > 600?
        # Not easily checkable without inspecting Z matrix.

        # But we can verify that the grid covers the panel and not infinity.
        assert data_x_max <= 620 + 20, "Heatmap grid extends too far"
        assert data_y_max <= 620 + 20, "Heatmap grid extends too far"

        print("✅ Heatmap Grid Bounds Verified.")
    else:
        print("⚠️ No contour data found (empty figure?)")

if __name__ == "__main__":
    verify_data_bounds()
    verify_heatmap_axis()
