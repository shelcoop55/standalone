import pytest
import pandas as pd
from src.io.exporters.excel import generate_excel_report

def test_excel_report_generation():
    df = pd.DataFrame({
        'UNIT_INDEX_X': [1], 'UNIT_INDEX_Y': [1],
        'DEFECT_TYPE': ['Nick'], 'Verification': ['T'],
        'QUADRANT': ['Q1'], 'SIDE': ['F'],
        'SOURCE_FILE': ['test.xlsx']
    })

    report_bytes = generate_excel_report(df, 7, 7)
    assert report_bytes is not None
    assert len(report_bytes) > 0
