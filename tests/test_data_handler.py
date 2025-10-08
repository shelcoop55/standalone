import pytest
import pandas as pd
from io import BytesIO
from src.data_handler import load_data, QUADRANT_WIDTH, QUADRANT_HEIGHT
from src.config import GAP_SIZE

# To run tests, use `pytest` in the root directory.

@pytest.fixture
def test_excel_file() -> list[BytesIO]:
    """
    A pytest fixture that creates an in-memory Excel file for testing.
    This simulates a file upload without needing a physical file on disk.
    It uses a standard BytesIO object and adds a .name attribute to mimic
    Streamlit's UploadedFile object.
    """
    data = {
        'DEFECT_ID': [101, 102, 103, 104],
        'DEFECT_TYPE': ['Nick', 'Short', 'Cut', 'Nick'],
        'UNIT_INDEX_X': [0, 1, 0, 1],
        'UNIT_INDEX_Y': [0, 0, 1, 1],
        'Verification': ['T', 'F', 'T', 'TA'],
    }
    df = pd.DataFrame(data)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Defects')
    output.seek(0)

    # Mimic Streamlit's UploadedFile object by adding a 'name' attribute
    output.name = "test_data.xlsx"

    return [output]

@pytest.fixture
def test_excel_file_missing_cols() -> list[BytesIO]:
    """A pytest fixture that creates an in-memory Excel file with missing columns."""
    data = {
        'DEFECT_ID': [101, 102],
        'DEFECT_TYPE': ['Nick', 'Short'],
        # 'UNIT_INDEX_X' is missing
        'UNIT_INDEX_Y': [0, 1],
    }
    df = pd.DataFrame(data)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Defects')
    output.seek(0)
    output.name = "missing_cols.xlsx"
    return [output]

import streamlit as st
import importlib
from src import data_handler

def no_op_decorator(func):
    """A dummy decorator that does nothing."""
    return func

def test_load_data_quadrant_assignment(test_excel_file, monkeypatch):
    """
    Tests that the load_data function correctly reads a file and assigns quadrants.
    """
    # Patch the decorator BEFORE reloading the module where it's used.
    monkeypatch.setattr(st, "cache_data", lambda func: func)
    importlib.reload(data_handler)

    # For this test, we assume a simple 1x1 grid per quadrant
    panel_rows = 1
    panel_cols = 1

    df = data_handler.load_data(test_excel_file, panel_rows, panel_cols)

    # 1. Basic validation
    assert isinstance(df, pd.DataFrame), "load_data should return a pandas DataFrame"
    assert not df.empty, "DataFrame should not be empty"
    assert len(df) == 4, "DataFrame should have 4 rows for the 4 defects"

    # 2. Check quadrant assignment logic
    # Defect ID 101: X=0, Y=0 -> Q1
    assert df[df['DEFECT_ID'] == 101]['QUADRANT'].iloc[0] == 'Q1'
    # Defect ID 102: X=1, Y=0 -> Q2
    assert df[df['DEFECT_ID'] == 102]['QUADRANT'].iloc[0] == 'Q2'
    # Defect ID 103: X=0, Y=1 -> Q3
    assert df[df['DEFECT_ID'] == 103]['QUADRANT'].iloc[0] == 'Q3'
    # Defect ID 104: X=1, Y=1 -> Q4
    assert df[df['DEFECT_ID'] == 104]['QUADRANT'].iloc[0] == 'Q4'

def test_load_data_coordinate_calculation(test_excel_file, monkeypatch):
    """
    Tests that the load_data function correctly calculates the physical plot coordinates.
    """
    monkeypatch.setattr(st, "cache_data", lambda func: func)
    importlib.reload(data_handler)
    panel_rows = 1
    panel_cols = 1

    df = data_handler.load_data(test_excel_file, panel_rows, panel_cols)

    q1_defect = df[df['DEFECT_ID'] == 101]
    q2_defect = df[df['DEFECT_ID'] == 102]
    q3_defect = df[df['DEFECT_ID'] == 103]
    q4_defect = df[df['DEFECT_ID'] == 104]

    # Check that plot_x and plot_y columns exist and are floats
    assert 'plot_x' in df.columns and pd.api.types.is_float_dtype(df['plot_x'])
    assert 'plot_y' in df.columns and pd.api.types.is_float_dtype(df['plot_y'])

    # Check coordinate ranges based on quadrant
    # Q1 (bottom-left)
    assert 0 < q1_defect['plot_x'].iloc[0] < QUADRANT_WIDTH
    assert 0 < q1_defect['plot_y'].iloc[0] < QUADRANT_HEIGHT

    # Q2 (bottom-right)
    assert QUADRANT_WIDTH + GAP_SIZE < q2_defect['plot_x'].iloc[0] < (QUADRANT_WIDTH * 2) + GAP_SIZE
    assert 0 < q2_defect['plot_y'].iloc[0] < QUADRANT_HEIGHT

    # Q3 (top-left)
    assert 0 < q3_defect['plot_x'].iloc[0] < QUADRANT_WIDTH
    assert QUADRANT_HEIGHT + GAP_SIZE < q3_defect['plot_y'].iloc[0] < (QUADRANT_HEIGHT * 2) + GAP_SIZE

    # Q4 (top-right)
    assert QUADRANT_WIDTH + GAP_SIZE < q4_defect['plot_x'].iloc[0] < (QUADRANT_WIDTH * 2) + GAP_SIZE
    assert QUADRANT_HEIGHT + GAP_SIZE < q4_defect['plot_y'].iloc[0] < (QUADRANT_HEIGHT * 2) + GAP_SIZE

def test_load_data_sample_generation(monkeypatch):
    """
    Tests that sample data is generated correctly when no file is uploaded.
    """
    monkeypatch.setattr(st, "cache_data", lambda func: func)
    # Mock the streamlit info call as it's part of the UI
    monkeypatch.setattr(st.sidebar, "info", lambda *args, **kwargs: None)
    importlib.reload(data_handler)

    # Pass an empty list to simulate no file upload
    df = data_handler.load_data([], panel_rows=7, panel_cols=7)

    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert len(df) == 150 # The default number of sample defects

    # Check that all required columns are present
    expected_cols = ['DEFECT_ID', 'DEFECT_TYPE', 'UNIT_INDEX_X', 'UNIT_INDEX_Y', 'QUADRANT', 'plot_x', 'plot_y']
    assert all(col in df.columns for col in expected_cols)
    assert df['SOURCE_FILE'].iloc[0] == 'Sample Data'

def test_load_data_missing_columns(test_excel_file_missing_cols, monkeypatch):
    """
    Tests that an empty DataFrame is returned if the uploaded file has missing columns.
    """
    monkeypatch.setattr(st, "cache_data", lambda func: func)
    # Mock the streamlit error call to avoid printing during tests
    monkeypatch.setattr(st, "error", lambda *args, **kwargs: None)
    monkeypatch.setattr(st.sidebar, "success", lambda *args, **kwargs: None)
    importlib.reload(data_handler)

    df = data_handler.load_data(test_excel_file_missing_cols, panel_rows=1, panel_cols=1)

    assert isinstance(df, pd.DataFrame)
    assert df.empty
