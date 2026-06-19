import base64
from os import PathLike
from typing import Union

from PIL import Image


ImagePath = Union[str, PathLike[str]]


def embed_raster_image_in_svg(input_path: ImagePath, output_path: ImagePath, mime_type: str) -> None:
    """Wrap raster pixels in SVG without vector tracing.

    Example: embed_raster_image_in_svg("logo.png", "logo.svg", "image/png")
    """
    with Image.open(input_path) as image:
        width, height = image.size
    if width < 1 or height < 1:
        raise ValueError(f"Imagem invalida: {(width, height)}; esperado largura e altura positivas.")
    encoded_image = _encode_image_file(input_path)
    _write_embedded_svg(output_path, mime_type, encoded_image, width, height)


def save_jpeg_preserving_visual(image: Image.Image, output_path: ImagePath, quality: int = 100) -> None:
    """Save JPEG with minimal avoidable visual degradation.

    Example: save_jpeg_preserving_visual(image, "photo.jpg", 95)
    """
    rgb_image = _flatten_transparency_on_white(image) if _image_has_alpha(image) else image.convert("RGB")
    save_options: dict[str, object] = {"quality": quality, "optimize": True, "subsampling": 0}
    if image.info.get("icc_profile"):
        save_options["icc_profile"] = image.info["icc_profile"]
    rgb_image.save(output_path, "JPEG", **save_options)


def save_webp_lossless(image: Image.Image, output_path: ImagePath) -> None:
    """Save WebP without lossy quality loss or alpha removal.

    Example: save_webp_lossless(image, "image.webp")
    """
    webp_image = image.convert("RGBA") if _image_has_alpha(image) else image.copy()
    save_options: dict[str, object] = {"lossless": True, "method": 6, "exact": True}
    if image.info.get("icc_profile"):
        save_options["icc_profile"] = image.info["icc_profile"]
    webp_image.save(output_path, "WEBP", **save_options)


def copy_pdf_compatible_image(image: Image.Image) -> Image.Image:
    """Create a PDF-safe image while keeping visible pixels stable.

    Example: pdf_image = copy_pdf_compatible_image(image)
    """
    if _image_has_alpha(image):
        return _flatten_transparency_on_white(image)
    copied_image = image.convert("RGB")
    return copied_image.copy()


def _image_has_alpha(image: Image.Image) -> bool:
    if image.mode in {"RGBA", "LA"}:
        return True
    has_palette_transparency = image.mode == "P" and "transparency" in image.info
    return has_palette_transparency


def _flatten_transparency_on_white(image: Image.Image) -> Image.Image:
    rgba_image = image.convert("RGBA")
    background = Image.new("RGBA", rgba_image.size, (255, 255, 255, 255))
    background.alpha_composite(rgba_image)
    return background.convert("RGB")


def _encode_image_file(input_path: ImagePath) -> str:
    with open(input_path, "rb") as file:
        image_bytes = file.read()
    if not image_bytes:
        raise ValueError(f"Imagem vazia: {input_path}; esperado arquivo com bytes.")
    return base64.b64encode(image_bytes).decode("ascii")


def _write_embedded_svg(
    output_path: ImagePath,
    mime_type: str,
    encoded_image: str,
    width: int,
    height: int,
) -> None:
    svg_text = _build_embedded_svg(mime_type, encoded_image, width, height)
    with open(output_path, "w", encoding="utf-8") as file:
        file.write(svg_text)


def _build_embedded_svg(mime_type: str, encoded_image: str, width: int, height: int) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        f'<image width="{width}" height="{height}" href="data:{mime_type};base64,{encoded_image}"/>'
        "</svg>"
    )
