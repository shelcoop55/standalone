
import os
import time
from playwright.sync_api import sync_playwright

def verify_root_cause_layout():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Set viewport to ensure sidebar is visible
        page = browser.new_page(viewport={"width": 1600, "height": 900})

        try:
            print("Navigating...")
            page.goto("http://localhost:8501")

            # Wait for main app to load
            page.wait_for_selector("h1:has-text('Panel Defect Analysis Tool')", timeout=15000)

            # Check if we need to click Run Analysis
            # If "Welcome to the Panel Defect Analysis Tool!" is visible, we need to click Run.
            if page.is_visible("text=Welcome to the Panel Defect Analysis Tool!"):
                print("Welcome screen detected. Clicking Run Analysis...")

                # The sidebar form submit button "Run Analysis"
                # Use get_by_role button with name "Run Analysis"
                # Note: The emoji might be part of the name "🚀 Run Analysis"
                run_btn = page.get_by_role("button", name="Run Analysis")
                run_btn.click()

                # Wait for reload
                time.sleep(3)

            # Now wait for data to load (Sample data)
            print("Waiting for data load (BU-01 button)...")
            page.wait_for_selector("button:has-text('BU-01')", timeout=15000)

            print("Clicking Analysis Button...")
            analysis_btn = page.get_by_role("button", name="Analysis", exact=True)
            analysis_btn.wait_for(state="visible")
            analysis_btn.click()

            # Wait for the Sidebar to update
            print("Waiting for Analysis Dashboard in sidebar...")
            page.wait_for_selector("text=Analysis Dashboard", timeout=10000)

            time.sleep(1)

            print("Selecting Root Cause Analysis...")
            # Click the Radio button option.
            page.get_by_text("Root Cause Analysis").click()

            # Wait for the Root Cause specific controls to appear
            print("Waiting for Cross-Section Controls...")
            page.wait_for_selector("text=Cross-Section Controls", timeout=5000)

            time.sleep(2) # Allow sliders to render

            # Take screenshot
            os.makedirs("verification_screenshots", exist_ok=True)
            page.screenshot(path="verification_screenshots/root_cause_ui.png", full_page=True)
            print("Done.")

        except Exception as e:
            print(f"Error: {e}")
            page.screenshot(path="verification_screenshots/error_state_final.png")
            raise e
        finally:
            browser.close()

if __name__ == "__main__":
    verify_root_cause_layout()
