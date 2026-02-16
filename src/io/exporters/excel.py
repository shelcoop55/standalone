"""
Excel Export Logic.
Handles the creation of the multi-sheet Excel report using xlsxwriter with a professional "McKinsey-style" design.
"""
import pandas as pd
import io
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import xlsxwriter.utility as xu
from src.analytics.verification import filter_true_defects

# --- CORPORATE THEME CONFIG ---
THEME_COLOR_PRIMARY = '#1F497D'       # Dark Blue (Headers)
THEME_COLOR_SECONDARY = '#D9E1F2'     # Light Blue (Alternating Rows)
THEME_COLOR_ACCENT = '#C0504D'        # Red (Critical/Bad)
THEME_COLOR_GOOD = '#9BBB59'          # Green (Good/Yield)
THEME_COLOR_TEXT = '#000000'
FONT_MAIN = 'Calibri'

logger = logging.getLogger(__name__)

def _define_formats(workbook) -> Dict[str, Any]:
    """Defines professional styling formats for the Excel report."""
    base_fmt = {'font_name': FONT_MAIN, 'font_size': 11, 'border': 0}
    
    formats = {
        'title': workbook.add_format({**base_fmt, 'bold': True, 'font_size': 18, 'font_color': THEME_COLOR_PRIMARY, 'valign': 'vcenter'}),
        'subtitle': workbook.add_format({**base_fmt, 'bold': True, 'font_size': 14, 'font_color': '#595959', 'valign': 'vcenter'}),
        'header': workbook.add_format({
            **base_fmt, 'bold': True, 'text_wrap': True, 'valign': 'top', 
            'fg_color': THEME_COLOR_PRIMARY, 'font_color': 'white', 
            'border': 1, 'align': 'center'
        }),
        'cell': workbook.add_format({**base_fmt, 'border': 1}),
        'cell_center': workbook.add_format({**base_fmt, 'border': 1, 'align': 'center'}),
        'percent': workbook.add_format({**base_fmt, 'num_format': '0.0%', 'border': 1, 'align': 'center'}),
        'int': workbook.add_format({**base_fmt, 'num_format': '#,##0', 'border': 1, 'align': 'center'}),
        'density': workbook.add_format({**base_fmt, 'num_format': '0.00', 'border': 1, 'align': 'center'}),
        
        # Dashboard Cards
        'card_title': workbook.add_format({**base_fmt, 'bold': True, 'font_size': 12, 'font_color': '#7F7F7F'}),
        'card_value': workbook.add_format({**base_fmt, 'bold': True, 'font_size': 24, 'font_color': THEME_COLOR_PRIMARY}),
        'card_sub': workbook.add_format({**base_fmt, 'font_size': 10, 'font_color': '#7F7F7F'}),
        
        # Source of Truth Header
        'meta_label': workbook.add_format({**base_fmt, 'bold': True, 'font_color': '#7F7F7F', 'font_size': 8}),
        'meta_value': workbook.add_format({**base_fmt, 'font_color': '#000000', 'font_size': 8}),

        # Yield Map
        # Yield Map - Percentage Format fix
        'yield_good': workbook.add_format({**base_fmt, 'bg_color': '#EBF1DE', 'font_color': '#006100', 'border': 1, 'align': 'center', 'num_format': '0.0%'}), # Greenish
        'yield_warn': workbook.add_format({**base_fmt, 'bg_color': '#FFEB9C', 'font_color': '#9C6500', 'border': 1, 'align': 'center', 'num_format': '0.0%'}), # Yellowish
        'yield_bad': workbook.add_format({**base_fmt, 'bg_color': '#FFC7CE', 'font_color': '#9C0006', 'border': 1, 'align': 'center', 'num_format': '0.0%'}), # Reddish
        
        # Hierarchy
        'group_l1': workbook.add_format({**base_fmt, 'bold': True, 'bg_color': '#F2F2F2', 'border': 1}), # Quadrant
        'group_l2': workbook.add_format({**base_fmt, 'indent': 1, 'border': 1}), # Defect
    }
    return formats

def _auto_fit_columns(worksheet, df: pd.DataFrame, start_col: int = 0, padding: int = 2):
    """Adjusts column widths based on content."""
    for i, col in enumerate(df.columns):
        # Calculate max length of data and column header
        max_len = max(
            df[col].astype(str).map(len).max() if not df[col].empty else 0,
            len(str(col))
        )
        worksheet.set_column(start_col + i, start_col + i, max_len + padding)

# --- SHEET 1: EXECUTIVE DASHBOARD ---
def _create_executive_dashboard(writer, formats, full_df, panel_rows, panel_cols, source_filename):
    workbook = writer.book
    sheet = workbook.add_worksheet('Executive Dashboard')
    sheet.hide_gridlines(2)
    
    # --- 0. Source of Truth Header Block ---
    # Rows 0-1 reserved for metadata
    sheet.write('A1', 'CONFIDENTIALITY:', formats['meta_label'])
    sheet.write('B1', 'INTERNAL USE ONLY', formats['meta_value'])
    sheet.write('D1', 'GENERATED:', formats['meta_label'])
    sheet.write('E1', datetime.now().strftime("%Y-%m-%d %H:%M:%S"), formats['meta_value'])
    sheet.write('A2', 'SOURCE HASH:', formats['meta_label'])
    sheet.write('B2', f"{abs(hash(source_filename)) % 10**8} (Verifiable)", formats['meta_value']) # Pseudo-hash
    
    # Header
    sheet.merge_range('B4:H4', 'Executive Defect Analysis Dashboard', formats['title'])
    sheet.write('B5', f'Source: {source_filename}', formats['subtitle'])
    
    start_row = 7

    # --- 1. Big KPIs ---
    total_defects = len(full_df)
    
    # Determine usage of verification for counts
    has_verif = 'Verification' in full_df.columns
    if has_verif:
        # True defects: Exclude specific safe codes? 
        # For this high level, strict true defects = everything NOT in safe list
        # Assuming filtered_df logic handles the primary view, but here we have full_df
        # Let's count "True Defects" (approximate logic provided previously)
        safe_codes = ['GE57', 'N', 'TA', 'FALSE'] 
        true_defects = full_df[~full_df['Verification'].isin(safe_codes)]
        true_count = len(true_defects)
        safe_count = total_defects - true_count
        
        # Yield Estimate (Simplified: 1 defect = 1 bad cell)
        # Real yield is geometric, but we stick to the KPI standard used in summary
        total_cells = (panel_rows * panel_cols) * 4 # 4 Quadrants usually? Or is full_df just one layer?
        # If full_df is multi-layer, total_cells needs to reflect that. 
        # Let's assume full_df is the scope of analysis. 
        # We'll calculate density.
    else:
        true_count = total_defects
        safe_count = 0
        
    start_row = 5
    
    # Metric Helper
    def write_card(col, title, value, sub):
        sheet.write(start_row, col, title, formats['card_title'])
        sheet.write(start_row + 1, col, value, formats['card_value'])
        sheet.write(start_row + 2, col, sub, formats['card_sub'])
        
    write_card(1, "Total Count", f"{total_defects:,}", "All recorded entries")
    write_card(3, "True Defects", f"{true_count:,}", "Actionable defects") 
    write_card(5, "Safe / False", f"{safe_count:,}", "Non-critical entries")
    
    # --- 1.5 Dynamic Executive Summary Text Box ---
    # Analyze data for top insight
    top_insight = "No significant defects found."
    if not full_df.empty:
        # Find top defect type
        top_defect = full_df['DEFECT_TYPE'].mode().iloc[0] if not full_df['DEFECT_TYPE'].empty else "N/A"
        # Find top quadrant
        top_quad = full_df['QUADRANT'].mode().iloc[0] if not full_df['QUADRANT'].empty else "N/A"
        top_insight = f"Primary Analysis: The dominant defect is '{top_defect}', most concentrated in Quarter {top_quad}."
        
    sheet.merge_range(start_row, 1, start_row + 2, 6, top_insight, workbook.add_format({
        'border': 1, 'bg_color': '#FFFFCC', 'valign': 'top', 'text_wrap': True, 'font_size': 10, 'font_name': FONT_MAIN
    }))
    start_row += 4

    # --- 2. Yield Map (2x2 Visual) ---
    map_start_row = start_row
    sheet.write(map_start_row, 1, "Quarter Yield Map", formats['subtitle'])
    
    quadrants = ['Q2', 'Q1', 'Q3', 'Q4'] # Visual layout: Q2 Q1 (Top), Q3 Q4 (Bottom) ? Standard convention varies.
    # Standard Math: Q2 | Q1
    #                -------
    #                Q3 | Q4
    
    # Yield Calc per Quad
    q_metrics = {}
    cap_per_quad = panel_rows * panel_cols if (panel_rows * panel_cols) > 0 else 1
    
    # Filter for Real Defects Only for Yield Map - Calculate Both Total (for False Alarm) and Real
    # "This Quarter kpi you are generating should show Real defects (False Alarms) ... defect count should be Just real one"
    
    for q in ['Q1', 'Q2', 'Q3', 'Q4']:
        # We start with the full DF filtered by quadrant to get TOTAL
        q_total_df = full_df[full_df['QUADRANT'] == q]
        q_total_count = len(q_total_df)
        
        # Calculate Real Defects
        q_real_df = filter_true_defects(q_total_df)
        q_real_count = len(q_real_df)
        
        # False Alarms
        q_false_count = q_total_count - q_real_count
        
        # Yield is based on (Total Cells - Bad Cells) / Total Cells
        # Using Real Defects count for yield calculation
        yield_pct = max(0, (cap_per_quad - q_real_count) / cap_per_quad)
        
        q_metrics[q] = {
            'real': q_real_count,
            'false': q_false_count,
            'yield': yield_pct
        }

    # Normalized colors (Red < 80%, Yellow < 95%, Green > 95%)
    def get_fmt(val):
        if val >= 0.95: return formats['yield_good']
        if val >= 0.80: return formats['yield_warn']
        return formats['yield_bad']
        
    # Draw 2x2 Grid
    # Row 1: Q2, Q1
    q2_data = q_metrics.get('Q2', {'real': 0, 'false': 0, 'yield': 1.0})
    q1_data = q_metrics.get('Q1', {'real': 0, 'false': 0, 'yield': 1.0})
    
    # Format: Q1- Real (Real): False (False)
    sheet.write(map_start_row + 2, 1, f"Q2- {q2_data['real']} (Real): {q2_data['false']} (False)", get_fmt(q2_data['yield']))
    sheet.write(map_start_row + 2, 2, f"Q1- {q1_data['real']} (Real): {q1_data['false']} (False)", get_fmt(q1_data['yield']))
    
    # Row 2: Q3, Q4
    q3_data = q_metrics.get('Q3', {'real': 0, 'false': 0, 'yield': 1.0})
    q4_data = q_metrics.get('Q4', {'real': 0, 'false': 0, 'yield': 1.0})
    
    sheet.write(map_start_row + 3, 1, f"Q3- {q3_data['real']} (Real): {q3_data['false']} (False)", get_fmt(q3_data['yield']))
    sheet.write(map_start_row + 3, 2, f"Q4- {q4_data['real']} (Real): {q4_data['false']} (False)", get_fmt(q4_data['yield']))
    
    sheet.set_column(1, 2, 20) # Wider columns for map boxes
    sheet.set_row(map_start_row + 2, 50)
    sheet.set_row(map_start_row + 3, 50)

    # --- 3. Layer / Source Comparison ---
    # Use SOURCE_FILE as proxy for Layer if available
    if 'SOURCE_FILE' in full_df.columns:
        layer_start_row = map_start_row + 6
        sheet.write(layer_start_row, 1, "Layer Performance", formats['subtitle'])
        
        # Group by Source
        layer_stats = full_df.groupby('SOURCE_FILE').size().reset_index(name='Count')
        layer_stats['% of Total'] = layer_stats['Count'] / total_defects
        layer_stats = layer_stats.sort_values('Count', ascending=False)
        
        # Table Header
        sheet.write(layer_start_row + 1, 1, "Layer / Source", formats['header'])
        sheet.write(layer_start_row + 1, 2, "Defect Count", formats['header'])
        sheet.write(layer_start_row + 1, 3, "% Contribution", formats['header'])
        
        r = layer_start_row + 2
        for _, row in layer_stats.iterrows():
            sheet.write(r, 1, row['SOURCE_FILE'], formats['cell'])
            sheet.write(r, 2, row['Count'], formats['int'])
            sheet.write(r, 3, row['% of Total'], formats['percent'])
            
            # Conditional Formatting "Heatmap" for % Contribution
            # Simple manual check for now
            if row['% of Total'] > 0.20:
                sheet.write(r, 3, row['% of Total'], formats['yield_bad'])
            elif row['% of Total'] > 0.10:
                sheet.write(r, 3, row['% of Total'], formats['yield_warn'])
            else:
                 sheet.write(r, 3, row['% of Total'], formats['percent']) # Standard

            r += 1
            
        sheet.set_column(1, 1, 40) # Wide source col
        
    # --- Print Settings ---
    sheet.set_landscape()
    sheet.set_paper(9) # A4
    sheet.fit_to_pages(1, 0) # Fit width to 1 page


# --- SHEET 2: DETAILED BREAKDOWN ---
def _create_granular_breakdown(writer, formats, full_df):
    workbook = writer.book
    sheet = workbook.add_worksheet('Detailed Breakdown')
    sheet.hide_gridlines(2)
    
    sheet.write('A1', 'Granular Defect Breakdown', formats['subtitle'])
    
    # Rename Quadrant -> Quarter
    headers = ['Quarter', 'Defect Type', 'Verification', 'Count', '% of Type', '% of Quad']
    for i, h in enumerate(headers):
        sheet.write(2, i, h, formats['header'])
        
    # Logic: Group by Quadrant -> Defect -> Verification
    # If Verification missing, just Quad -> Defect
    
    has_verif = 'Verification' in full_df.columns
    if not has_verif:
        # Create dummy column for uniform logic
        full_df['Verification'] = 'N/A'
        
    # Grouping
    # 1. Group by Quad, Defect, Verif
    grouped = full_df.groupby(['QUADRANT', 'DEFECT_TYPE', 'Verification']).size().reset_index(name='Count')
    grouped = grouped[grouped['Count'] > 0] # Remove zeros
    
    # 2. Aggregations for Percentages
    quad_sums = grouped.groupby('QUADRANT')['Count'].transform('sum')
    type_sums = grouped.groupby(['QUADRANT', 'DEFECT_TYPE'])['Count'].transform('sum')
    
    # Pre-calculate Defect Type Totals for "Summary Rows"
    # We want to show:
    # Q1 | Scratch | (Total) | 10 | 10% | ...
    #    |         | Real    |  8 | ...
    
    # We iterate manually to insert logic
    unique_quads = grouped['QUADRANT'].unique()
    
    row = 3
    
    for quad in unique_quads:
        quad_df = grouped[grouped['QUADRANT'] == quad]
        total_quad_defects = quad_df['Count'].sum()
        
        # New Quarter Section
        sheet.merge_range(row, 0, row, 5, f"Quarter: {quad} (Total: {total_quad_defects})", formats['group_l1'])
        row += 1
        
        unique_defects = quad_df['DEFECT_TYPE'].unique()
        for dtype in unique_defects:
            dtype_df = quad_df[quad_df['DEFECT_TYPE'] == dtype]
            total_type_defects = dtype_df['Count'].sum()
            pct_quad = total_type_defects / total_quad_defects
            
            # --- SUMMARY ROW (The "Parent") ---
            # Shows Defect Type Total
            sheet.write(row, 0, quad, formats['cell_center'])
            sheet.write(row, 1, dtype, formats['cell']) # Bold this?
            sheet.write(row, 2, "All Verifications", formats['cell']) # Explicit "All"
            sheet.write(row, 3, total_type_defects, formats['int'])
            sheet.write(row, 4, 1.0, formats['percent']) # 100% of itself
            sheet.write(row, 5, pct_quad, formats['percent'])
            
            # highlight the row slightly?
            sheet.set_row(row, None, formats['group_l2'])
            row += 1
            
            # --- CHILD ROWS (The Breakdown) ---
            if has_verif:
                for _, item in dtype_df.iterrows():
                    pct_type = item['Count'] / total_type_defects
                    
                    sheet.write(row, 0, "", formats['cell_center']) # Indent visually
                    sheet.write(row, 1, "", formats['cell'])
                    sheet.write(row, 2, item['Verification'], formats['cell'])
                    sheet.write(row, 3, item['Count'], formats['int'])
                    sheet.write(row, 4, pct_type, formats['percent']) # % of Type
                    sheet.write(row, 5, item['Count'] / total_quad_defects, formats['percent']) # % of Quad
                    
                    if item['Verification'] not in ['N', 'GE57', 'TA', 'FALSE', 'N/A']:
                         sheet.write(row, 2, item['Verification'], formats['cell']) # Could add red text formatting
                         
                    row += 1
        
        sheet.set_row(row, 5) # Small gap between quadrants
        row += 1
        
    _auto_fit_columns(sheet, grouped, 0)


# --- SHEET 3: INTERACTIVE DATA (SLICERS) ---
def _create_interactive_table(writer, formats, full_df):
    workbook = writer.book
    sheet = workbook.add_worksheet('Interactive Data')
    
    # Select Columns
    cols = ['QUADRANT', 'SIDE', 'DEFECT_TYPE', 'Verification', 'UNIT_INDEX_X', 'UNIT_INDEX_Y']
    # Filter to existing cols
    valid_cols = [c for c in cols if c in full_df.columns]
    data = full_df[valid_cols]
    
    # Write Header
    sheet.write('A1', 'Total Defect List (Use Slicers to Filter)', formats['subtitle'])
    
    # Add Table
    (max_row, max_col) = data.shape
    
    # 1. Write Data
    # We write data normally first? No, add_table handles data if we define range, 
    # BUT xlsxwriter add_table requires data to be in the cells. 
    # So we write data first using pandas to excel, then apply table on top?
    # Pandas to_excel writes data. We just need to define table over it.
    
    start_row = 3
    data.to_excel(writer, sheet_name='Interactive Data', startrow=start_row, index=False)
    
    # 2. Add Excel Table Definition
    # range: A4:F(max_row+4)
    # column letters
    end_col_char = xu.xl_col_to_name(max_col - 1)
    table_range = f"A{start_row+1}:{end_col_char}{start_row + 1 + max_row}"
    
    sheet.add_table(table_range, {
        'columns': [{'header': c} for c in data.columns],
        'style': 'TableStyleMedium2', # Blue banded
        'name': 'DefectTable'
    })
    
    # 3. Add Slicers
    # xlsxwriter 3.0+ supports slicers. Check availability.
    if hasattr(sheet, 'add_slicer'):
        try:
            # Slicer for Quadrant
            sheet.add_slicer(start_row, max_col + 2, {'name': 'DefectTable', 'column': 'QUADRANT', 'caption': 'Filter Quadrant'})
            
            # Slicer for Side (if exists)
            if 'SIDE' in data.columns:
                sheet.add_slicer(start_row, max_col + 6, {'name': 'DefectTable', 'column': 'SIDE', 'caption': 'Filter Side'})
                
            # Slicer for Defect Type
            sheet.add_slicer(start_row + 10, max_col + 2, {'name': 'DefectTable', 'column': 'DEFECT_TYPE', 'caption': 'Filter Defect'})
        except Exception as e:
            logger.warning(f"Failed to add slicers: {e}")
    else:
        logger.info("xlsxwriter version too old for Slicers. Skipping.")
    
    _auto_fit_columns(sheet, data, 0)
    sheet.set_column(max_col, max_col + 1, 3) # Gap


def generate_excel_report(
    full_df: pd.DataFrame,
    panel_rows: int,
    panel_cols: int,
    source_filename: str = "Sample Data",
    quadrant_selection: str = "All",
    verification_selection: str = "All"
) -> bytes:
    """
    Generates a comprehensive, McKinsey-style Excel report.
    """
    output_buffer = io.BytesIO()

    with pd.ExcelWriter(output_buffer, engine='xlsxwriter') as writer:
        workbook = writer.book
        formats = _define_formats(workbook)

        # 1. Executive Dashboard
        _create_executive_dashboard(writer, formats, full_df, panel_rows, panel_cols, source_filename)
        
        # 2. Granular Breakdown (Strict Hierarchy)
        _create_granular_breakdown(writer, formats, full_df)
        
        # 3. Interactive Data (Table + Slicers)
        _create_interactive_table(writer, formats, full_df)
        
        # 4. Old Summary Sheets (Optional - kept for compatibility but renamed/moved to end?)
        # Let's keep the Full List separately just in case 
        # _create_full_defect_list_sheet(writer, formats, full_df) 

    excel_bytes = output_buffer.getvalue()
    return excel_bytes

def generate_coordinate_list_report(defective_coords: set) -> bytes:
    """Generates simple coord list (No changes needed)."""
    output = io.BytesIO()
    if defective_coords:
        df = pd.DataFrame(list(defective_coords), columns=['UNIT_INDEX_X', 'UNIT_INDEX_Y'])
        df.sort_values(by=['UNIT_INDEX_Y', 'UNIT_INDEX_X'], inplace=True)
    else:
        df = pd.DataFrame(columns=['UNIT_INDEX_X', 'UNIT_INDEX_Y'])
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Defective_Cell_Locations')
    return output.getvalue()

