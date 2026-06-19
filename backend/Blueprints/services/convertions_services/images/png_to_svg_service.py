from Blueprints.services.convertions_services.images.image_preservation import embed_raster_image_in_svg

def convert_png_svg(input_path, output_path): embed_raster_image_in_svg(input_path, output_path, "image/png")
