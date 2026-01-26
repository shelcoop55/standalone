import pytest
import pandas as pd
from src.core.models import PanelData, BuildUpLayer
from src.io.ingestion import load_panel_data
from src.core.config import FRAME_WIDTH

def test_panel_data_structure():
    panel_data = PanelData()
    df = pd.DataFrame({
        'DEFECT_ID': [1], 'UNIT_INDEX_X': [1], 'UNIT_INDEX_Y': [1],
        'DEFECT_TYPE': ['Nick'], 'Verification': ['N'],
        'SOURCE_FILE': ['test.xlsx'], 'SIDE': ['F']
    })
    layer = BuildUpLayer(1, 'F', df, 7, 7)
    panel_data.add_layer(layer)

    assert panel_data.get_layer(1, 'F') is not None
    assert not panel_data.get_combined_dataframe().empty

def test_load_sample_data():
    # Test loading synthetic data
    panel_data = load_panel_data([], 7, 7, 470, 470, 3.0, 3.0)
    assert panel_data
    layers = panel_data.get_all_layer_nums()
    assert len(layers) > 0
