import os
import zipfile
import fitz

def convert_pdf_jpg(input_path, output_path):
    zoom = get_pdf_render_zoom()

    with fitz.open(input_path) as document:
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_STORED) as archive:
            for page_index, page in enumerate(document, start=1):
                pixmap = page.get_pixmap(
                    matrix=fitz.Matrix(zoom, zoom)
                    ,alpha=False
                )
                archive.writestr(f"page_{page_index}.jpg", pixmap.tobytes("jpeg"))


def get_pdf_render_zoom():
    try:
        return max(1.0, float(os.getenv("PDF_RENDER_ZOOM", "2.0")))
    except ValueError: return 2.0
