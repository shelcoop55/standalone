"""
Package Export Logic.
Handles the generation of the downloadable ZIP package containing reports and images.
"""
import io
import logging
import zipfile
import json
import pandas as pd
from typing import Dict, Any, Optional, Union, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

from src.core.config import (
    GAP_SIZE, PANEL_WIDTH, PANEL_HEIGHT, FRAME_WIDTH, FRAME_HEIGHT,
    SAFE_VERIFICATION_VALUES, PlotTheme,
    PNG_EXPORT_SCALE, PNG_EXPORT_WIDTH, PNG_EXPORT_HEIGHT, PNG_EXPORT_HEIGHT_PARETO,
)
from src.core.models import PanelData
from src.enums import Quadrant
from src.io.exporters.excel import generate_excel_report, generate_coordinate_list_report
from src.plotting.renderers.maps import (
    create_defect_map_figure, create_still_alive_figure, create_spatial_grid_heatmap,
    create_density_contour_map, create_stress_heatmap, create_cross_section_heatmap,
    create_animated_cross_section_heatmap, create_unit_grid_heatmap, create_animated_spatial_heatmap
)
from src.plotting.renderers.infographics import create_geometry_infographic
from src.plotting.renderers.charts import (
    create_pareto_figure, create_defect_sankey, create_defect_sunburst
)
from src.analytics.stress import aggregate_stress_data_from_df
from src.analytics.yield_analysis import get_cross_section_matrix
from src.io.naming import generate_standard_filename

def generate_zip_package(
    full_df, # pandas.DataFrame
    panel_rows: int,
    panel_cols: int,
    quadrant_selection: str,
    verification_selection: str,
    source_filename: str,
    true_defect_data: Dict[Tuple[int, int], Dict[str, Any]],
    ctx: Any = None, # Added ctx argument to match call signature
    include_excel: bool = True,
    include_coords: bool = True,
    include_map: bool = True,
    include_insights: bool = True,
    include_png_all_layers: bool = False,
    include_pareto_png: bool = False,
    include_heatmap_png: bool = False,
    include_heatmap_html: bool = False,
    include_stress_png: bool = False,
    include_root_cause_html: bool = False,
    include_still_alive_png: bool = False,
    layer_data: Optional[Union[Dict, PanelData]] = None,
    process_comment: str = "",
    lot_number: str = "",
    theme_config: Optional[PlotTheme] = None,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
    gap_x: float = GAP_SIZE,
    gap_y: float = GAP_SIZE,
    dyn_gap_x: float = 0.0, # New argument
    dyn_gap_y: float = 0.0, # New argument
    visual_origin_x: float = 0.0,
    visual_origin_y: float = 0.0,
    fixed_offset_x: float = 0.0,
    fixed_offset_y: float = 0.0,
    panel_width: float = PANEL_WIDTH,
    panel_height: float = PANEL_HEIGHT,
    # Heatmap export options (use UI values when available)
    heatmap_bin_size_mm: Optional[float] = None,
    heatmap_use_density: Optional[bool] = None,
    heatmap_real_defects_only: Optional[bool] = None,
    heatmap_zmax_override: Optional[float] = None,
    rca_slice_axis: str = 'Y'
) -> bytes:
    """
    Generates a ZIP file containing selected report components.
    Includes Excel reports, coordinate lists, and interactive HTML charts.
    Also optionally includes PNG images for all layers/sides.
    """
    zip_buffer = io.BytesIO()

    # --- Debug Logging Setup ---
    debug_logs: List[str] = ["DEBUG LOG FOR IMAGE GENERATION\n" + "="*30]
    def log(msg):
        debug_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    log("Starting generate_zip_package")
    log(f"Options: PNG_Maps={include_png_all_layers}, PNG_Pareto={include_pareto_png}")
    log(f"New Options: Heatmap PNG={include_heatmap_png}, Heatmap HTML={include_heatmap_html}, Stress={include_stress_png}, RCA={include_root_cause_html}, Alive={include_still_alive_png}")
    log(f"Verification Selection: {verification_selection}")
    if ctx:
        offset_x, offset_y = ctx.offset_x, ctx.offset_y
        gap_x, gap_y = ctx.effective_gap_x, ctx.effective_gap_y
        visual_origin_x, visual_origin_y = ctx.visual_origin_x, ctx.visual_origin_y
        panel_width, panel_height = ctx.panel_width, ctx.panel_height

    # --- Detailed Geometry Logging ---
    if ctx:
        log("\n--- DETAILED GEOMETRY BREAKDOWN ---")

        # Horizontal
        q1_start_x = ctx.offset_x
        q1_width = ctx.quad_width
        inter_gap_x = ctx.effective_gap_x
        q2_start_x = q1_start_x + q1_width + inter_gap_x
        q2_width = ctx.quad_width
        right_margin = FRAME_WIDTH - (q2_start_x + q2_width)

        log(f"Horizontal (X): Left Margin: {q1_start_x:.2f} mm ({fixed_offset_x} Fixed + {dyn_gap_x} Dynamic)")
        log(f"Horizontal (X): Q1 Width: {q1_width:.2f} mm")
        log(f"Horizontal (X): Inter-Quadrant Gap: {inter_gap_x:.2f} mm ({dyn_gap_x} Dyn + 3.0 Fixed + {dyn_gap_x} Dyn)")
        log(f"Horizontal (X): Q2 Width: {q2_width:.2f} mm")
        log(f"Horizontal (X): Right Margin: {right_margin:.2f} mm ({fixed_offset_x} Fixed + {dyn_gap_x} Dynamic)")

        # Vertical
        q1_start_y = ctx.offset_y
        q1_height = ctx.quad_height
        inter_gap_y = ctx.effective_gap_y
        q3_start_y = q1_start_y + q1_height + inter_gap_y
        q3_height = ctx.quad_height
        bottom_margin = FRAME_HEIGHT - (q3_start_y + q3_height)

        log(f"Vertical (Y): Top Margin: {q1_start_y:.2f} mm ({fixed_offset_y} Fixed + {dyn_gap_y} Dynamic)")
        log(f"Vertical (Y): Q1 Height: {q1_height:.2f} mm")
        log(f"Vertical (Y): Inter-Quadrant Gap: {inter_gap_y:.2f} mm ({dyn_gap_y} Dyn + 3.0 Fixed + {dyn_gap_y} Dyn)")
        log(f"Vertical (Y): Q3 Height: {q3_height:.2f} mm")
        log(f"Vertical (Y): Bottom Margin: {bottom_margin:.2f} mm ({fixed_offset_y} Fixed + {dyn_gap_y} Dynamic)")

        # Unit
        log(f"Unit Dimensions: {ctx.cell_width:.4f} x {ctx.cell_height:.4f} mm")

        log(f"Context Dump: {ctx}")
        log("-----------------------------------\n")
    else:
        log(f"Layout Params: Offset=({offset_x},{offset_y}), Gap=({gap_x},{gap_y}), FixedOffset=({fixed_offset_x},{fixed_offset_y})")

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:

        # 1. Excel Report
        if include_excel:
            excel_bytes = generate_excel_report(
                full_df, panel_rows, panel_cols, source_filename, quadrant_selection, verification_selection
            )
            excel_filename = generate_standard_filename(
                prefix="Defect_Report",
                selected_layer=None, # Already combined
                analysis_params={"lot_number": lot_number, "process_comment": process_comment},
                extension="xlsx"
            )
            zip_file.writestr(excel_filename, excel_bytes)

        # 2. Coordinate List (CSV/Excel)
        if include_coords:
            coord_bytes = generate_coordinate_list_report(set(true_defect_data.keys()))
            coord_filename = generate_standard_filename(
                prefix="Defective_Coordinates",
                selected_layer=None,
                analysis_params={"lot_number": lot_number, "process_comment": process_comment},
                extension="xlsx"
            )
            zip_file.writestr(coord_filename, coord_bytes)

        # 3. Defect Map (Interactive HTML) - CURRENT VIEW
        if include_map:
            fig = create_defect_map_figure(
                full_df, panel_rows, panel_cols, ctx, quadrant_selection,
                title=f"Panel Defect Map - {quadrant_selection}",
                theme_config=theme_config
            )
            html_content = fig.to_html(full_html=True, include_plotlyjs='cdn')
            map_filename = generate_standard_filename(
                prefix="Defect_Map",
                selected_layer=None,
                analysis_params={"lot_number": lot_number, "process_comment": process_comment},
                extension="html"
            )
            zip_file.writestr(map_filename, html_content)

        # 4. Insights Charts (Interactive HTML) - CURRENT VIEW
        if include_insights:
            sunburst_fig = create_defect_sunburst(full_df, theme_config=theme_config)
            sunburst_name = generate_standard_filename(
                prefix="Insights_Sunburst",
                selected_layer=None,
                analysis_params={"lot_number": lot_number, "process_comment": process_comment},
                extension="html"
            )
            zip_file.writestr(sunburst_name, sunburst_fig.to_html(full_html=True, include_plotlyjs='cdn'))

            sankey_fig = create_defect_sankey(full_df, theme_config=theme_config)
            if sankey_fig:
                sankey_name = generate_standard_filename(
                    prefix="Insights_Sankey",
                    selected_layer=None,
                    analysis_params={"lot_number": lot_number, "process_comment": process_comment},
                    extension="html"
                )
                zip_file.writestr(sankey_name, sankey_fig.to_html(full_html=True, include_plotlyjs='cdn'))

        # 5. PNG Images (All Layers/Sides) - OPTIONAL
        if (include_png_all_layers or include_pareto_png):
            if layer_data:
                log(f"Layer data found. Processing {len(layer_data)} layers.")
                # Iterate through all layers in layer_data
                for layer_num in layer_data.get_all_layer_nums():
                    sides = layer_data.get_sides_for_layer(layer_num)
                    for side in sides:
                        layer_obj = layer_data.get_layer(layer_num, side)
                        if not layer_obj: continue

                        df = layer_obj.data
                        side_name = "Front" if side == 'F' else "Back"
                        log(f"Processing Layer {layer_num} - {side_name}")

                        filtered_df = df
                        if verification_selection != 'All':
                            if isinstance(verification_selection, list):
                                if not verification_selection:
                                    filtered_df = filtered_df.iloc[0:0]
                                else:
                                    filtered_df = filtered_df[filtered_df['Verification'].isin(verification_selection)]
                            else:
                                filtered_df = filtered_df[filtered_df['Verification'] == verification_selection]

                        if filtered_df.empty:
                            log(f"  Skipped: DataFrame empty after filtering (Filter: {verification_selection})")
                            continue

                        # Suffix for images
                        parts = []
                        if process_comment:
                            parts.append(process_comment)
                        if lot_number:
                            parts.append(lot_number)

                        img_suffix = "_" + "_".join(parts) if parts else ""

                        # Generate Defect Map PNG
                        if include_png_all_layers:
                            log("  Generating Defect Map PNG...")
                            fig_map = create_defect_map_figure(
                                filtered_df, panel_rows, panel_cols, ctx, Quadrant.ALL.value,
                                title=f"Layer {layer_num} - {side_name} - Defect Map",
                                theme_config=theme_config
                            )
                            try:
                                img_bytes = fig_map.to_image(format="png", engine="kaleido", scale=PNG_EXPORT_SCALE, width=PNG_EXPORT_WIDTH, height=PNG_EXPORT_HEIGHT)
                                # Consistent naming for internal images as well
                                img_name = generate_standard_filename(
                                    prefix=f"Map_L{layer_num}_{side_name}",
                                    selected_layer=layer_num,
                                    layer_data=layer_data,
                                    analysis_params={"lot_number": lot_number, "process_comment": process_comment},
                                    extension="png"
                                )
                                zip_file.writestr(f"Images/{img_name}", img_bytes)
                                log("  Success.")
                            except Exception as e:
                                msg = f"Failed to generate map PNG for Layer {layer_num} {side}: {e}"
                                logger.warning(msg)
                                log(f"  ERROR: {msg}")

                        # Generate Pareto PNG
                        if include_pareto_png:
                            log("  Generating Pareto PNG...")
                            fig_pareto = create_pareto_figure(filtered_df, Quadrant.ALL.value, theme_config=theme_config)
                            fig_pareto.update_layout(
                                title=f"Layer {layer_num} - {side_name} - Pareto"
                            )
                            try:
                                img_bytes = fig_pareto.to_image(format="png", engine="kaleido", scale=PNG_EXPORT_SCALE, width=PNG_EXPORT_WIDTH, height=PNG_EXPORT_HEIGHT_PARETO)
                                pareto_name = generate_standard_filename(
                                    prefix=f"Pareto_L{layer_num}_{side_name}",
                                    selected_layer=layer_num,
                                    layer_data=layer_data,
                                    analysis_params={"lot_number": lot_number, "process_comment": process_comment},
                                    extension="png"
                                )
                                zip_file.writestr(f"Images/{pareto_name}", img_bytes)
                                log("  Success.")
                            except Exception as e:
                                msg = f"Failed to generate pareto PNG for Layer {layer_num} {side}: {e}"
                                logger.warning(msg)
                                log(f"  ERROR: {msg}")
            else:
                log("WARNING: No layer_data provided!")

        # 6. Still Alive Map PNG
        if include_still_alive_png or include_png_all_layers:
            if true_defect_data:
                log("Generating Still Alive Map PNG...")
                fig_alive = create_still_alive_figure(
                    panel_rows, panel_cols, true_defect_data, ctx, theme_config=theme_config
                )
                try:
                    img_bytes = fig_alive.to_image(format="png", engine="kaleido", scale=PNG_EXPORT_SCALE, width=PNG_EXPORT_WIDTH, height=PNG_EXPORT_HEIGHT)
                    alive_name = generate_standard_filename(
                        prefix="Still_Alive_Map",
                        selected_layer=None,
                        analysis_params={"lot_number": lot_number, "process_comment": process_comment},
                        extension="png"
                    )
                    zip_file.writestr(f"Images/{alive_name}", img_bytes)
                    log("Success.")
                except Exception as e:
                    msg = f"Failed to generate Still Alive Map PNG: {e}"
                    logger.warning(msg)
                    log(f"ERROR: {msg}")
            else:
                log("Skipping Still Alive Map: No true defect data found.")

        # 7. Additional Analysis Charts

        if include_heatmap_png:
            log("Generating Heatmap exports from the *analysis* view (Spatial heatmap)...")
            try:
                # Export the same spatial heatmap shown in the Analysis -> Heatmap view
                bin_size = heatmap_bin_size_mm or 10.0
                use_density = bool(heatmap_use_density) if heatmap_use_density is not None else False
                real_defects = True if heatmap_real_defects_only is None else bool(heatmap_real_defects_only)

                fig_spatial = create_spatial_grid_heatmap(
                    full_df,
                    ctx,
                    bin_size_mm=bin_size,
                    real_defects_only=real_defects,
                    use_density=use_density,
                    theme_config=theme_config,
                    zmax_override=heatmap_zmax_override,
                )

                if include_heatmap_png:
                    img_bytes_spatial = fig_spatial.to_image(format="png", engine="kaleido", scale=PNG_EXPORT_SCALE, width=PNG_EXPORT_WIDTH, height=PNG_EXPORT_HEIGHT)
                    heatmap_name = generate_standard_filename(
                        prefix="Analysis_Heatmap_Spatial",
                        selected_layer=None,
                        analysis_params={"lot_number": lot_number, "process_comment": process_comment},
                        extension="png"
                    )
                    zip_file.writestr(f"Images/{heatmap_name}", img_bytes_spatial)

                log("Success.")
            except Exception as e:
                log(f"ERROR Generating Heatmap: {e}")

        if include_stress_png:
            log("Generating Stress Map PNG (Cumulative)...")
            try:
                stress_data = aggregate_stress_data_from_df(full_df, panel_rows, panel_cols)
                fig_stress = create_stress_heatmap(
                    stress_data, panel_rows, panel_cols, ctx, view_mode="Continuous", theme_config=theme_config
                )
                img_bytes = fig_stress.to_image(format="png", engine="kaleido", scale=PNG_EXPORT_SCALE, width=PNG_EXPORT_WIDTH, height=PNG_EXPORT_HEIGHT)
                stress_name = generate_standard_filename(
                    prefix="Analysis_StressMap_Cumulative",
                    selected_layer=None,
                    analysis_params={"lot_number": lot_number, "process_comment": process_comment},
                    extension="png"
                )
                zip_file.writestr(f"Images/{stress_name}", img_bytes)
                log("Success.")
            except Exception as e:
                log(f"ERROR Generating Stress Map: {e}")

        if include_root_cause_html:
            log(f"Generating Root Cause HTML (Axis: {rca_slice_axis})...")
            try:
                # Requires PanelData object. Wrap layer_data if it's a dict.
                panel_obj = layer_data
                if isinstance(layer_data, dict):
                    panel_obj = PanelData()
                    panel_obj._layers = layer_data

                # Create Figure (Animated)
                # We pass the full panel_obj to the animated generator
                fig_rca = create_animated_cross_section_heatmap(
                    panel_obj,
                    panel_rows,
                    panel_cols,
                    axis=rca_slice_axis,
                    theme_config=theme_config
                )

                # For initial view, we might want to default to the worst slice, but Plotly frames start at 0.
                # Setting initial state might be complex with sliders.
                # The user can scrub to find issues.
                # Optionally, we could set 'active' in layout sliders to slice_index,
                # but for now let's just provide the full scanner starting from 0.

                html_content = fig_rca.to_html(full_html=True, include_plotlyjs='cdn', auto_play=False)
                rca_name = generate_standard_filename(
                    prefix="Root_Cause_Analysis",
                    selected_layer=None,
                    analysis_params={"lot_number": lot_number, "process_comment": process_comment},
                    extension="html"
                )
                zip_file.writestr(rca_name, html_content)
                log("Success.")

            except Exception as e:
                msg = f"Failed to generate Root Cause HTML: {e}"
                logger.warning(msg)
                log(f"ERROR: {msg}")

        # 8. Geometry Infographic
        if ctx:
            log("Generating Geometry Infographic...")
            try:
                fig_geo = create_geometry_infographic(
                    ctx, fixed_offset_x, fixed_offset_y, dyn_gap_x, dyn_gap_y
                )
                img_bytes = fig_geo.to_image(format="png", engine="kaleido", scale=PNG_EXPORT_SCALE, width=PNG_EXPORT_WIDTH, height=PNG_EXPORT_HEIGHT)
                geo_name = generate_standard_filename(
                    prefix="Geometry_Layout_Infographic",
                    selected_layer=None,
                    analysis_params={"lot_number": lot_number, "process_comment": process_comment},
                    extension="png"
                )
                zip_file.writestr(geo_name, img_bytes)
                log("Success.")
            except Exception as e:
                msg = f"Failed to generate Geometry Infographic: {e}"
                logger.warning(msg)
                log(f"ERROR: {msg}")

        # Write Debug Log to ZIP
        zip_file.writestr("Debug_Log.txt", "\n".join(debug_logs))

    return zip_buffer.getvalue()
