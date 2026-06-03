from Blueprints.services.convertions_services.ocr.ocr_to_text_service import convert_image_ocr_txt, convert_pdf_ocr_txt

from Blueprints.converter_routes.registry.models import SimpleConverterRoute


OCR_CONVERTER_ROUTES = (
    # OCR
    SimpleConverterRoute("image_ocr_txt", "/convert/image-ocr-to-txt", ("jpg", "jpeg", "png", "webp", "heic"), convert_image_ocr_txt, "txt", "image_ocr_to_txt"),
    SimpleConverterRoute("pdf_ocr_txt", "/convert/pdf-ocr-to-txt", ("pdf",), convert_pdf_ocr_txt, "txt", "pdf_ocr_to_txt"),
)
