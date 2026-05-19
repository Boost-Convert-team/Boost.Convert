import os
import tempfile

from PIL import Image
from playwright.sync_api import sync_playwright

from Blueprints.services.conversions.conversion_option_values import get_image_quality

def convert_svg_jpg(input_path, output_path, options=None):
    options = options or {}
    temp_png = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name

    try:
        if not convert_with_cairosvg(input_path, temp_png):
            convert_with_playwright(input_path, temp_png)

        with Image.open(temp_png) as img:
            img.convert("RGB").save(output_path, "JPEG", quality=get_image_quality(options), optimize=True)

    finally:
        if os.path.exists(temp_png):
            os.remove(temp_png)

def convert_with_cairosvg(input_path, output_path):
    try:
        import cairosvg

        cairosvg.svg2png(url=input_path, write_to=output_path)
        return True
    except Exception:
        return False

def convert_with_playwright(input_path, output_path):
    svg_path = input_path.replace("\\", "/")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"file:///{svg_path}")
        page.screenshot(path=output_path, omit_background=True)
        browser.close()
