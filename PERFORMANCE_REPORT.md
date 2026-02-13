# Performance Analysis Report

## Executive Summary
This report identifies 10 key performance bottlenecks in the Panel Defect Analysis application. The analysis focused on the backend data processing (`src/io/`, `src/analytics/`) and frontend visualization rendering (`src/plotting/renderers/`, `src/plotting/generators/`), specifically targeting responsiveness and heatmap generation issues reported with datasets of 4,000-10,000 rows.

## Critical Issues (High Impact on Responsiveness)

### 1. O(N*M) Shape Generation in "Still Alive" Map
**Location:** `src/plotting/renderers/maps.py` -> `create_still_alive_figure` / `_create_still_alive_map_shapes`
**Issue:** The code iterates through every single cell in the panel grid (Rows × Columns) and creates a dictionary object representing a rectangle shape for `layout.shapes`.
**Impact:** For a fine-grained grid (e.g., 100x100), this generates 10,000 shape objects. Sending this massive JSON payload to the frontend freezes the browser and causes significant rendering lag.
**Recommendation:** Use `go.Heatmap` or `go.Image` to render the grid colors as a single trace, rather than thousands of vector shapes.

### 2. Slow Python Loops in Heatmap Coordinate Calculation
**Location:** `src/plotting/renderers/maps.py` -> `create_stress_heatmap`
**Issue:** When `view_mode="Quarterly"`, the code uses nested Python `for` loops (`for r in range(rows): for c in range(cols):`) to calculate physical coordinates for every cell.
**Impact:** Python loops are slow. With high-resolution panels, this calculation blocks the server thread, delaying the response.
**Recommendation:** Vectorize this logic using NumPy meshgrids and broadcasting to calculate all coordinates in a single operation.

### 3. Inefficient Tooltip String Generation
**Location:** `src/analytics/stress.py` -> `aggregate_stress_data_from_df`
**Issue:** The function iterates over `grouped_cells` and manually concatenates strings to build HTML tooltips for every cell with defects.
**Impact:** String operations in a loop are expensive. As defect density increases, this function becomes a major bottleneck during data aggregation.
**Recommendation:** Use vectorized string operations or defer tooltip generation to the frontend using Plotly's `hovertemplate` more effectively.

## Major Issues (Significant Processing Overhead)

### 4. Repeated DataFrame Filtering in Trace Generation
**Location:** `src/plotting/generators/traces.py` -> `create_defect_traces`
**Issue:** The code iterates through every unique defect type (or verification code) and performs a full DataFrame filter (`df[df[group_col] == group_val]`) for each iteration.
**Impact:** This scans the entire dataset $K$ times (where $K$ is the number of defect types). For 10,000 rows and 20 defect types, this is 200,000 row checks.
**Recommendation:** Use `df.groupby(group_col)` to iterate over groups efficiently without repeated filtering.

### 5. Redundant String Normalization
**Location:** `src/analytics/verification.py` -> `filter_true_defects` (and related helpers)
**Issue:** The helper function `true_defect_filter` calls `.str.upper()` on the 'Verification' column every time it is invoked (which is frequent).
**Impact:** String normalization is relatively slow. Doing it repeatedly on the same data wastes CPU cycles.
**Recommendation:** Normalize the 'Verification' column to uppercase once during the `load_data` phase and store it.

### 6. Excessive Payload Size for Hover Data
**Location:** `src/plotting/renderers/maps.py` (and related) -> All Heatmaps
**Issue:** The backend constructs full HTML strings (including `<b>`, `<br>`, etc.) for every cell's hover text and sends this as a large array to the browser.
**Impact:** This increases the network transfer size and memory usage on the client side.
**Recommendation:** Send only the raw data (counts, types) and use Plotly's client-side formatting (hovertemplate) to construct the HTML string.

### 7. Redundant Data Copying in Analysis
**Location:** `src/analytics/yield_analysis.py` -> `get_cross_section_matrix`
**Issue:** Inside the loop over layers, the code creates a copy of the dataframe (`df.copy()`) before filtering.
**Impact:** This triggers memory allocation and data copying for every layer, which is unnecessary overhead.
**Recommendation:** Perform filtering on the original dataframe or use views/masks to avoid full copies.

## Minor Issues (Optimization Opportunities)

### 8. Inefficient Grid Line Generation
**Location:** `src/plotting/generators/shapes.py` -> `create_grid_shapes`
**Issue:** Grid lines are added as individual line shapes in a loop.
**Impact:** While less critical than the rectangle shapes, adding hundreds of line objects still adds overhead to the Plotly layout serialization and rendering.
**Recommendation:** Use a single path shape (SVG path) to draw the grid or use Plotly's native axis grid functionality if alignment permits.

### 9. Scatter Plot Overheads for Large Datasets
**Location:** `src/plotting/renderers/maps.py` -> `create_defect_map_figure`
**Issue:** Plotting 10,000 individual scatter points with unique hover data can be heavy for the browser's WebGL or SVG renderer.
**Impact:** Pan and zoom operations may become jerky.
**Recommendation:** Use `go.Scattergl` (WebGL) instead of `go.Scatter` (SVG) for datasets larger than a few thousand points.

### 10. Synchronous Blocking Execution
**Location:** General
**Issue:** All data processing and plotting logic runs synchronously on the main Streamlit thread.
**Impact:** The UI becomes unresponsive while the server is processing a request (e.g., switching views or loading data).
**Recommendation:** While Streamlit is synchronous by default, heavy computations could be offloaded to background threads or cached more aggressively to improve perceived responsiveness.
