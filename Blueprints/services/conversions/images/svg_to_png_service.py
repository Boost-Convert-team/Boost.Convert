from playwright.sync_api import sync_playwright

def convert_svg_png(input_path, output_path):
    if convert_with_cairosvg(input_path, output_path):
        return

    convert_with_playwright(input_path, output_path)

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
