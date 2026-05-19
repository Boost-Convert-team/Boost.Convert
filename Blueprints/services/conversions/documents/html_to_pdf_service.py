from playwright.sync_api import sync_playwright

def convert_html_pdf(input_path, output_path):
    html_path = input_path.replace("\\", "/")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"file:///{html_path}")
        page.pdf(path=output_path, format="A4")

        browser.close()