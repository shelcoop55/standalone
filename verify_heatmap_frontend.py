import time
from playwright.sync_api import sync_playwright

def run_verification():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Wide viewport to force expansion if not constrained
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        try:
            print("Navigating to app...")
            page.goto("http://localhost:8501", timeout=60000)
            page.wait_for_selector("text=Panel Defect Analysis Tool", timeout=60000)

            # 1. Click "Run Analysis" to load sample data
            print("Clicking 'Run Analysis'...")
            run_btn = page.get_by_role("button", name="Run Analysis")
            run_btn.click()

            # Wait for data to load
            print("Waiting for data load...")
            time.sleep(3) # Give it a moment for rerun

            # 2. Select "Heatmap" view
            print("Selecting Heatmap Analysis view...")
            page.get_by_text("Heatmap Analysis").click()
            time.sleep(3) # Wait for re-render

            # 3. Verify the "Unit Grid Density" chart
            # Use specific header locator
            header = page.get_by_role("heading", name="1. Unit Grid Density (Yield Loss)")
            header.wait_for()
            print("Heatmap visible.")

            # Scroll to it
            header.scroll_into_view_if_needed()
            time.sleep(2)

            # Take screenshot
            page.screenshot(path="verification_heatmap.png", full_page=False)
            print("Screenshot saved to verification_heatmap.png")

        except Exception as e:
            print(f"Error during verification: {e}")
            page.screenshot(path="error.png")
        finally:
            browser.close()

if __name__ == "__main__":
    run_verification()
