
import sys
import os
import pandas as pd
import io

# Add project root to path
sys.path.append(os.getcwd())

from src.io.exporters.excel import generate_excel_report

def verify_excel_gen():
    print("Verifying Excel Report Generation...")
    
    # Mock Data
    df = pd.DataFrame({
        'QUADRANT': ['Q1', 'Q1', 'Q1', 'Q2'],
        'DEFECT_TYPE': ['Scratch', 'Scratch', 'Dent', 'Pit'],
        'Verification': ['Real', 'N', 'Real', 'Real'],
        'SOURCE_FILE': ['L1', 'L1', 'L1', 'L2'],
        'UNIT_INDEX_X': [1, 2, 3, 4],
        'UNIT_INDEX_Y': [1, 2, 3, 4],
        'SIDE': ['Front', 'Front', 'Back', 'Front']
    })
    
    try:
        excel_bytes = generate_excel_report(
            df, 
            panel_rows=10, 
            panel_cols=10, 
            source_filename="Test.csv",
            verification_selection="All"
        )
        
        print(f"SUCCESS: Generated {len(excel_bytes)} bytes.")
        
        # Save to file for manual inspection if needed
        with open("test_report.xlsx", "wb") as f:
            f.write(excel_bytes)
        print("Saved to test_report.xlsx")
        
    except Exception as e:
        print(f"FAIL: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_excel_gen()
