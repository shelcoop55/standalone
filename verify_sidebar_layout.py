
import os
import time
from playwright.sync_api import sync_playwright

def verify_sidebar_layout():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 900})

        try:
            print("Navigating...")
            page.goto("http://localhost:8501")

            # Wait for main app
            page.wait_for_selector("h1:has-text('Panel Defect Analysis Tool')", timeout=15000)

            # Click Run Analysis if needed
            if page.is_visible("text=Welcome to the Panel Defect Analysis Tool!"):
                print("Clicking Run Analysis...")
                page.get_by_role("button", name="Run Analysis").click()
                time.sleep(3)

            # Wait for data load (Layer buttons appear)
            page.wait_for_selector("button:has-text('Layer')", timeout=10000)

            # 1. Verify 'Analysis' button is GONE from main view selector
            print("Verifying 'Analysis' button removal from main page...")
            analysis_btn = page.get_by_role("button", name="Analysis", exact=True)
            if analysis_btn.is_visible():
                # Double check it's not the sidebar button (Sidebar one is 'Show Analysis Dashboard' or inside 'Analysis Tools')
                # But 'exact=True' with name='Analysis' should match 'Analysis' button if it existed.
                # The sidebar expander header is '🔍 Analysis Tools'. The button inside is '🚀 Show Analysis Dashboard'.
                # So 'Analysis' exact match should be safe.
                print("FAIL: 'Analysis' button still visible on main page!")
            else:
                print("SUCCESS: 'Analysis' button not found (as expected).")

            # 2. Verify Sidebar Controls
            print("Verifying Sidebar 'Analysis Tools'...")

            # Try to find the button inside directly.
            # We use a partial match for the button name to handle the emoji.
            show_btn = page.get_by_role("button", name="Show Analysis Dashboard")

            if not show_btn.is_visible():
                print("Button not visible. Toggling 'Analysis Tools' expander...")
                # It might be closed.
                # Use a specific selector for the summary/header of the expander
                expander_header = page.locator("summary").filter(has_text="Analysis Tools")
                if expander_header.is_visible():
                    expander_header.click()
                    time.sleep(1)
                else:
                    # Fallback to text match
                    page.get_by_text("Analysis Tools").click()
                    time.sleep(1)

            # Check again
            if show_btn.is_visible():
                 print("SUCCESS: 'Show Analysis Dashboard' button found.")
            else:
                 raise Exception("FAIL: 'Show Analysis Dashboard' button not found even after toggle.")

            # 3. Activate Analysis View
            print("Clicking 'Show Analysis Dashboard'...")
            show_btn.click()
            time.sleep(3)

            # 4. Verify Main Content is Analysis Dashboard
            # Look for "Heatmap Analysis" header (default view)
            print("Verifying Dashboard Activation...")
            if page.get_by_role("heading", name="Heatmap Analysis").is_visible():
                print("SUCCESS: Dashboard activated (Heatmap View).")
            else:
                raise Exception("FAIL: Dashboard did not activate or wrong default view.")

            # 5. Change Subview in Sidebar to Stress
            print("Switching to Stress Map in Sidebar...")
            # Radio button group "Select Module". Find the label "Stress Map"
            # Since radio buttons are often <label><input>...</label> or nearby.
            # Playwright get_by_label works if label is associated.
            # Streamlit radio buttons: The label "Stress Map" is one of the options.
            # We can just click the text "Stress Map" inside the sidebar.

            # We need to make sure we don't click "Stress Map Settings" header.
            # The option is ViewMode.STRESS.value which is likely just "Stress Map".

            stress_option = page.locator("label").filter(has_text="Stress Map").first
            stress_option.click()
            time.sleep(2)

            if page.get_by_role("heading", name="Cumulative Stress Map Analysis").is_visible():
                 print("SUCCESS: Switched to Stress Map via Sidebar.")
            else:
                 raise Exception("FAIL: Did not switch to Stress Map.")

            # 6. Screenshot
            os.makedirs("verification_screenshots", exist_ok=True)
            page.screenshot(path="verification_screenshots/sidebar_layout_verification.png", full_page=True)
            print("Done.")

        except Exception as e:
            print(f"Error: {e}")
            page.screenshot(path="verification_screenshots/sidebar_error_retry.png")
            raise e
        finally:
            browser.close()

if __name__ == "__main__":
    verify_sidebar_layout()
