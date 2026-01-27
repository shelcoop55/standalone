import plotly.graph_objects as go
from src.core.geometry import GeometryContext
from src.core.config import FRAME_WIDTH, FRAME_HEIGHT

def create_geometry_infographic(
    ctx: GeometryContext,
    fixed_offset_x: float,
    fixed_offset_y: float,
    dyn_gap_x: float,
    dyn_gap_y: float
) -> go.Figure:
    """
    Creates a professional infographic detailing the panel geometry.
    Visualizes margins, gaps, quadrant dimensions, and unit cell details.
    """
    fig = go.Figure()

    # --- Colors & Styles ---
    frame_color = "#2C3E50" # Dark Blue/Grey
    quad_color = "#E74C3C"  # Muted Red
    gap_color = "#BDC3C7"   # Grey
    arrow_color = "black"
    text_color = "black"
    bg_color = "white"

    # --- 1. Draw Frame ---
    fig.add_shape(type="rect",
        x0=0, y0=0, x1=FRAME_WIDTH, y1=FRAME_HEIGHT,
        line=dict(color=frame_color, width=4),
        fillcolor="rgba(0,0,0,0)"
    )

    # --- 2. Draw Quadrants ---
    # Using origins from context, but SWAPPING LABELS as requested for visual representation
    # Request: "top left is Q3", "Q1 is lower left"
    # Mapping:
    #   Old Q1 (Top-Left) -> New Label Q3
    #   Old Q2 (Top-Right) -> New Label Q4 (Implied opposite)
    #   Old Q3 (Bottom-Left) -> New Label Q1
    #   Old Q4 (Bottom-Right) -> New Label Q2

    label_map = {
        'Q1': 'Q3',
        'Q2': 'Q4',
        'Q3': 'Q1',
        'Q4': 'Q2'
    }

    for q_key, (qx, qy) in ctx.quadrant_origins.items():
        display_label = label_map.get(q_key, q_key)

        fig.add_shape(type="rect",
            x0=qx, y0=qy,
            x1=qx + ctx.quad_width,
            y1=qy + ctx.quad_height,
            fillcolor=quad_color,
            opacity=0.2,
            line=dict(width=1, color=quad_color)
        )
        # Label Quadrants
        fig.add_annotation(
            x=qx + ctx.quad_width/2, y=qy + ctx.quad_height/2,
            text=f"<b>{display_label}</b><br>{ctx.quad_width:.1f} x {ctx.quad_height:.1f} mm",
            showarrow=False,
            font=dict(size=14, color=frame_color)
        )

    # --- 3. Dimension Annotations (Arrows) ---

    def add_dim_arrow(x0, y0, x1, y1, text, anchor="middle"):
        """Helper to draw a dimension line with arrowheads."""
        fig.add_annotation(
            x=x0, y=y0, ax=x1, ay=y1,
            xref="x", yref="y", axref="x", ayref="y",
            showarrow=True, arrowhead=2, arrowwidth=1, arrowcolor=arrow_color,
            text=""
        )
        # Reverse arrow for double-headed effect
        fig.add_annotation(
            x=x1, y=y1, ax=x0, ay=y0,
            xref="x", yref="y", axref="x", ayref="y",
            showarrow=True, arrowhead=2, arrowwidth=1, arrowcolor=arrow_color,
            text=""
        )

        # Label
        mid_x = (x0 + x1) / 2
        mid_y = (y0 + y1) / 2

        fig.add_annotation(
            x=mid_x, y=mid_y,
            text=f"<b>{text}</b>",
            showarrow=False,
            bgcolor="white",
            bordercolor="black",
            borderwidth=1,
            borderpad=2,
            font=dict(size=10)
        )

    # Left Margin (Total)
    # Draw at Y = Q1 Center
    mid_q1_y = ctx.offset_y + ctx.quad_height / 2
    add_dim_arrow(0, mid_q1_y, ctx.offset_x, mid_q1_y, f"Left Margin<br>{ctx.offset_x:.1f} mm<br>({fixed_offset_x}+{dyn_gap_x})")

    # Top Margin (Total)
    # Draw at X = Q1 Center
    mid_q1_x = ctx.offset_x + ctx.quad_width / 2
    add_dim_arrow(mid_q1_x, 0, mid_q1_x, ctx.offset_y, f"Top Margin<br>{ctx.offset_y:.1f} mm<br>({fixed_offset_y}+{dyn_gap_y})")

    # Inter-Quadrant Gap X
    q1_end_x = ctx.offset_x + ctx.quad_width
    q2_start_x = q1_end_x + ctx.effective_gap_x
    add_dim_arrow(q1_end_x, mid_q1_y, q2_start_x, mid_q1_y, f"Gap X<br>{ctx.effective_gap_x:.1f} mm<br>({dyn_gap_x}+3.0+{dyn_gap_x})")

    # Inter-Quadrant Gap Y
    q1_end_y = ctx.offset_y + ctx.quad_height
    q3_start_y = q1_end_y + ctx.effective_gap_y
    add_dim_arrow(mid_q1_x, q1_end_y, mid_q1_x, q3_start_y, f"Gap Y<br>{ctx.effective_gap_y:.1f} mm")

    # Right Margin (Total)
    # Draw at Y = Q2 Center (which is same as Q1 Y for now, but general logic stands)
    # Start: End of Q2. End: Frame Width.
    q2_end_x = q2_start_x + ctx.quad_width
    add_dim_arrow(q2_end_x, mid_q1_y, FRAME_WIDTH, mid_q1_y, f"Right Margin<br>{(FRAME_WIDTH - q2_end_x):.1f} mm")

    # Bottom Margin (Total)
    # Draw at X = Q3 Center (same as Q1 X)
    # Start: End of Q3. End: Frame Height.
    q3_end_y = q3_start_y + ctx.quad_height
    add_dim_arrow(mid_q1_x, q3_end_y, mid_q1_x, FRAME_HEIGHT, f"Bottom Margin<br>{(FRAME_HEIGHT - q3_end_y):.1f} mm")

    # --- 4. Unit Cell Detail (Inset) ---
    # Draw a magnified unit cell in the center gap or empty space
    # Center of Frame
    cx, cy = FRAME_WIDTH / 2, FRAME_HEIGHT / 2

    # Unit Box
    u_w_display = 40 # Scale up for visibility
    u_h_display = 40 * (ctx.cell_height / ctx.cell_width)

    # Draw Box in center
    fig.add_shape(type="rect",
        x0=cx - u_w_display/2, y0=cy - u_h_display/2,
        x1=cx + u_w_display/2, y1=cy + u_h_display/2,
        fillcolor="#F39C12", line=dict(color="black", width=2)
    )

    fig.add_annotation(
        x=cx, y=cy - u_h_display/2 - 10,
        text=f"<b>Unit Cell</b><br>{ctx.cell_width:.3f} x {ctx.cell_height:.3f} mm",
        showarrow=False,
        font=dict(size=12)
    )

    # --- Layout Config ---
    fig.update_layout(
        title=dict(text="Panel Geometry Layout & Dimensions", x=0.5, font=dict(size=20)),
        width=1000, height=1000,
        xaxis=dict(
            range=[-20, FRAME_WIDTH + 20],
            showgrid=False, zeroline=False, visible=False
        ),
        yaxis=dict(
            range=[FRAME_HEIGHT + 20, -20], # Invert Y to match physical top-left origin
            showgrid=False, zeroline=False, visible=False
        ),
        plot_bgcolor=bg_color,
        paper_bgcolor=bg_color,
        margin=dict(l=20, r=20, t=60, b=20)
    )

    return fig
