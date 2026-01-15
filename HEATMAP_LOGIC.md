# Heatmap Analysis Logic: Technical Documentation

This document explains the technical implementation and analytical logic behind the "Smoothed Density Contour Map" (Heatmap) in the Panel Defect Analysis Dashboard.

## 1. Core Logic: Server-Side Aggregation

The heatmap implementation moved from a client-side approach (sending raw points to the browser) to a **Server-Side Aggregation** model. This was done to handle large datasets (100k+ defects) with sub-second latency.

### How it works:
1.  **Input:** A list of defect coordinates `(x, y)` from the filtered dataset.
2.  **Aggregation (`numpy.histogram2d`):**
    - The Python backend creates a 2D grid (matrix) representing the physical panel.
    - It counts how many defects fall into each grid cell.
    - **Resolution:** The grid resolution is dynamic, controlled by the "Smoothing" slider.
        - *Formula:* `num_bins = 50 + (20 - smoothing_factor) * 5`
        - Higher smoothing = Fewer, larger bins (smoother look).
        - Lower smoothing = More, smaller bins (sharper detail).
3.  **Output:** A small $M \times N$ matrix of integers (Z-values) is sent to the frontend, instead of $N$ coordinate pairs.

## 2. Algorithmic Correctness Features

Standard heatmaps often distort data at the edges or ignore physical gaps. We implemented specific logic to match the semiconductor panel reality.

### A. Hard Boundary Conditions
*   **Problem:** Standard smoothing algorithms "bleed" density into the empty space outside the panel (negative coordinates), causing edge hotspots to appear weaker than they are (dilution).
*   **Solution:** We enforce strict limits on the histogram range: `[[0, PANEL_WIDTH], [0, PANEL_HEIGHT]]`. Any probability mass that would "smooth" off the edge is essentially contained, providing a true representation of edge density.

### B. Quadrant Gap Masking
*   **Context:** The panel consists of 4 Quadrants separated by a physical `GAP_SIZE`.
*   **Problem:** A naive heatmap treats the gap as valid space. A hotspot near the gap would look continuous, suggesting defects exists in the empty air between quadrants.
*   **Solution (Gap Masking):**
    - We calculate the histogram over the *entire* global coordinate system.
    - **Post-Processing:** We mathematically define the "Crossbar" region corresponding to the gap.
    - We force the Z-values (Density) in this gap region to `NaN` (Not a Number) or `0`.
    - **Result:** The heatmap visually breaks at the crossbar, correctly isolating the quadrants.

## 3. Top Defect Driver Logic (Tooltips)

The heatmap provides analytical depth via the "Top Cause" tooltip.

### Logic:
1.  **Iterative Binning:** Instead of just counting *all* defects, the algorithm iterates through the top distinct `DEFECT_TYPE`s (e.g., Nick, Short, Open).
2.  **Stacked Histograms:** It calculates a separate density grid for *each* defect type.
3.  **ArgMax:** For every cell $(i, j)$ in the grid, it compares the counts of all defect types.
4.  **Assignment:** It assigns the label of the defect type with the *highest count* to that cell.
5.  **Visualization:** When you hover over a red hotspot, the tooltip queries this "Driver Map" and displays: *Top Cause: Copper Void*.

## 4. Rendering Strategy

*   **Engine:** Plotly `go.Contour`.
*   **Color Scale:** 'Turbo' (High contrast, perceptually uniform).
*   **Overlays:** Individual defect points are overlaid using `go.Scattergl` (WebGL enabled). This ensures that while the heatmap shows the *trend*, the user can still see the exact *location* of outliers without crashing the browser.
