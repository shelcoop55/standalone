import pandas as pd
from typing import List

REQUIRED_COLUMNS = ['DEFECT_TYPE', 'UNIT_INDEX_X', 'UNIT_INDEX_Y']

def validate_schema(df: pd.DataFrame, filename: str) -> pd.DataFrame:
    """
    Validates and cleans the input dataframe schema.
    Ensures required columns exist and types are correct.
    """
    # 1. Check required columns
    # We allow 'DEFECT_ID' to be missing (optional)
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"File '{filename}' is missing required columns: {missing}")

    # 2. Type Hygiene: Unit Indices must be Integers
    try:
        # Use Int32 to allow NaNs initially (though we drop them next)
        df['UNIT_INDEX_X'] = pd.to_numeric(df['UNIT_INDEX_X'], errors='coerce').astype('Int32')
        df['UNIT_INDEX_Y'] = pd.to_numeric(df['UNIT_INDEX_Y'], errors='coerce').astype('Int32')
    except Exception as e:
        raise ValueError(f"File '{filename}' contains invalid values in UNIT_INDEX columns. Must be numeric. Error: {e}")

    # 3. Drop rows with invalid indices
    initial_count = len(df)
    df.dropna(subset=['UNIT_INDEX_X', 'UNIT_INDEX_Y'], inplace=True)
    dropped = initial_count - len(df)
    if dropped > 0:
        print(f"Warning: Dropped {dropped} rows with missing/invalid coordinates in '{filename}'.")

    # 4. Clean String Columns
    df['DEFECT_TYPE'] = df['DEFECT_TYPE'].astype(str).str.strip().astype('category')

    if 'Verification' in df.columns:
        df['Verification'] = df['Verification'].fillna('N').astype(str).str.strip().str.upper()
        df['Verification'] = df['Verification'].replace('', 'N').astype('category')

    if 'DEFECT_ID' in df.columns:
        df['DEFECT_ID'] = pd.to_numeric(df['DEFECT_ID'], errors='coerce').fillna(-1).astype('int32')

    return df
