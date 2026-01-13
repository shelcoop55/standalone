
import pandas as pd
import sys
import os

# Add the project root to the path so we can import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.plotting import create_defect_sankey

# Mock Data
df = pd.DataFrame({
    'DEFECT_TYPE': ['Short', 'Cut', 'Short', 'Nick', 'Short', 'Cut'],
    'Verification': ['CU18', 'N', 'CU18', 'N', 'CU22', 'CU18'],
    'HAS_VERIFICATION_DATA': [True] * 6
})

print("--- Running create_defect_sankey with mock data ---")
try:
    fig = create_defect_sankey(df)
    if fig:
        print("Figure created successfully.")
        # Inspect some properties to verify the structure
        # We expect 1 trace of type Sankey
        trace = fig.data[0]
        print(f"Trace Type: {type(trace)}")
        print(f"Node Labels: {trace.node.label}")
        print(f"Node Colors: {trace.node.color}")
        print(f"Link Sources: {trace.link.source}")
        print(f"Link Targets: {trace.link.target}")
        print(f"Link Values: {trace.link.value}")
        print(f"Link Colors: {trace.link.color}") # This might be None currently
    else:
        print("Figure returned None.")
except Exception as e:
    print(f"Error: {e}")
