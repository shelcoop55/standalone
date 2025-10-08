from playwright.sync_api import sync_playwright, expect
import time

def run_verification():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_viewport_size({"width": 1920, "height": 1080})

        # 1. Navigate to the app and load the data
        page.goto("http://localhost:8501")
        run_analysis_button = page.get_by_role("button", name="🚀 Run Analysis")
        expect(run_analysis_button).to_be_visible(timeout=20000)
        run_analysis_button.click()
        expect(page.get_by_text("Panel Defect Map", exact=False)).to_be_visible(timeout=20000)

        # 2. Ensure we are in Defect View
        expect(page.get_by_text("Panel Defect Map", exact=False)).to_be_visible()

        # 3. Verify the new Verification Summary section is present
        summary_title = page.get_by_text("Verification Summary", exact=True)
        expect(summary_title).to_be_visible()

        # 4. Verify the metric labels are present
        expect(page.get_by_text("True Defects (T)", exact=True)).to_be_visible()
        expect(page.get_by_text("False Defects (F)", exact=True)).to_be_visible()
        expect(page.get_by_text("Acceptable Defects (TA)", exact=True)).to_be_visible()

        # 5. Take a screenshot of the page to show the final layout
        page.screenshot(path="jules-scratch/verification/summary_metrics_layout.png")

        browser.close()

if __name__ == "__main__":
    run_verification()