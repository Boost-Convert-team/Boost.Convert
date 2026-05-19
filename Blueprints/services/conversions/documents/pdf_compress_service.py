import fitz

def convert_pdf_compress(input_path, output_path, options=None):
    options = options or {}
    compression_level = options.get("compression_level", "balanced")

    save_options = {
        "garbage": 4,
        "deflate": True,
        "clean": True,
    }

    if compression_level == "strong":
        save_options["deflate_images"] = True
        save_options["deflate_fonts"] = True

    elif compression_level == "light":
        save_options["garbage"] = 3

    with fitz.open(input_path) as document:
        document.save(output_path, **save_options)
