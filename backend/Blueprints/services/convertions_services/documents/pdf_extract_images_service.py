import zipfile
import fitz

def convert_pdf_extract_images(input_path, output_path):
    found_images = False
    seen_images = set()

    with fitz.open(input_path) as document:
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_STORED) as archive:
            for page_index, page in enumerate(document, start=1):
                for image_index, image_info in enumerate(page.get_images(full=True), start=1):
                    xref = image_info[0]

                    if xref in seen_images:
                        continue

                    seen_images.add(xref)
                    image = document.extract_image(xref)
                    archive.writestr(
                         f"pagina_{page_index}_imagem_{image_index}.{image.get('ext', 'png')}"
                        ,image["image"]
                    )
                    found_images = True

    if not found_images: raise ValueError("Nao encontrei imagens incorporadas neste PDF.")
