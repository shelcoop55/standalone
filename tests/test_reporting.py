import pytest
import pandas as pd
from io import BytesIO
from src.reporting import generate_excel_report
from src.data_handler import load_data # Using this to generate a realistic df

import streamlit as st
import importlib
from src import data_handler
from tests.test_data_handler import test_excel_file

@pytest.fixture
def sample_report_df(test_excel_file, monkeypatch) -> pd.DataFrame:
    """
    Uses the load_data function to generate a realistic DataFrame for testing reporting.
    This ensures the test data has all the columns the reporting function expects.
    """
    monkeypatch.setattr(st, "cache_data", lambda func: func)
    importlib.reload(data_handler)
    return data_handler.load_data(test_excel_file, panel_rows=1, panel_cols=1)

def test_generate_excel_report_structure(sample_report_df):
    """
    Tests that the generated Excel report has the correct structure (sheets).
    """
    report_bytes = generate_excel_report(sample_report_df, 1, 1, "test_file.xlsx")

    # 1. Basic validation
    assert isinstance(report_bytes, bytes)
    assert len(report_bytes) > 0

    # 2. Check the structure of the Excel file
    # Load the bytes back into a pandas ExcelFile object to inspect it
    with pd.ExcelFile(BytesIO(report_bytes), engine='openpyxl') as xls:
        sheet_names = xls.sheet_names

        # We expect a summary, a full list, and one sheet for each of the 4 quadrants
        expected_sheets = [
            'Quarterly Summary',
            'Q1 Top Defects',
            'Q2 Top Defects',
            'Q3 Top Defects',
            'Q4 Top Defects',
            'Full Defect List'
        ]

        assert len(sheet_names) == len(expected_sheets)
        assert all(sheet in sheet_names for sheet in expected_sheets)

def test_generate_excel_report_summary_content(sample_report_df):
    """
    Tests the content of the 'Quarterly Summary' sheet.
    """
    report_bytes = generate_excel_report(sample_report_df, 1, 1, "test_file.xlsx")

    # Header is on row 5 (index 4). Skip the first 4 rows of metadata.
    # The next line will be correctly interpreted as the header.
    summary_df = pd.read_excel(BytesIO(report_bytes), sheet_name='Quarterly Summary', skiprows=4)

    # Check column names
    expected_columns = ['Quadrant', 'Total Defects', 'Defect Density']
    assert all(col in summary_df.columns for col in expected_columns)

    # Check the data
    # There should be 5 rows: Q1, Q2, Q3, Q4, and Total
    assert len(summary_df) == 5

    # Check the 'Total' row
    total_row = summary_df[summary_df['Quadrant'] == 'Total']
    assert total_row['Total Defects'].iloc[0] == 4 # 4 total defects in the sample data

    # Check a specific quadrant row
    q1_row = summary_df[summary_df['Quadrant'] == 'Q1']
    assert q1_row['Total Defects'].iloc[0] == 1 # 1 defect in Q1
    # For a 1x1 panel, density should equal total defects
    assert q1_row['Defect Density'].iloc[0] == 1.0

def test_generate_excel_report_top_defects_content(sample_report_df):
    """
    Tests the content of a 'Top Defects' sheet (e.g., for Q1).
    """
    report_bytes = generate_excel_report(sample_report_df, 1, 1, "test_file.xlsx")

    # Read the Q1 Top Defects sheet
    q1_defects_df = pd.read_excel(BytesIO(report_bytes), sheet_name='Q1 Top Defects')

    # Check column names
    expected_columns = ['Defect Type', 'Count', 'Percentage']
    assert all(col in q1_defects_df.columns for col in expected_columns)

    # In our sample data, Q1 has one defect: 'Nick'
    assert len(q1_defects_df) == 1
    assert q1_defects_df['Defect Type'].iloc[0] == 'Nick'
    assert q1_defects_df['Count'].iloc[0] == 1
    assert q1_defects_df['Percentage'].iloc[0] == 1.0 # 1 out of 1 defect is 100%

def test_generate_excel_report_full_list_content(sample_report_df):
    """
    Tests the content of the 'Full Defect List' sheet.
    """
    report_bytes = generate_excel_report(sample_report_df, 1, 1, "test_file.xlsx")

    # Read the full list sheet
    full_list_df = pd.read_excel(BytesIO(report_bytes), sheet_name='Full Defect List')

    # Check column names
    expected_columns = ['UNIT_INDEX_X', 'UNIT_INDEX_Y', 'DEFECT_TYPE', 'QUADRANT', 'SOURCE_FILE']
    assert all(col in full_list_df.columns for col in expected_columns)

    # The full list should contain all 4 defects from the sample data
    assert len(full_list_df) == 4

    # Verify a specific defect entry (e.g., the 'Short' defect in Q2)
    short_defect = full_list_df[full_list_df['DEFECT_TYPE'] == 'Short']
    assert not short_defect.empty
    assert short_defect['QUADRANT'].iloc[0] == 'Q2'
    assert short_defect['UNIT_INDEX_X'].iloc[0] == 1
    assert short_defect['UNIT_INDEX_Y'].iloc[0] == 0
