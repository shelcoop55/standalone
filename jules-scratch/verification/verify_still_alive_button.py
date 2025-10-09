from playwright.sync_api import sync_playwright, expect
import time

def run_verification():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # 1. Navigate to the app
            page.goto("http://localhost:8501", timeout=30000)

            # Wait for the app to be ready
            expect(page.get_by_role("heading", name="📊 Panel Defect Analysis Tool", level=1)).to_be_visible(timeout=20000)

            # 2. Run analysis with default sample data
            page.get_by_role("button", name="Run Analysis").click()

            # 3. Verify all view buttons are visible
            expect(page.get_by_role("button", name="Layer 1")).to_be_visible(timeout=15000)
            expect(page.get_by_role("button", name="Layer 2")).to_be_visible()
            expect(page.get_by_role("button", name="Layer 3")).to_be_visible()
            still_alive_button = page.get_by_role("button", name="Still Alive")
            expect(still_alive_button).to_be_visible()

            # 4. Click the "Still Alive" button
            still_alive_button.click()

            # 5. Verify the header and a metric are visible
            expect(page.get_by_role("heading", name="Still Alive Panel Yield Map")).to_be_visible(timeout=15000)
            expect(page.get_by_text("Panel Yield")).to_be_visible()

            # 6. Take screenshot for visual confirmation
            page.screenshot(path="jules-scratch/verification/still_alive_button_verification.png")
            print("Screenshot of 'Still Alive' view (button layout) captured successfully.")

        except Exception as e:
            print(f"An error occurred during verification: {e}")
            page.screenshot(path="jules-scratch/verification/error.png")
        finally:
            browser.close()

if __name__ == "__main__":
    run_verification()