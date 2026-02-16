
import pytest
import pandas as pd
import numpy as np
from src.core.layout import apply_layout_to_dataframe
from src.core.geometry import GeometryContext

@pytest.fixture
def mock_geometry_context():
    # Helper to create a predictable context
    # Assume 2x2 panel, unit size 10x10, gap 2
    # Quad size: 2 units * 10 + 1 gap * 2 = 22? No.
    # Cell width calculation in engine: (quad_w - (cols+1)*gap)/cols
    # Let's reverse:
    # quad_width = 100
    # cell_width = 40
    # gap = 10
    # stride = 50
    return GeometryContext(
        panel_width=210, # 2 quads + gap
        panel_height=210,
        quad_width=100,
        quad_height=100,
        cell_width=40,
        cell_height=40,
        stride_x=50, # 40 + 10
        stride_y=50,
        offset_x=5,
        offset_y=5,
        effective_gap_x=10,
        effective_gap_y=10,
        visual_origin_x=0,
        visual_origin_y=0,
        quadrant_origins={'Q1': (5, 5), 'Q2': (115, 5), 'Q3': (5, 115), 'Q4': (115, 115)}
    )

def test_apply_layout_basic_structure(mock_geometry_context):
    """Test standard layout application without spatial override."""
    df = pd.DataFrame({
        'UNIT_INDEX_X': [0, 1, 2, 3], # 0,1 in Q1/Q3; 2,3 in Q2/Q4 (assuming panel_cols=2)
        'UNIT_INDEX_Y': [0, 0, 0, 0],
        'SIDE': ['F', 'F', 'F', 'F']
    })
    
    panel_cols = 2
    panel_rows = 2
    
    df_result = apply_layout_to_dataframe(df, mock_geometry_context, panel_rows, panel_cols)
    
    assert 'plot_x' in df_result.columns
    assert 'plot_y' in df_result.columns
    assert 'QUADRANT' in df_result.columns
    
    # Check Quadrants
    # Col 0,1 -> Q1 (since Y=0 < rows=2)
    # Col 2,3 -> Q2
    assert df_result.loc[0, 'QUADRANT'] == 'Q1'
    assert df_result.loc[2, 'QUADRANT'] == 'Q2'
    
    # Check Coordinates (Approximate check given jitter)
    # Col 0: gap(10) + 0*50 = 10. + offset(0) = 10. + Jitter (approx 5-35) -> 15-45
    # Col 2: In Q2. base = gap(10) + 0*50 = 10. + Q_offset(100+10=110) = 120. -> 125-155
    
    x0 = df_result.loc[0, 'plot_x']
    x2 = df_result.loc[2, 'plot_x']
    
    assert 10 <= x0 <= 60 # Broad range for jitter
    assert 120 <= x2 <= 170

def test_side_flipping_logic(mock_geometry_context):
    """Test that Back side units are flipped correctly in Physical coordinates."""
    df = pd.DataFrame({
        'UNIT_INDEX_X': [0, 3], # Leftmost and Rightmost
        'UNIT_INDEX_Y': [0, 0],
        'SIDE': ['F', 'B']      # Mixed sides
    })
    
    panel_cols = 2 
    # Total width = 4 units (Indices 0,1,2,3)
    
    df_result = apply_layout_to_dataframe(df, mock_geometry_context, panel_rows=2, panel_cols=2)
    
    # Check Front Side (Index 0)
    # Physical Flipped should be same as Index (0)
    row_f = df_result[df_result['SIDE'] == 'F'].iloc[0]
    assert row_f['PHYSICAL_X_FLIPPED'] == 0
    
    # Check Back Side (Index 3)
    # Physical Flipped should be (Total - 1) - Index
    # Total = 4. Max Index = 3.
    # 3 (TotalWidth) - 3 (Index) = 0?
    # Logic: (2 * cols - 1) - index
    # (4 - 1) - 3 = 0.
    # So Back-Side Index 3 (Rightmost) maps to Physical 0 (Leftmost) when flipped.
    
    row_b = df_result[df_result['SIDE'] == 'B'].iloc[0]
    assert row_b['PHYSICAL_X_FLIPPED'] == 0
    
    # Verify Raw Physical is unchanged
    assert row_b['PHYSICAL_X_RAW'] == 3

def test_spatial_coordinates_override(mock_geometry_context):
    """Test that X_COORDINATES override grid logic."""
    df = pd.DataFrame({
        'UNIT_INDEX_X': [0],
        'UNIT_INDEX_Y': [0],
        'SIDE': ['F'],
        'X_COORDINATES': [50000.0], # 50 mm
        'Y_COORDINATES': [20000.0]  # 20 mm
    })
    
    df_result = apply_layout_to_dataframe(df, mock_geometry_context, panel_rows=2, panel_cols=2)
    
    # Should use spatial coords directly (um -> mm)
    assert df_result.loc[0, 'plot_x'] == 50.0
    assert df_result.loc[0, 'plot_y'] == 20.0
    
    # Verify Physical Coords match plot coords (simple mapping)
    assert df_result.loc[0, 'physical_plot_x_flipped'] == 50.0
