"""
Excel Reporting Module.

This module provides functions for generating professional, multi-sheet Excel
reports from the defect analysis data. It uses xlsxwriter to format the report
with headers, themed charts, and conditional formatting for enhanced readability
and analytical value.
"""
import pandas as pd
import io
import plotly.graph_objects as go
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
import zipfile
import json
from src.core.config import PANEL_COLOR, CRITICAL_DEFECT_TYPES, PLOT_AREA_COLOR, BACKGROUND_COLOR, PlotTheme, LIGHT_THEME, GAP_SIZE, PANEL_WIDTH, PANEL_HEIGHT, SAFE_VERIFICATION_VALUES
from src.plotting.renderers.maps import (
    create_defect_map_figure, create_still_alive_figure, create_density_contour_map,
    create_stress_heatmap, create_cross_section_heatmap
)
from src.plotting.renderers.charts import (
    create_pareto_figure, create_defect_sankey, create_defect_sunburst
)
from src.analytics.stress import aggregate_stress_data_from_df
from src.analytics.yield_analysis import get_cross_section_matrix, get_true_defect_coordinates
from src.core.models import PanelData
from src.enums import Quadrant

# ==============================================================================
# --- Private Helper Functions for Report Generation ---
# ==============================================================================

def _define_formats(workbook):
    """Defines all the custom formats used in the Excel report."""
    formats = {
        'title': workbook.add_format({'bold': True, 'font_size': 18, 'font_color': PANEL_COLOR, 'valign': 'vcenter'}),
        'subtitle': workbook.add_format({'bold': True, 'font_size': 12, 'valign': 'vcenter'}),
        'header': workbook.add_format({'bold': True, 'text_wrap': True, 'valign': 'top', 'fg_color': '#DDEBF7', 'border': 1, 'align': 'center'}),
        'cell': workbook.add_format({'border': 1}),
        'percent': workbook.add_format({'num_format': '0.00%', 'border': 1}),
        'density': workbook.add_format({'num_format': '0.00', 'border': 1}),
        'critical': workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})
    }
    return formats

def _write_report_header(worksheet, formats, source_filename):
    """Writes the main header section to a worksheet."""
    worksheet.set_row(0, 30)
    worksheet.merge_range('A1:D1', 'Panel Defect Analysis Report', formats['title'])
    worksheet.write('A2', 'Source File:', formats['subtitle'])
    worksheet.write('B2', source_filename)
    worksheet.write('A3', 'Report Date:', formats['subtitle'])
    worksheet.write('B3', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

def _create_summary_sheet(writer, formats, full_df, panel_rows, panel_cols, source_filename, quadrant_selection, verification_selection):
    """Creates the 'Quarterly Summary' sheet with KPIs, parameters, and a chart."""
    workbook = writer.book
    worksheet = workbook.add_worksheet('Quarterly Summary')

    _write_report_header(worksheet, formats, source_filename)

    # --- Analysis Parameters Table ---
    param_data = {
        "Parameter": ["Panel Rows", "Panel Columns", "Quadrant Filter", "Verification Filter"],
        "Value": [panel_rows, panel_cols, quadrant_selection, verification_selection]
    }
    param_df = pd.DataFrame(param_data)

    param_start_row = 5
    worksheet.merge_range(f'A{param_start_row-1}:B{param_start_row-1}', 'Analysis Parameters', formats['subtitle'])
    param_df.to_excel(writer, sheet_name='Quarterly Summary', startrow=param_start_row, header=True, index=False)


    # --- KPI Summary Table ---
    kpi_start_row = param_start_row + len(param_df) + 3
    worksheet.merge_range(f'A{kpi_start_row-1}:C{kpi_start_row-1}', 'KPI Summary', formats['subtitle'])

    kpi_data = []
    quadrants = ['Q1', 'Q2', 'Q3', 'Q4']

    for quad in quadrants:
        quad_df = full_df[full_df['QUADRANT'] == quad]
        total_defects = len(quad_df)
        density = total_defects / (panel_rows * panel_cols) if (panel_rows * panel_cols) > 0 else 0
        kpi_data.append({"Quadrant": quad, "Total Defects": total_defects, "Defect Density": density})

    total_defects_all = len(full_df)
    density_all = total_defects_all / (4 * panel_rows * panel_cols) if (panel_rows * panel_cols) > 0 else 0
    kpi_data.append({"Quadrant": "Total", "Total Defects": total_defects_all, "Defect Density": density_all})

    summary_df = pd.DataFrame(kpi_data)

    summary_df.to_excel(writer, sheet_name='Quarterly Summary', startrow=kpi_start_row, header=False, index=False)

    for col_num, value in enumerate(summary_df.columns.values):
        worksheet.write(kpi_start_row - 1, col_num, value, formats['header'])
        
    for row_num in range(len(summary_df)):
        worksheet.write(row_num + kpi_start_row, 0, summary_df.iloc[row_num, 0], formats['cell'])
        worksheet.write(row_num + kpi_start_row, 1, summary_df.iloc[row_num, 1], formats['cell'])
        worksheet.write(row_num + kpi_start_row, 2, summary_df.iloc[row_num, 2], formats['density'])

    worksheet.autofit()

    chart = workbook.add_chart({'type': 'column'})
    chart.add_series({
        'name': 'Total Defects by Quadrant',
        'categories': ['Quarterly Summary', kpi_start_row, 0, kpi_start_row + len(quadrants) - 1, 0],
        'values': ['Quarterly Summary', kpi_start_row, 1, kpi_start_row + len(quadrants) - 1, 1],
        'fill': {'color': PANEL_COLOR},
        'border': {'color': '#000000'},
        'data_labels': {'value': True}
    })
    chart.set_title({'name': 'Defect Count Comparison by Quadrant'})
    chart.set_legend({'position': 'none'})
    chart.set_y_axis({'name': 'Count'})
    chart.set_style(10)
    worksheet.insert_chart('E2', chart, {'x_scale': 1.5, 'y_scale': 1.5})

def _create_panel_wide_top_defects_sheet(writer, formats, full_df):
    """Creates a sheet summarizing the top defects for the entire panel, with a chart."""
    if full_df.empty:
        return

    sheet_name = 'Panel-Wide Top Defects'

    top_offenders = full_df['DEFECT_TYPE'].value_counts().reset_index()
    top_offenders.columns = ['Defect Type', 'Count']
    top_offenders = top_offenders[top_offenders['Count'] > 0]
    top_offenders['Percentage'] = (top_offenders['Count'] / len(full_df))

    top_offenders.to_excel(writer, sheet_name=sheet_name, startrow=1, header=False, index=False)

    worksheet = writer.sheets[sheet_name]

    for col_num, value in enumerate(top_offenders.columns.values):
        worksheet.write(0, col_num, value, formats['header'])

    worksheet.set_column('A:A', 30)
    worksheet.set_column('B:B', 12)
    worksheet.set_column('C:C', 12, formats['percent'])

    # Add a chart for better visualization
    chart = writer.book.add_chart({'type': 'pie'})
    chart.add_series({
        'name':       'Panel-Wide Defect Distribution',
        'categories': [sheet_name, 1, 0, len(top_offenders), 0],
        'values':     [sheet_name, 1, 1, len(top_offenders), 1],
        'data_labels': {'percentage': True, 'leader_lines': True},
    })
    chart.set_title({'name': 'Panel-Wide Defect Distribution'})
    chart.set_style(10)
    worksheet.insert_chart('E2', chart, {'x_scale': 1.5, 'y_scale': 1.5})


def _create_per_quadrant_top_defects_sheets(writer, formats, full_df):
    """Creates a separate sheet for the top defects of each quadrant."""
    quadrants = ['Q1', 'Q2', 'Q3', 'Q4']
    for quad in quadrants:
        quad_df = full_df[full_df['QUADRANT'] == quad]
        if not quad_df.empty:
            sheet_name = f'{quad} Top Defects'

            top_offenders = quad_df['DEFECT_TYPE'].value_counts().reset_index()
            top_offenders.columns = ['Defect Type', 'Count']
            top_offenders = top_offenders[top_offenders['Count'] > 0]
            top_offenders['Percentage'] = (top_offenders['Count'] / len(quad_df))
            
            top_offenders.to_excel(writer, sheet_name=sheet_name, startrow=1, header=False, index=False)

            worksheet = writer.sheets[sheet_name]

            for col_num, value in enumerate(top_offenders.columns.values):
                worksheet.write(0, col_num, value, formats['header'])
            worksheet.set_column('C:C', 12, formats['percent'])
            worksheet.autofit()

def _create_full_defect_list_sheet(writer, formats, full_df):
    """Creates the sheet with a full list of all defects and conditional formatting."""
    workbook = writer.book

    # Add 'SIDE' to the report columns if it exists
    report_columns = ['UNIT_INDEX_X', 'UNIT_INDEX_Y', 'DEFECT_TYPE', 'QUADRANT', 'SIDE', 'SOURCE_FILE']
    final_df = full_df[[col for col in report_columns if col in full_df.columns]]

    worksheet = workbook.add_worksheet('Full Defect List')
    final_df.to_excel(writer, sheet_name='Full Defect List', startrow=1, header=False, index=False)

    for col_num, value in enumerate(final_df.columns.values):
        worksheet.write(0, col_num, value, formats['header'])

    # The column for DEFECT_TYPE might change if SIDE is present, so find it dynamically
    try:
        defect_type_col_index = final_df.columns.get_loc('DEFECT_TYPE')
        # Convert index to Excel column letter (A=1, B=2, ...)
        defect_type_col_letter = chr(ord('A') + defect_type_col_index)

        formula_parts = [f'${defect_type_col_letter}2="{defect_type}"' for defect_type in CRITICAL_DEFECT_TYPES]
        criteria_formula = f"=OR({', '.join(formula_parts)})"

        # Apply formatting to the entire row range
        worksheet.conditional_format(f'A2:{chr(ord("A") + len(final_df.columns)-1)}{len(final_df) + 1}', {
            'type': 'formula',
            'criteria': criteria_formula,
            'format': formats['critical']
        })
    except KeyError:
        # If DEFECT_TYPE column doesn't exist for some reason, skip formatting
        pass

    worksheet.autofit()

# ==============================================================================
# --- Public API Function ---
# ==============================================================================

def generate_coordinate_list_report(defective_coords: set) -> bytes:
    """
    Generates a simple Excel report of unique defective cell coordinates.

    Args:
        defective_coords (set): A set of tuples, where each tuple is a
                                (UNIT_INDEX_X, UNIT_INDEX_Y) coordinate.

    Returns:
        bytes: The content of the Excel file as a bytes object.
    """
    output = io.BytesIO()

    # Convert the set of tuples to a DataFrame
    if defective_coords:
        df = pd.DataFrame(list(defective_coords), columns=['UNIT_INDEX_X', 'UNIT_INDEX_Y'])
        df.sort_values(by=['UNIT_INDEX_Y', 'UNIT_INDEX_X'], inplace=True)
    else:
        df = pd.DataFrame(columns=['UNIT_INDEX_X', 'UNIT_INDEX_Y'])

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Defective_Cell_Locations')

        # Auto-adjust column widths for better readability
        worksheet = writer.sheets['Defective_Cell_Locations']
        for i, col in enumerate(df.columns):
            width = max(df[col].astype(str).map(len).max(), len(col)) + 2
            worksheet.set_column(i, i, width)

    return output.getvalue()

def generate_excel_report(
    full_df: pd.DataFrame,
    panel_rows: int,
    panel_cols: int,
    source_filename: str = "Sample Data",
    quadrant_selection: str = "All",
    verification_selection: str = "All"
) -> bytes:
    """
    Generates a comprehensive, multi-sheet Excel report.

    This function orchestrates calls to private helpers to build the report.
    """
    output_buffer = io.BytesIO()

    with pd.ExcelWriter(output_buffer, engine='xlsxwriter') as writer:
        workbook = writer.book
        formats = _define_formats(workbook)

        _create_summary_sheet(writer, formats, full_df, panel_rows, panel_cols, source_filename, quadrant_selection, verification_selection)
        _create_panel_wide_top_defects_sheet(writer, formats, full_df)
        _create_per_quadrant_top_defects_sheets(writer, formats, full_df)
        _create_full_defect_list_sheet(writer, formats, full_df)

    excel_bytes = output_buffer.getvalue()
    return excel_bytes

def generate_zip_package(
    full_df: pd.DataFrame,
    panel_rows: int,
    panel_cols: int,
    quadrant_selection: str,
    verification_selection: str,
    source_filename: str,
    true_defect_coords: set,
    include_excel: bool = True,
    include_coords: bool = True,
    include_map: bool = True,
    include_insights: bool = True,
    include_png_all_layers: bool = False,
    include_pareto_png: bool = False,
    include_heatmap_png: bool = False,
    include_stress_png: bool = False,
    include_root_cause_html: bool = False, # Renamed from include_root_cause_png
    include_still_alive_png: bool = False,
    layer_data: Optional[Union[Dict, PanelData]] = None,
    process_comment: str = "",
    lot_number: str = "",
    theme_config: Optional[PlotTheme] = None,
    # New Layout Parameters matching App logic
    offset_x: float = 0.0,
    offset_y: float = 0.0,
    gap_x: float = GAP_SIZE,
    gap_y: float = GAP_SIZE,
    visual_origin_x: float = 0.0,
    visual_origin_y: float = 0.0,
    fixed_offset_x: float = 0.0,
    fixed_offset_y: float = 0.0,
    panel_width: float = PANEL_WIDTH,
    panel_height: float = PANEL_HEIGHT
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
    log(f"New Options: Heatmap={include_heatmap_png}, Stress={include_stress_png}, RCA={include_root_cause_html}, Alive={include_still_alive_png}")
    log(f"Verification Selection: {verification_selection}")
    log(f"Layout Params: Offset=({offset_x},{offset_y}), Gap=({gap_x},{gap_y}), FixedOffset=({fixed_offset_x},{fixed_offset_y})")

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:

        # 1. Excel Report
        if include_excel:
            excel_bytes = generate_excel_report(
                full_df, panel_rows, panel_cols, source_filename, quadrant_selection, verification_selection
            )
            name_suffix = f"_{process_comment}" if process_comment else ""
            zip_file.writestr(f"Defect_Analysis_Report{name_suffix}.xlsx", excel_bytes)

        # 2. Coordinate List (CSV/Excel)
        if include_coords:
            coord_bytes = generate_coordinate_list_report(true_defect_coords)
            name_suffix = f"_{process_comment}" if process_comment else ""
            zip_file.writestr(f"Defective_Cell_Coordinates{name_suffix}.xlsx", coord_bytes)

        # 3. Defect Map (Interactive HTML) - CURRENT VIEW
        if include_map:
            fig = create_defect_map_figure(
                full_df, panel_rows, panel_cols, quadrant_selection,
                title=f"Panel Defect Map - {quadrant_selection}",
                theme_config=theme_config,
                offset_x=offset_x, offset_y=offset_y,
                gap_x=gap_x, gap_y=gap_y,
                visual_origin_x=visual_origin_x, visual_origin_y=visual_origin_y,
                fixed_offset_x=fixed_offset_x, fixed_offset_y=fixed_offset_y,
                panel_width=panel_width, panel_height=panel_height
            )
            html_content = fig.to_html(full_html=True, include_plotlyjs='cdn')
            zip_file.writestr("Defect_Map.html", html_content)

        # 4. Insights Charts (Interactive HTML) - CURRENT VIEW
        if include_insights:
            sunburst_fig = create_defect_sunburst(full_df, theme_config=theme_config)
            zip_file.writestr("Insights_Sunburst.html", sunburst_fig.to_html(full_html=True, include_plotlyjs='cdn'))

            sankey_fig = create_defect_sankey(full_df, theme_config=theme_config)
            if sankey_fig:
                zip_file.writestr("Insights_Sankey.html", sankey_fig.to_html(full_html=True, include_plotlyjs='cdn'))

        # 5. PNG Images (All Layers/Sides) - OPTIONAL
        if (include_png_all_layers or include_pareto_png):
            if layer_data:
                log(f"Layer data found. Processing {len(layer_data)} layers.")
                # Iterate through all layers in layer_data
                for layer_num, layer_sides in layer_data.items():
                    for side, layer_obj in layer_sides.items():
                        # Handle PanelData BuildUpLayer objects vs legacy Dict[str, DF]
                        if hasattr(layer_obj, 'data'):
                            df = layer_obj.data
                        else:
                            df = layer_obj # Legacy support

                        side_name = "Front" if side == 'F' else "Back"
                        log(f"Processing Layer {layer_num} - {side_name}")

                        filtered_df = df
                        if verification_selection != 'All':
                            if isinstance(verification_selection, list):
                                if not verification_selection:
                                    # If empty list (unselected all), assume NO filtering match -> empty
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
                                filtered_df, panel_rows, panel_cols, Quadrant.ALL.value,
                                title=f"Layer {layer_num} - {side_name} - Defect Map",
                                theme_config=theme_config,
                                offset_x=offset_x, offset_y=offset_y,
                                gap_x=gap_x, gap_y=gap_y,
                                visual_origin_x=visual_origin_x, visual_origin_y=visual_origin_y,
                                fixed_offset_x=fixed_offset_x, fixed_offset_y=fixed_offset_y,
                                panel_width=panel_width, panel_height=panel_height
                            )
                            try:
                                img_bytes = fig_map.to_image(format="png", engine="kaleido", scale=2, width=1200, height=1200)
                                zip_file.writestr(f"Images/Layer_{layer_num}_{side_name}_DefectMap{img_suffix}.png", img_bytes)
                                log("  Success.")
                            except Exception as e:
                                msg = f"Failed to generate map PNG for Layer {layer_num} {side}: {e}"
                                print(msg)
                                log(f"  ERROR: {msg}")

                        # Generate Pareto PNG
                        if include_pareto_png:
                            log("  Generating Pareto PNG...")
                            fig_pareto = create_pareto_figure(filtered_df, Quadrant.ALL.value, theme_config=theme_config)
                            fig_pareto.update_layout(
                                title=f"Layer {layer_num} - {side_name} - Pareto"
                            )
                            try:
                                img_bytes = fig_pareto.to_image(format="png", engine="kaleido", scale=2, width=1200, height=800)
                                zip_file.writestr(f"Images/Layer_{layer_num}_{side_name}_Pareto{img_suffix}.png", img_bytes)
                                log("  Success.")
                            except Exception as e:
                                msg = f"Failed to generate pareto PNG for Layer {layer_num} {side}: {e}"
                                print(msg)
                                log(f"  ERROR: {msg}")
            else:
                log("WARNING: No layer_data provided!")

        # 6. Still Alive Map PNG
        if include_still_alive_png or include_png_all_layers:
            if true_defect_coords:
                log("Generating Still Alive Map PNG...")
                fig_alive = create_still_alive_figure(
                    panel_rows, panel_cols, true_defect_coords, theme_config=theme_config,
                    offset_x=offset_x, offset_y=offset_y,
                    gap_x=gap_x, gap_y=gap_y,
                    visual_origin_x=visual_origin_x, visual_origin_y=visual_origin_y,
                    fixed_offset_x=fixed_offset_x, fixed_offset_y=fixed_offset_y,
                    panel_width=panel_width, panel_height=panel_height
                )
                try:
                    img_bytes = fig_alive.to_image(format="png", engine="kaleido", scale=2, width=1200, height=1200)
                    zip_file.writestr("Images/Still_Alive_Map.png", img_bytes)
                    log("Success.")
                except Exception as e:
                    msg = f"Failed to generate Still Alive Map PNG: {e}"
                    print(msg)
                    log(f"ERROR: {msg}")
            else:
                log("Skipping Still Alive Map: No true defect coordinates found.")

        # 7. Additional Analysis Charts

        if include_heatmap_png:
            log("Generating Heatmap PNG (Global)...")
            try:
                # Issue 3: Use Smoothed Density Contour Map
                fig_heat = create_density_contour_map(
                    full_df, panel_rows, panel_cols, theme_config=theme_config,
                    offset_x=offset_x, offset_y=offset_y,
                    gap_x=gap_x, gap_y=gap_y,
                    visual_origin_x=visual_origin_x, visual_origin_y=visual_origin_y,
                    fixed_offset_x=fixed_offset_x, fixed_offset_y=fixed_offset_y,
                    panel_width=panel_width, panel_height=panel_height
                )
                img_bytes = fig_heat.to_image(format="png", engine="kaleido", scale=2, width=1200, height=1200)
                zip_file.writestr("Images/Analysis_Heatmap.png", img_bytes)
                log("Success.")
            except Exception as e:
                log(f"ERROR Generating Heatmap: {e}")

        if include_stress_png:
            log("Generating Stress Map PNG (Cumulative)...")
            from src.plotting.renderers.maps import create_stress_heatmap
            try:
                stress_data = aggregate_stress_data_from_df(full_df, panel_rows, panel_cols)
                fig_stress = create_stress_heatmap(
                    stress_data, panel_rows, panel_cols, view_mode="Continuous", theme_config=theme_config,
                    offset_x=offset_x, offset_y=offset_y,
                    gap_x=gap_x, gap_y=gap_y,
                    visual_origin_x=visual_origin_x, visual_origin_y=visual_origin_y,
                    fixed_offset_x=fixed_offset_x, fixed_offset_y=fixed_offset_y,
                    panel_width=panel_width, panel_height=panel_height
                )
                img_bytes = fig_stress.to_image(format="png", engine="kaleido", scale=2, width=1200, height=1200)
                zip_file.writestr("Images/Analysis_StressMap_Cumulative.png", img_bytes)
                log("Success.")
            except Exception as e:
                log(f"ERROR Generating Stress Map: {e}")

        if include_root_cause_html:
            log("Generating Root Cause HTML (Top Killer Unit Slice)...")
            try:
                # 1. Identify Worst Unit (True Defects Only)
                safe_upper = {v.upper() for v in SAFE_VERIFICATION_VALUES}

                # Check if Verification column exists and normalize
                if 'Verification' in full_df.columns:
                    true_df = full_df[~full_df['Verification'].astype(str).str.upper().isin(safe_upper)]
                else:
                    true_df = full_df

                if not true_df.empty:
                    # Find worst unit
                    worst_coords = true_df.groupby(['UNIT_INDEX_X', 'UNIT_INDEX_Y']).size().idxmax()
                    worst_x, worst_y = worst_coords
                    log(f"Worst Unit found at X:{worst_x}, Y:{worst_y}")

                    # 2. Generate Cross Section Matrix
                    # Requires PanelData object. Wrap layer_data if it's a dict.
                    panel_obj = layer_data
                    if isinstance(layer_data, dict):
                        panel_obj = PanelData()
                        panel_obj._layers = layer_data

                    # We slice by Y (Row) at the worst Y, to show the row of that unit.
                    # Or slice by X? Usually seeing a Row cross-section is good.
                    slice_axis = 'Y'
                    slice_index = int(worst_y)

                    matrix, layer_labels, axis_labels = get_cross_section_matrix(
                        panel_obj, slice_axis, slice_index, panel_rows, panel_cols
                    )

                    # 3. Create Figure
                    fig_rca = create_cross_section_heatmap(
                        matrix, layer_labels, axis_labels,
                        f"Root Cause Slice: Row {slice_index} (Worst Unit)",
                        theme_config=theme_config
                    )

                    html_content = fig_rca.to_html(full_html=True, include_plotlyjs='cdn')
                    zip_file.writestr("Root_Cause_Analysis.html", html_content)
                    log("Success.")
                else:
                    log("Skipped Root Cause: No true defects found.")

            except Exception as e:
                msg = f"Failed to generate Root Cause HTML: {e}"
                print(msg)
                log(f"ERROR: {msg}")

        # Write Debug Log to ZIP
        zip_file.writestr("Debug_Log.txt", "\n".join(debug_logs))

    return zip_buffer.getvalue()
