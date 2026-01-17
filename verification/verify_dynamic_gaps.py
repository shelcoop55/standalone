from playwright.sync_api import sync_playwright, expect
import time

def verify_dynamic_gaps(page):
    print("Navigating to app...")
    page.goto("http://localhost:8501")

    # Wait for the app to load
    print("Waiting for app to load...")
    expect(page.get_by_text("Control Panel")).to_be_visible(timeout=20000)

    print("Expanding Advanced Configuration...")
    # Look for the expander summary
    expander = page.get_by_text("Advanced Configuration")
    expander.click()

    # Wait for the inputs to be visible
    print("Waiting for inputs...")

    # Verify new inputs exist using EXACT matching for the label if possible,
    # but for "Dynamic Gap X (mm)" standard label matching is fine.
    print("Checking for Dynamic Gap inputs...")
    expect(page.get_by_label("Dynamic Gap X (mm)")).to_be_visible()
    expect(page.get_by_label("Dynamic Gap Y (mm)")).to_be_visible()

    # Verify old "Gap X" and "Gap Y" are GONE.
    # We use exact=True to avoid "Dynamic Gap X (mm)" matching "Gap X (mm)"
    print("Verifying old Gap inputs are gone...")
    expect(page.get_by_label("Gap X (mm)", exact=True)).not_to_be_visible()
    expect(page.get_by_label("Gap Y (mm)", exact=True)).not_to_be_visible()

    # Take a screenshot
    print("Taking screenshot...")
    page.screenshot(path="verification/dynamic_gaps_verification.png")
    print("Screenshot saved.")

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            verify_dynamic_gaps(page)
        except Exception as e:
            print(f"Error: {e}")
            page.screenshot(path="verification/error_screenshot.png")
        finally:
            browser.close()
