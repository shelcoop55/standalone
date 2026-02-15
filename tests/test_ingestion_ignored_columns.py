import io
import sys
import pandas as pd
from unittest.mock import patch


def test_ingestion_drops_configured_ignored_columns():
    # Patch streamlit.cache_resource to avoid hashing issues with in-memory files
    mock_cache = lambda func=None, **kwargs: func if func else (lambda f: f)

    with patch('streamlit.cache_resource', mock_cache):
        # Re-import to apply the patched decorator
        if 'src.io.ingestion' in sys.modules:
            del sys.modules['src.io.ingestion']
        from src.io.ingestion import load_panel_data

        # Create dataframe with required columns + configured ignored columns
        df = pd.DataFrame({
            'DEFECT_TYPE': ['Nick', 'Nick'],
            'UNIT_INDEX_X': [1, 2],
            'UNIT_INDEX_Y': [1, 2],
            'Verification': ['N', 'N'],
            'EMBEDDED_EXCEL': [b"PK\x03\x04", b"PK\x03\x04"],
            'EMBEDDED_OBJECT': ['Embedded object (Workbook)', None],
            'OLE_OBJECT': [None, b"\x00\x01"]
        })

        # Save to Excel in memory
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Defects', index=False)
        buffer.seek(0)
        buffer.name = 'BU-05F.xlsx'

        panel_data = load_panel_data([buffer], 7, 7, 470, 470, 3.0, 3.0)
        layer = panel_data.get_layer(5, 'F')
        assert layer is not None
        cols = layer.data.columns.str.upper().tolist()

        # Columns listed in config must be removed (case-insensitive)
        assert 'EMBEDDED_EXCEL' not in cols
        assert 'EMBEDDED_OBJECT' not in cols
        assert 'OLE_OBJECT' not in cols

        # Required columns must remain
        assert 'DEFECT_TYPE' in cols
        assert 'UNIT_INDEX_X' in cols
        assert 'UNIT_INDEX_Y' in cols