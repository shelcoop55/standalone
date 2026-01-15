from playwright.sync_api import sync_playwright
import time
import os

def run_verification():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("Navigating to app...")
        page.goto("http://localhost:8501", timeout=60000)

        # Wait for "Control Panel"
        try:
            page.wait_for_selector("text=Control Panel", timeout=20000)
        except:
             print("Control Panel not found. App might not be loaded.")
             return

        # Check if we are already analyzing (shouldn't be in new session)
        if page.is_visible("text=Panel Defect Analysis Tool") and page.is_visible("text=Layer"):
             # Reset
             if page.is_visible("button:has-text('Reset Analysis')"):
                  page.click("button:has-text('Reset Analysis')")
                  time.sleep(2)

        # Upload files
        print("Uploading files...")
        file_input = page.locator('input[type="file"]')

        # We need sample files.
        import glob
        valid_files = glob.glob("*.xlsx")
        valid_files = [os.path.abspath(f) for f in valid_files][:2]

        if not valid_files:
            print("No xlsx files found for testing.")
            return

        file_input.set_input_files(valid_files)
        time.sleep(2)

        # Click Run Analysis
        print("Clicking 'Run Analysis'...")
        page.wait_for_selector("button:has-text('Run Analysis')", state="visible")
        page.get_by_role("button", name="Run Analysis").click()

        # Wait for data load
        print("Waiting for data load...")
        try:
            page.wait_for_selector("text=Panel Defect Map", timeout=30000)
        except:
            print("Timeout waiting for analysis results.")
            return

        print("Layer Inspection Loaded.")

        # Navigate to Analysis Page
        print("Switching to Analysis Page...")
        page.click("button:has-text('Analysis Page')")
        time.sleep(3)

        # Check Map View Toggle (Should be ABSENT)
        if page.is_visible("text=Map View") and page.is_visible("text=Quarterly"):
             print("FAILURE: Map View Toggle Found (Should be removed).")
        else:
             print("SUCCESS: Map View Toggle NOT found.")

        page.screenshot(path="verification_analysis_final.png")
        print("Final screenshot saved.")

if __name__ == "__main__":
    run_verification()
