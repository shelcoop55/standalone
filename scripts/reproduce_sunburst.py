
import pandas as pd
import sys
import os

# Add the project root to the path so we can import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.plotting.renderers.charts import create_defect_sunburst

def test_sunburst_hierarchy():
    df = pd.DataFrame({
        'QUADRANT': ['Q1', 'Q1', 'Q2'], # Should be ignored
        'DEFECT_TYPE': ['TypeA', 'TypeA', 'TypeB'],
        'Verification': ['Verif1', 'Verif2', 'Verif1'],
        'HAS_VERIFICATION_DATA': [True, True, True]
    })

    fig = create_defect_sunburst(df)

    # Extract IDs to verify structure
    ids = fig.data[0].ids
    print(f"IDs: {ids}")

    expected_ids_subset = ['Total', 'TypeA', 'TypeA-Verif1', 'TypeA-Verif2', 'TypeB', 'TypeB-Verif1']
    for eid in expected_ids_subset:
        if eid not in ids:
            print(f"MISSING ID: {eid}")
        else:
            print(f"Found ID: {eid}")

test_sunburst_hierarchy()
