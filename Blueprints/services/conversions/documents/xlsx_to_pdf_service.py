import pandas as pd
import tempfile
import os
from playwright.sync_api import sync_playwright

def convert_excel_pdf(input_path, output_path):
    df = pd.read_excel(input_path)
    html_content = df.to_html(index=False)

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as temp_html:
        temp_html.write(html_content)
        temp_html_path = temp_html.name

    try:
        html_path = temp_html_path.replace("\\", "/")

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()

            page.goto(f"file:///{html_path}")
            page.pdf(path=output_path,format="A4")

            browser.close()

    finally: 
        if os.path.exists(temp_html_path): os.remove(temp_html_path)