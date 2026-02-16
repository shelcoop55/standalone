import plotly.graph_objects as go
import pandas as pd
from typing import List, Optional
from src.core.config import (
    PANEL_COLOR, TEXT_COLOR, BACKGROUND_COLOR, PLOT_AREA_COLOR,
    VERIFICATION_COLOR_SAFE, VERIFICATION_COLOR_DEFECT, NEON_PALETTE,
    PlotTheme, get_extended_palette
)
from src.analytics.verification import is_true_defect_value
from src.enums import Quadrant
from src.plotting.utils import apply_panel_theme, hex_to_rgba

def create_grouped_pareto_trace(df: pd.DataFrame) -> List[go.Bar]:
    if df.empty: return []

    has_verification_data = df['HAS_VERIFICATION_DATA'].any() if 'HAS_VERIFICATION_DATA' in df.columns else False
    group_col = 'Verification' if has_verification_data else 'DEFECT_TYPE'

    grouped_data = df.groupby(['QUADRANT', group_col], observed=True).size().reset_index(name='Count')
    # Filter out zero counts
    grouped_data = grouped_data[grouped_data['Count'] > 0]
    
    # Get top items, excluding zero counts
    top_items_counts = df[group_col].value_counts()
    top_items = top_items_counts[top_items_counts > 0].index.tolist()

    traces = []
    quadrants = ['Q1', 'Q2', 'Q3', 'Q4']
    # Explicit colors to prevent black bars in report exports
    quadrant_colors = {'Q1': '#636EFA', 'Q2': '#EF553B', 'Q3': '#00CC96', 'Q4': '#AB63FA'}

    for quadrant in quadrants:
        quadrant_data = grouped_data[grouped_data['QUADRANT'] == quadrant]
        pivot = quadrant_data.pivot(index=group_col, columns='QUADRANT', values='Count').reindex(top_items).fillna(0)
        if not pivot.empty:
            color = quadrant_colors.get(quadrant, '#4682B4')
            traces.append(go.Bar(name=quadrant, x=pivot.index, y=pivot[quadrant], marker_color=color))
    return traces

def create_pareto_figure(df: pd.DataFrame, quadrant_selection: str = Quadrant.ALL.value, theme_config: Optional[PlotTheme] = None) -> go.Figure:
    """
    Creates the Pareto Figure with Dual Axis (Count + Cumulative %) and Smart Styling.
    """
    if df.empty:
        return go.Figure()

    # 1. Prepare Aggregated Data for Sorting and Cumulative Line
    has_verification_data = df['HAS_VERIFICATION_DATA'].any() if 'HAS_VERIFICATION_DATA' in df.columns else False
    group_col = 'Verification' if has_verification_data else 'DEFECT_TYPE'
    
    # Total counts per type (descending)
    counts = df[group_col].value_counts().reset_index()
    counts.columns = ['Label', 'Count']
    # Filter out zero counts (e.g. from unused categories like GE57, N)
    counts = counts[counts['Count'] > 0]
    
    if counts.empty:
        return go.Figure()

    total_defects = counts['Count'].sum()
    counts['Cumulative'] = counts['Count'].cumsum()
    counts['CumulativePct'] = (counts['Cumulative'] / total_defects) * 100

    fig = go.Figure()

    # 2. Add Bar Traces
    if quadrant_selection == Quadrant.ALL.value:
        # Stacked Bar by Quadrant (Keep existing logic but ensure sort order matches total)
        traces = create_grouped_pareto_trace(df)
        for trace in traces:
            fig.add_trace(trace)
        fig.update_layout(barmode='stack')
    else:
        # Single Series - Apply "Vital Few" Coloring
        # Identify "Vital Few" (up to 80%)
        # We assign color based on whether the *previous* bar was already past 80%? 
        # Or if this bar *contributes* to the first 80%. 
        # Usually vital few are the ones that BRING the line up to 80%.
        
        # Vectorized color assignment
        # Logic: If CumulativePct <= 80 OR (it's the first one crossing 80), it's Vital.
        # Actually simplest: distinct color for top N bars.
        
        colors = []
        vital_color = '#EF553B' # Red/Orange
        trivial_color = '#636EFA' # Blue/Grey
        
        for pct in counts['CumulativePct']:
            if pct <= 80.0:
                colors.append(vital_color)
            else:
                # Check if the *previous* one was <= 80. If so, this one *crossed* it. 
                # But for simplicity, let's just use strict cut-off or handle the crossover.
                # If we want to capture the bar that crosses 80%, we need slightly more logic.
                # Let's stick to: if it's <= 85% it gets the color, to be safe? 
                # Or just strictly <= 80. 
                # Let's do: Strict <= 80 means "Inside Vital Zone".
                colors.append(trivial_color)
                
        # Fix: Ensure at least one vital color if 80% is crossed immediately? 
        # If the first bar is 90%, it should be vital.
        if counts['CumulativePct'].iloc[0] > 80.0:
            colors[0] = vital_color
            
        fig.add_trace(go.Bar(
            name='Count',
            x=counts['Label'],
            y=counts['Count'],
            marker_color=colors,
            text=counts['Count'],            # Smart Annotation
            textposition='auto',             # Auto inside/outside
            hovertemplate='%{x}: %{y} defects<extra></extra>'
        ))

    # 3. Add Cumulative Percentage Line (Dual Axis)
    fig.add_trace(go.Scatter(
        x=counts['Label'],
        y=counts['CumulativePct'],
        name='Cumulative %',
        mode='lines+markers',
        marker=dict(symbol='circle', size=6, color="#00CC96"), # Green line
        line=dict(width=2, color="#00CC96"),
        yaxis='y2',
        hovertemplate='Cumulative: %{y:.1f}%<extra></extra>'
    ))

    # 4. Layout Improvements
    apply_panel_theme(fig, f"Defect Pareto - Quadrant: {quadrant_selection}", height=600, theme_config=theme_config)

    fig.update_layout(
        xaxis=dict(title="Defect Type", categoryorder='array', categoryarray=counts['Label']),
        yaxis=dict(title="Defect Count", showgrid=True),
        yaxis2=dict(
            title="Cumulative %",
            overlaying='y',
            side='right',
            range=[0, 105],
            showgrid=False,
            dtick=20,
        ),
        legend=dict(x=0.8, y=0.95),
        showlegend=True
    )

    return fig

# Removed separate create_pareto_trace as it is now integrated.


def create_defect_sankey(df: pd.DataFrame, theme_config: Optional[PlotTheme] = None) -> go.Sankey:
    """
    Creates a Sankey diagram mapping Defect Types (Left) to Verification Status (Right).
    IMPROVEMENTS:
    - Smart Labels with Counts/Percentages
    - Neon Color Palette
    - Sorted Nodes
    - Thicker Nodes & Solid Links
    - Narrative Tooltips
    """
    if df.empty:
        return None

    has_verification = df['HAS_VERIFICATION_DATA'].iloc[0] if 'HAS_VERIFICATION_DATA' in df.columns else False
    if not has_verification:
        return None

    # Data Prep: Group by [DEFECT_TYPE, Verification]
    sankey_df = df.groupby(['DEFECT_TYPE', 'Verification'], observed=True).size().reset_index(name='Count')

    # Calculate Totals for Labels and Sorting
    total_defects = sankey_df['Count'].sum()
    defect_counts = sankey_df.groupby('DEFECT_TYPE', observed=True)['Count'].sum().sort_values(ascending=False)
    verification_counts = sankey_df.groupby('Verification', observed=True)['Count'].sum().sort_values(ascending=False)

    # Unique Sorted Labels
    defect_types = defect_counts.index.tolist()
    verification_statuses = verification_counts.index.tolist()

    all_labels_raw = defect_types + verification_statuses

    # Generate Smart Labels: "Scratch (42 - 15%)"
    smart_labels = []

    # Source Labels (Defects)
    for dtype in defect_types:
        count = defect_counts[dtype]
        pct = (count / total_defects) * 100
        smart_labels.append(f"{dtype} ({count} - {pct:.1f}%)")

    # Target Labels (Verification)
    for ver in verification_statuses:
        count = verification_counts[ver]
        pct = (count / total_defects) * 100
        smart_labels.append(f"{ver} ({count} - {pct:.1f}%)")

    # Mapping
    source_map = {label: i for i, label in enumerate(defect_types)}
    offset = len(defect_types)
    target_map = {label: i + offset for i, label in enumerate(verification_statuses)}

    sources = []
    targets = []
    values = []
    link_colors = []
    custom_hovers = []

    # Assign Neon Colors to Source Nodes
    source_colors_hex = []
    for i, dtype in enumerate(defect_types):
        color = NEON_PALETTE[i % len(NEON_PALETTE)]
        source_colors_hex.append(color)

    # Assign Status Colors to Target Nodes
    target_colors_hex = []
    for status in verification_statuses:
        if not is_true_defect_value(status):
            target_colors_hex.append(VERIFICATION_COLOR_SAFE)
        else:
            target_colors_hex.append(VERIFICATION_COLOR_DEFECT)

    node_colors = source_colors_hex + target_colors_hex

    # Build Links
    # We iterate through the SORTED defect types to ensure visual flow order
    for dtype in defect_types:
        dtype_df = sankey_df[sankey_df['DEFECT_TYPE'] == dtype]
        for _, row in dtype_df.iterrows():
            ver = row['Verification']
            count = row['Count']

            s_idx = source_map[dtype]
            t_idx = target_map[ver]

            sources.append(s_idx)
            targets.append(t_idx)
            values.append(count)

            # Link Color: Match Source with High Opacity (0.8) for "Pipe" look
            source_hex = source_colors_hex[s_idx]
            link_colors.append(hex_to_rgba(source_hex, opacity=0.8))

            # Narrative Tooltip
            pct_flow = (count / total_defects) * 100
            hover_text = (
                f"<b>{count} {dtype}s</b> accounted for <b>{pct_flow:.1f}%</b> of total flow<br>"
                f"Resulting in <b>{ver}</b> status."
            )
            custom_hovers.append(hover_text)

    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=25,
            thickness=30,    # Much Thicker Nodes
            line=dict(color="black", width=1), # Sharp border
            label=smart_labels,
            color=node_colors,
            hovertemplate='%{label}<extra></extra>'
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            color=link_colors,
            customdata=custom_hovers,
            hovertemplate='%{customdata}<extra></extra>' # Use the narrative text
        ),
        textfont=dict(size=14, color=TEXT_COLOR, family="Roboto")
    )])

    apply_panel_theme(fig, "Defect Type → Verification Flow Analysis", height=700, theme_config=theme_config)

    fig.update_layout(
        font=dict(size=12, color=TEXT_COLOR),
        margin=dict(l=20, r=20, t=60, b=20),
        xaxis=dict(showgrid=False, showline=False), # Sankey doesn't need axes
        yaxis=dict(showgrid=False, showline=False)
    )
    return fig

def create_defect_sunburst(df: pd.DataFrame, theme_config: Optional[PlotTheme] = None) -> go.Figure:
    """
    Creates a Sunburst chart: Defect Type -> Verification (if avail).
    Hierarchy: Total -> Defect Type -> Verification Status
    """
    if df.empty:
        return go.Figure()

    has_verification = df['HAS_VERIFICATION_DATA'].iloc[0] if 'HAS_VERIFICATION_DATA' in df.columns else False

    # 1. Aggregate
    if has_verification:
        grouped = df.groupby(['DEFECT_TYPE', 'Verification'], observed=True).size().reset_index(name='Count')
    else:
        grouped = df.groupby(['DEFECT_TYPE'], observed=True).size().reset_index(name='Count')

    # Build lists
    ids = []
    labels = []
    parents = []
    values = []
    node_colors = [] # Explicit colors to prevent black output in exports

    # Root
    total_count = grouped['Count'].sum()
    ids.append("Total")
    labels.append(f"Total<br>{total_count}")
    parents.append("")
    values.append(total_count)
    node_colors.append("#000000") # Black for Total

    # Root needs hover text too (or defaults)

    # Prepare detailed hover info
    # Format: Type/Status | Count | % of Parent | % of Total
    custom_data = [] # Stores [Label, Count, Pct Parent, Pct Total]

    # Root custom data
    custom_data.append(["Total", total_count, "100%", "100%"])

    # Level 1: Defect Type
    unique_dtypes = grouped['DEFECT_TYPE'].unique()

    # Use extended palette for dynamic range
    palette = get_extended_palette(len(unique_dtypes))

    for i, dtype in enumerate(unique_dtypes):
        dtype_count = grouped[grouped['DEFECT_TYPE'] == dtype]['Count'].sum()
        ids.append(f"{dtype}")
        labels.append(dtype)
        parents.append("Total")
        values.append(dtype_count)

        # Explicit Color for Defect Type
        color = palette[i]
        node_colors.append(color)

        pct_total = (dtype_count / total_count) * 100
        custom_data.append([dtype, dtype_count, f"{pct_total:.1f}%", f"{pct_total:.1f}%"])

        # Level 2: Verification (if exists)
        if has_verification:
            dtype_df = grouped[grouped['DEFECT_TYPE'] == dtype]
            for ver in dtype_df['Verification'].unique():
                ver_count = dtype_df[dtype_df['Verification'] == ver]['Count'].sum()
                ids.append(f"{dtype}-{ver}")
                labels.append(ver)
                parents.append(f"{dtype}")
                values.append(ver_count)

                # Explicit Color for Verification Status
                if not is_true_defect_value(ver):
                    node_colors.append(VERIFICATION_COLOR_SAFE)
                else:
                    # Inherit color from parent (Defect Type)
                    node_colors.append(color)

                pct_parent = (ver_count / dtype_count) * 100
                pct_total_ver = (ver_count / total_count) * 100
                custom_data.append([ver, ver_count, f"{pct_parent:.1f}%", f"{pct_total_ver:.1f}%"])

    fig = go.Figure(go.Sunburst(
        ids=ids,
        labels=labels,
        parents=parents,
        values=values,
        branchvalues="total",
        customdata=custom_data,
        marker=dict(colors=node_colors), # Apply explicit colors
        hovertemplate="<b>%{customdata[0]}</b><br>Count: %{customdata[1]}<br>% of Layer: %{customdata[2]}<br>% of Total: %{customdata[3]}<extra></extra>"
    ))

    # Apply standard theme with title and larger square-like layout
    apply_panel_theme(fig, "Defect Distribution", height=700, theme_config=theme_config)

    fig.update_layout(
        margin=dict(t=40, l=10, r=10, b=10), # Adjusted margins for title
        xaxis=dict(visible=False), # Hide axes to remove any white lines
        yaxis=dict(visible=False),
        showlegend=False # Explicitly hide legend as requested
    )

    return fig
