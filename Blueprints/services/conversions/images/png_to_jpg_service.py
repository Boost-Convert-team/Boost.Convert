from PIL import Image
from Blueprints.services.conversions.conversion_option_values import get_image_quality

def convert_png_jpg(input_path, output_path, options=None):
    options = options or {}
    quality = get_image_quality(options)

    with Image.open(input_path) as img:
        if img.mode in ("RGBA", "LA"):
            background = Image.new("RGB", img.size, (255,255,255))
            background.paste(img, mask=img.getchannel("A"))
            background.save(output_path, "JPEG", quality=quality, optimize=True)
        else:
            img.convert("RGB").save(output_path, "JPEG", quality=quality, optimize=True)
