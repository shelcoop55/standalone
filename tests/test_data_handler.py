import pytest
import pandas as pd
from io import BytesIO
from src.data_handler import load_data, get_true_defect_coordinates, QUADRANT_WIDTH, QUADRANT_HEIGHT
from src.config import GAP_SIZE
import streamlit as st
import importlib
from src import data_handler
from unittest.mock import MagicMock

@pytest.fixture
def test_excel_file() -> list[BytesIO]:
    """Creates an in-memory Excel file with a valid 'BU-XXF' name."""
    data = {
        'DEFECT_ID': [101, 102, 103, 104], 'DEFECT_TYPE': ['Nick', 'Short', 'Cut', 'Nick'],
        'UNIT_INDEX_X': [0, 1, 0, 1], 'UNIT_INDEX_Y': [0, 0, 1, 1],
        'Verification': ['T', 'F', 'T', 'TA'],
    }
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Defects')
    output.seek(0)
    output.name = "BU-01F-test-data.xlsx"
    return [output]

@pytest.fixture
def test_excel_file_missing_cols() -> list[BytesIO]:
    """Creates an in-memory Excel file with missing columns and a valid 'BU-XXB' name."""
    data = {'DEFECT_ID': [101], 'DEFECT_TYPE': ['Nick']}
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Defects')
    output.seek(0)
    output.name = "BU-02B-missing-cols.xlsx"
    return [output]

@pytest.fixture
def test_excel_file_invalid_name() -> list[BytesIO]:
    """Creates an in-memory Excel file with an invalid name."""
    df = pd.DataFrame({'DEFECT_ID': [101]})
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Defects')
    output.seek(0)
    output.name = "invalid_name.xlsx"
    return [output]

def test_load_data_multilayer(test_excel_file, monkeypatch):
    """Tests that load_data correctly processes a valid multi-layer file with sides."""
    monkeypatch.setattr(st, "cache_data", lambda func: func)
    monkeypatch.setattr(st.sidebar, "success", lambda *args, **kwargs: None)
    importlib.reload(data_handler)

    layer_data = data_handler.load_data(test_excel_file, 1, 1)

    assert isinstance(layer_data, dict)
    assert 1 in layer_data
    assert 'F' in layer_data[1]
    df = layer_data[1]['F']
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 4
    assert 'QUADRANT' in df.columns
    assert 'SIDE' in df.columns
    assert df['SIDE'].unique() == ['F']

def test_load_data_sample_generation(monkeypatch):
    """Tests that sample data is generated correctly for multiple layers, including sides."""
    monkeypatch.setattr(st, "cache_data", lambda func: func)
    monkeypatch.setattr(st.sidebar, "info", lambda *args, **kwargs: None)
    importlib.reload(data_handler)

    layer_data = data_handler.load_data([], panel_rows=7, panel_cols=7)

    assert isinstance(layer_data, dict)
    assert set(layer_data.keys()) == {1, 2, 3}
    # All layers should now have Front and Back sides
    for i in range(1, 4):
        assert set(layer_data[i].keys()) == {'F', 'B'}

    # Check counts for a few examples
    assert len(layer_data[1]['F']) == 75
    assert len(layer_data[1]['B']) == 30
    assert len(layer_data[2]['F']) == 120
    assert len(layer_data[2]['B']) == 40
    assert len(layer_data[3]['F']) == 50
    assert len(layer_data[3]['B']) == 25
    assert 'plot_x' in layer_data[1]['F'].columns
    assert 'SIDE' in layer_data[2]['B'].columns

def test_load_data_invalid_filename(test_excel_file_invalid_name, monkeypatch):
    """Tests that a file with an invalid name is ignored."""
    monkeypatch.setattr(st, "cache_data", lambda func: func)
    mock_warning = MagicMock()
    monkeypatch.setattr(st, "warning", mock_warning)
    importlib.reload(data_handler)

    layer_data = data_handler.load_data(test_excel_file_invalid_name, 1, 1)
    assert not layer_data
    mock_warning.assert_called_once()

def test_load_data_missing_columns(test_excel_file_missing_cols, monkeypatch):
    """Tests that a file with missing required columns is skipped."""
    monkeypatch.setattr(st, "cache_data", lambda func: func)
    mock_error = MagicMock()
    monkeypatch.setattr(st, "error", mock_error)
    importlib.reload(data_handler)

    layer_data = data_handler.load_data(test_excel_file_missing_cols, 1, 1)
    assert not layer_data
    mock_error.assert_called_once()

def test_get_true_defect_coordinates():
    """Tests the aggregation of 'True' defect coordinates across multiple layers and sides."""
    layer_1_front = pd.DataFrame({'UNIT_INDEX_X': [1, 2], 'UNIT_INDEX_Y': [1, 2], 'Verification': ['T', 'F']})
    layer_2_front = pd.DataFrame({'UNIT_INDEX_X': [1, 3], 'UNIT_INDEX_Y': [1, 3], 'Verification': ['T', 'T']})
    layer_2_back = pd.DataFrame({'UNIT_INDEX_X': [4, 5], 'UNIT_INDEX_Y': [4, 5], 'Verification': ['T', 'TA']})

    layer_data = {
        1: {'F': layer_1_front},
        2: {'F': layer_2_front, 'B': layer_2_back}
    }

    result = get_true_defect_coordinates(layer_data)

    expected = {(1, 1), (3, 3), (4, 4)}
    assert result == expected