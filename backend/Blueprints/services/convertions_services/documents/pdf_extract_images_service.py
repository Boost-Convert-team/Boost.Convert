import os
import tempfile
import zipfile
import fitz

def convert_pdf_extract_images(input_path, output_path):
    image_paths = []
    seen_images = set()

    with fitz.open(input_path) as document:
        with tempfile.TemporaryDirectory() as temp_dir:
            for page_index, page in enumerate(document, start=1):
                for image_index, image_info in enumerate(page.get_images(full=True), start=1):
                    xref = image_info[0]

                    if xref in seen_images:
                        continue

                    seen_images.add(xref)
                    image = document.extract_image(xref)
                    image_path = os.path.join(
                         temp_dir
                        ,f"pagina_{page_index}_imagem_{image_index}.{image.get('ext', 'png')}"
                    )

                    with open(image_path, "wb") as file: file.write(image["image"])

                    image_paths.append(image_path)

            if not image_paths: raise ValueError("Nao encontrei imagens incorporadas neste PDF.")

            with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for image_path in image_paths: archive.write(image_path, os.path.basename(image_path))
