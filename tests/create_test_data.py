import pandas as pd
import numpy as np

# --- DEFECT DEFINITIONS ---
# List of (Code, Description) tuples for data generation
DEFECT_DEFINITIONS = [
    # Copper-related (CU)
    ("CU10", "Copper Void (Nick)"),
    ("CU14", "Copper Void on Copper Ground"),
    ("CU18", "Short on the Surface (AOI)"),
    ("CU17", "Plating Under Resist (Fine Short)"),
    ("CU22", "Copper Residue"),
    ("CU16", "Open on the Surface (AOI)"),
    ("CU54", "Copper Distribution Not Even / Nodule"),
    ("CU25", "Rough Trace"),
    ("CU15", "Fine Short (Burr)"),
    ("CU94", "Global Copper Thickness Out of Spec – Copper Sting"),
    ("CU19", "Eless Remaining (Chemical Copper Residue)"),
    ("CU20", "Circle Defect"),
    ("CU41", "Copper Coloration or Spots"),
    ("CU80", "Risk to Via Integrity (Core)"),
    # Base Material (BM)
    ("BM31", "Base Material Defect (Irregular Shape)"),
    ("BM01", "Base Material Defect (Crack)"),
    ("BM10", "Base Material Defect (Round Shape)"),
    ("BM34", "Measling / Crazing (White Spots)"),
    # General (GE)
    ("GE01", "Scratch"),
    ("GE32", "ABF Wrinkle"),
    ("GE57", "Foreign Material"),
    ("GE22", "Process Residue"),
    # Hole-related (HO)
    ("HO31", "Via Not Completely Filled"),
    ("HO12", "Hole Shift")
]

FALSE_ALARMS = ["N", "FALSE"]

def create_test_excel_file():
    """
    Creates a predictable Excel file with defect data for testing.
    """
    num_points = 20
    panel_cols = 7
    panel_rows = 7
    total_units_x = panel_cols * 2
    total_units_y = panel_rows * 2

    # Generate random indices
    unit_x = np.random.randint(0, total_units_x, size=num_points)
    unit_y = np.random.randint(0, total_units_y, size=num_points)

    defect_types = []
    verifications = []

    for _ in range(num_points):
        # Pick a base defect scenario
        code, desc = DEFECT_DEFINITIONS[np.random.randint(len(DEFECT_DEFINITIONS))]

        # Decide if it's a false alarm (20% chance)
        if np.random.rand() < 0.2:
            defect_types.append(desc)
            verifications.append(np.random.choice(FALSE_ALARMS))
        else:
            defect_types.append(desc)
            verifications.append(code)

    data = {
        'DEFECT_ID': range(1001, 1001 + num_points),
        'DEFECT_TYPE': defect_types,
        'Verification': verifications,
        'UNIT_INDEX_X': unit_x,
        'UNIT_INDEX_Y': unit_y,
    }
    df = pd.DataFrame(data)

    # Save to an Excel file in the same directory
    output_path = "tests/test_data.xlsx"
    df.to_excel(output_path, index=False, sheet_name='Defects', engine='openpyxl')
    print(f"Test data successfully created at {output_path} with {num_points} points.")
    print("Columns:", df.columns.tolist())
    print("Sample Data:")
    print(df.head())

if __name__ == "__main__":
    create_test_excel_file()
