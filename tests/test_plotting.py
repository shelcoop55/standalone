import pytest
import pandas as pd
from src.plotting.renderers.maps import create_defect_map_figure
from src.plotting.renderers.charts import create_pareto_figure

def test_create_defect_map_figure():
    df = pd.DataFrame({
        'UNIT_INDEX_X': [1, 2],
        'UNIT_INDEX_Y': [1, 2],
        'DEFECT_TYPE': ['Nick', 'Short'],
        'Verification': ['T', 'T'],
        'HAS_VERIFICATION_DATA': [True, True],
        'DEFECT_ID': [1, 2],
        'plot_x': [10.0, 20.0],
        'plot_y': [10.0, 20.0]
    })

    fig = create_defect_map_figure(df, 7, 7)
    assert fig is not None
    assert len(fig.data) > 0 # Should have traces

def test_create_pareto_figure():
    df = pd.DataFrame({
        'DEFECT_TYPE': ['Nick', 'Short', 'Nick'],
        'Verification': ['T', 'T', 'T'],
        'HAS_VERIFICATION_DATA': [True, True, True],
        'QUADRANT': ['Q1', 'Q1', 'Q2']
    })

    fig = create_pareto_figure(df)
    assert fig is not None
