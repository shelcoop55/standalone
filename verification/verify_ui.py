from playwright.sync_api import sync_playwright

def verify_ui():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto("http://localhost:8503")
            page.wait_for_load_state("networkidle")

            # Wait for sidebar
            page.wait_for_selector("[data-testid='stSidebar']")

            # Expand "Data Source & Configuration"
            # It seems it is expanded by default.

            # Scroll the sidebar to the bottom to ensure we see the new inputs
            # Sidebar is usually in a scrollable container.
            # Try to find the new inputs.

            # Check for "Plot Origin Configuration"
            loc = page.get_by_text("Plot Origin Configuration")
            if loc.count() > 0:
                print("Found 'Plot Origin Configuration' text.")
                loc.scroll_into_view_if_needed()
            else:
                print("ERROR: 'Plot Origin Configuration' text NOT found.")

            # Take screenshot of sidebar
            # We can try to take a full page screenshot to see everything
            page.screenshot(path="verification/full_page.png", full_page=True)
            print("Full page screenshot taken.")

            # Also try to specifically screenshot the Plot Origin section if found
            if loc.count() > 0:
                # Get the parent container or surrounding area?
                # Just screenshot the viewport after scrolling
                page.screenshot(path="verification/viewport_scrolled.png")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    verify_ui()
