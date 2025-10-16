"""
Excel Reporting Module.

This module provides functions for generating professional, multi-sheet Excel
reports from the defect analysis data. It uses xlsxwriter to format the report
with headers, themed charts, and conditional formatting for enhanced readability
and analytical value.
"""
import pandas as pd
import io
from datetime import datetime
from src.config import PANEL_COLOR, CRITICAL_DEFECT_TYPES

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

def _create_summary_sheet(writer, formats, full_df, panel_rows, panel_cols, source_filename):
    """Creates the 'Quarterly Summary' sheet with KPIs and a chart."""
    workbook = writer.book
    worksheet = workbook.add_worksheet('Quarterly Summary')

    _write_report_header(worksheet, formats, source_filename)

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

    start_row = 5
    summary_df.to_excel(writer, sheet_name='Quarterly Summary', startrow=start_row, header=False, index=False)

    for col_num, value in enumerate(summary_df.columns.values):
        worksheet.write(start_row - 1, col_num, value, formats['header'])
        
    for row_num in range(len(summary_df)):
        worksheet.write(row_num + start_row, 0, summary_df.iloc[row_num, 0], formats['cell'])
        worksheet.write(row_num + start_row, 1, summary_df.iloc[row_num, 1], formats['cell'])
        worksheet.write(row_num + start_row, 2, summary_df.iloc[row_num, 2], formats['density'])

    worksheet.autofit()

    chart = workbook.add_chart({'type': 'column'})
    chart.add_series({
        'name': 'Total Defects by Quadrant',
        'categories': ['Quarterly Summary', start_row, 0, start_row + len(quadrants) - 1, 0],
        'values': ['Quarterly Summary', start_row, 1, start_row + len(quadrants) - 1, 1],
        'fill': {'color': PANEL_COLOR},
        'border': {'color': '#000000'},
        'data_labels': {'value': True}
    })
    chart.set_title({'name': 'Defect Count Comparison by Quadrant'})
    chart.set_legend({'position': 'none'})
    chart.set_y_axis({'name': 'Count'})
    chart.set_style(10)
    worksheet.insert_chart('E2', chart, {'x_scale': 1.5, 'y_scale': 1.5})

def _create_top_defects_sheets(writer, formats, full_df):
    """Creates a separate sheet for the top defects of each quadrant."""
    quadrants = ['Q1', 'Q2', 'Q3', 'Q4']
    for quad in quadrants:
        quad_df = full_df[full_df['QUADRANT'] == quad]
        if not quad_df.empty:
            sheet_name = f'{quad} Top Defects'

            top_offenders = quad_df['DEFECT_TYPE'].value_counts().reset_index()
            top_offenders.columns = ['Defect Type', 'Count']
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
    report_columns = ['UNIT_INDEX_X', 'UNIT_INDEX_Y', 'DEFECT_TYPE', 'QUADRANT', 'SOURCE_FILE']
    final_df = full_df[[col for col in report_columns if col in full_df.columns]]

    worksheet = workbook.add_worksheet('Full Defect List')
    final_df.to_excel(writer, sheet_name='Full Defect List', startrow=1, header=False, index=False)

    for col_num, value in enumerate(final_df.columns.values):
        worksheet.write(0, col_num, value, formats['header'])

    formula_parts = [f'$C2="{defect_type}"' for defect_type in CRITICAL_DEFECT_TYPES]
    criteria_formula = f"=OR({', '.join(formula_parts)})"

    worksheet.conditional_format('A2:E{}'.format(len(final_df) + 1), {
        'type': 'formula',
        'criteria': criteria_formula,
        'format': formats['critical']
    })

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
    source_filename: str = "Sample Data"
) -> bytes:
    """
    Generates a comprehensive, multi-sheet Excel report.

    This function orchestrates calls to private helpers to build the report.
    """
    output_buffer = io.BytesIO()

    with pd.ExcelWriter(output_buffer, engine='xlsxwriter') as writer:
        workbook = writer.book
        formats = _define_formats(workbook)

        _create_summary_sheet(writer, formats, full_df, panel_rows, panel_cols, source_filename)
        _create_top_defects_sheets(writer, formats, full_df)
        _create_full_defect_list_sheet(writer, formats, full_df)

    excel_bytes = output_buffer.getvalue()
    return excel_bytes
