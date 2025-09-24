import pandas as pd

def create_test_excel_file():
    """
    Creates a predictable Excel file with defect data for testing.
    This is a utility script, not a test itself.
    """
    data = {
        'DEFECT_ID': [101, 102, 103, 104],
        'DEFECT_TYPE': ['Nick', 'Short', 'Cut', 'Nick'],
        'UNIT_INDEX_X': [0, 1, 0, 1], # Covers all quadrants for a 2x2 panel
        'UNIT_INDEX_Y': [0, 0, 1, 1],
    }
    df = pd.DataFrame(data)

    # Save to an Excel file in the same directory
    output_path = "tests/test_data.xlsx"
    df.to_excel(output_path, index=False, engine='openpyxl')
    print(f"Test data successfully created at {output_path}")

if __name__ == "__main__":
    create_test_excel_file()
