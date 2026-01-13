import pandas as pd
import plotly.graph_objects as go
from src.plotting import create_unit_grid_heatmap, GAP_SIZE, PANEL_WIDTH, PANEL_HEIGHT, TEXT_COLOR
from src.config import PLOT_AREA_COLOR, BACKGROUND_COLOR

def verify_heatmap_axis():
    # Mock Data
    data = []
    # Create some defects in Q1 and Q4
    # Q1: 0-7, 0-7
    # Q4: 8-15, 8-15
    data.append({'QUADRANT': 'Q1', 'UNIT_INDEX_X': 0, 'UNIT_INDEX_Y': 0, 'Verification': 'DEFECT'})
    data.append({'QUADRANT': 'Q1', 'UNIT_INDEX_X': 7, 'UNIT_INDEX_Y': 7, 'Verification': 'DEFECT'})
    data.append({'QUADRANT': 'Q4', 'UNIT_INDEX_X': 7, 'UNIT_INDEX_Y': 7, 'Verification': 'DEFECT'}) # Global 15, 15

    df = pd.DataFrame(data)
    panel_rows = 8
    panel_cols = 8

    fig = create_unit_grid_heatmap(df, panel_rows, panel_cols)

    # Inspect Layout
    layout = fig.layout
    xaxis = layout.xaxis
    yaxis = layout.yaxis

    print(f"X-Axis Range: {xaxis.range}")
    print(f"Y-Axis Range: {yaxis.range}")
    print(f"Y-Axis ScaleAnchor: {yaxis.scaleanchor}")

    # Generate HTML to view manually if needed (but we are in sandbox)
    # fig.write_html("test_heatmap.html")

if __name__ == "__main__":
    verify_heatmap_axis()
