from playwright.sync_api import sync_playwright, expect

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://localhost:8501")

        # 1. Verify BU-XX button names
        expect(page.get_by_role("button", name="BU-01")).to_be_visible(timeout=60000)
        expect(page.get_by_role("button", name="BU-02")).to_be_visible(timeout=60000)
        expect(page.get_by_role("button", name="BU-03")).to_be_visible(timeout=60000)

        # 2. Verify "Still Alive" map labels and download button
        page.get_by_role("button", name="Still Alive").click()

        # Check for X-axis title
        expect(page.get_by_text("Unit Column Index")).to_be_visible(timeout=60000)
        # Check for Y-axis title
        expect(page.get_by_text("Unit Row Index")).to_be_visible(timeout=60000)

        # Check for the download button
        expect(page.get_by_role("button", name="Download Coordinate List")).to_be_visible(timeout=60000)

        page.screenshot(path="jules-scratch/verification/final_ui_verification.png")
        browser.close()

if __name__ == "__main__":
    run()