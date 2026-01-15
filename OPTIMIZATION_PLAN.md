# Optimization Plan: Panel Defect Analysis Dashboard

**Role:** Senior Full-Stack Performance Engineer
**Target:** Performance Optimization of Historical/Analytical Heatmap & System Architecture

## Executive Summary
The following checklist outlines high-impact technical changes designed to resolve latency issues in the Heatmap feature and improve overall application responsiveness. The strategy focuses on moving computation from Client-Side (Browser) to Server-Side (Python) and minimizing data transfer.

---

## 1. Session State vs. Caching Strategy
**Goal:** Reduce memory bloat in user sessions and prevent redundant serialization.

- [ ] **Refactor `SessionStore` to hold Data References:**
    - **Current State:** `st.session_state['layer_data']` stores the entire `PanelData` object (containing heavy DataFrames). This increases memory usage per user and slows down Streamlit's rerun cycle due to state serialization.
    - **Action:** Modify `src/state.py` to store only a unique **Dataset ID** (hash of uploaded files) in `st.session_state`.
- [ ] **Leverage `st.cache_data` for Data Retrieval:**
    - **Current State:** Data is loaded via `load_data` (cached), but then copied into Session State.
    - **Action:** Update `app.py` and views to retrieve the `PanelData` object directly from the `@st.cache_data` decorated function using the Dataset ID. This ensures the heavy object resides in the global server cache (shared across sessions where possible) rather than duplicated in every user's session state.

## 2. Payload Optimization (Heatmap Specific)
**Goal:** Drastically reduce the JSON payload size sent to the frontend.

- [ ] **Server-Side Histogram Calculation:**
    - **Current State:** `src/plotting.py` uses `go.Histogram2dContour(x=..., y=...)`. This sends **all raw X/Y coordinates** to the browser, forcing the client's JavaScript engine to compute the density distribution. For large datasets (>100k points), this causes significant latency.
    - **Action:** Replace `go.Histogram2dContour` with:
        1.  **Numpy Aggregation:** Use `np.histogram2d` in Python to calculate the density matrix (Z-values) server-side.
        2.  **Pre-computed Rendering:** Pass the calculated Z-matrix to `go.Contour` (or `go.Heatmap`).
    - **Impact:** Reduces payload from $O(N)$ (number of defects) to $O(W \times H)$ (grid resolution).

## 3. Database / Data Query Tuning
**Goal:** Prevent calculation on read.

- [ ] **Pre-Aggregate Density Grids:**
    - **Current State:** Density is calculated on-the-fly during plotting.
    - **Action:** Extend `PanelData` or `load_data` to pre-calculate standard density grids (e.g., 50x50, 100x100 bins) immediately upon file upload. Store these lightweight matrices alongside the raw DataFrames.
- [ ] **Implement Columnar Storage (Optional but Recommended):**
    - **Action:** If memory pressure persists, convert `pd.DataFrame` storage in `load_data` to **PyArrow** backed DataFrames or simple dictionary-of-arrays to reduce overhead compared to standard Pandas objects.

## 4. Rendering Engine (Plotly Optimization)
**Goal:** Improve Frame Rate (FPS) and Interaction fluidity.

- [ ] **Enable WebGL for Scatter Plots:**
    - **Current State:** `src/plotting.py` uses `go.Scatter` for defect markers (overlay on heatmap and other views). This uses SVG rendering, which degrades performance significantly above 1,000 points.
    - **Action:** Replace all instances of `go.Scatter` with **`go.Scattergl`** in `create_defect_traces`, `create_multi_layer_defect_map`, and `create_density_contour_map`.
    - **Note:** WebGL renders points on the GPU, allowing smooth panning/zooming even with 100k+ points.

## 5. Miscellaneous
- [ ] **Disable Hover on Large Contours:**
    - **Action:** For the Heatmap/Contour view, set `hoverinfo='skip'` or simplify the tooltip to only show the Z-value (Density) rather than individual point details, unless at high zoom levels.
