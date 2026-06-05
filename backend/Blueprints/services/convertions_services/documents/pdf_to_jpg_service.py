import os
import tempfile
import zipfile
import fitz

def convert_pdf_jpg(input_path, output_path):
    zoom = get_pdf_render_zoom()

    with fitz.open(input_path) as document:
        with tempfile.TemporaryDirectory() as temp_dir:
            image_paths = []

            for page_index, page in enumerate(document, start=1):
                pixmap = page.get_pixmap(
                    matrix=fitz.Matrix(zoom, zoom)
                    ,alpha=False
                )
                image_path = os.path.join(temp_dir, f"page_{page_index}.jpg")
                pixmap.save(image_path)
                image_paths.append(image_path)

            with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for image_path in image_paths:
                    archive.write(image_path, os.path.basename(image_path))


def get_pdf_render_zoom():
    try:
        return max(1.0, float(os.getenv("PDF_RENDER_ZOOM", "1.5")))
    except ValueError: return 1.5
