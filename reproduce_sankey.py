
import plotly.graph_objects as go
import pandas as pd

def create_defect_sankey_repro(df: pd.DataFrame):
    """
    Copy of the function from src/plotting.py to test logic.
    """
    if df.empty:
        return None

    has_verification = True # Assume true for repro

    # Prepare data for Sankey
    sankey_df = df.groupby(['DEFECT_TYPE', 'Verification']).size().reset_index(name='Count')

    # Create unique labels list
    defect_types = sankey_df['DEFECT_TYPE'].unique().tolist()
    verification_statuses = sankey_df['Verification'].unique().tolist()

    # PROBLEM AREA:
    all_labels = defect_types + verification_statuses
    label_map = {label: i for i, label in enumerate(all_labels)}

    print(f"Defect Types: {defect_types}")
    print(f"Verification: {verification_statuses}")
    print(f"All Labels: {all_labels}")
    print(f"Label Map: {label_map}")

    sources = []
    targets = []
    values = []

    for _, row in sankey_df.iterrows():
        s = label_map[row['DEFECT_TYPE']]
        t = label_map[row['Verification']]
        sources.append(s)
        targets.append(t)
        values.append(row['Count'])
        print(f"Link: {row['DEFECT_TYPE']} ({s}) -> {row['Verification']} ({t}) : {row['Count']}")

    fig = go.Figure(data=[go.Sankey(
        node=dict(
            label=all_labels,
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values
        )
    )])
    return fig

# Test Case 1: Distinct Labels (Should work)
print("--- Test Case 1: Distinct ---")
df1 = pd.DataFrame({
    'DEFECT_TYPE': ['Short', 'Cut'],
    'Verification': ['CU18', 'N']
})
create_defect_sankey_repro(df1)

# Test Case 2: Overlap (Should fail)
print("\n--- Test Case 2: Overlap ---")
df2 = pd.DataFrame({
    'DEFECT_TYPE': ['Short', 'Cut'],
    'Verification': ['Short', 'N'] # 'Short' appears in both
})
create_defect_sankey_repro(df2)
