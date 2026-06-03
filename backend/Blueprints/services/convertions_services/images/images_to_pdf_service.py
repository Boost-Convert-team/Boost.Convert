import os
from PIL import Image

def convert_images_pdf(input_path, output_path):
    register_heif_support()

    image_paths = [
        os.path.join(input_path, filename)
        for filename in sorted(os.listdir(input_path))
        if os.path.isfile(os.path.join(input_path, filename))
    ]
    images = []

    for path in image_paths:
        with Image.open(path) as image:
            images.append(image.convert("RGB").copy())

    if not images: raise ValueError("Envie pelo menos uma imagem.")

    first, rest = images[0], images[1:]
    first.save(output_path, "PDF", save_all=True, append_images=rest)


def register_heif_support():
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        pass
