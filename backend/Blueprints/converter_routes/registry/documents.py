from Blueprints.services.convertions_services.documents.csv_to_xlsx_service import convert_csv_xlsx
from Blueprints.services.convertions_services.documents.doc_to_docx_service import convert_doc_docx
from Blueprints.services.convertions_services.documents.doc_to_pdf_service import convert_doc_pdf
from Blueprints.services.convertions_services.documents.docx_to_pdf_service import convert_docx_pdf
from Blueprints.services.convertions_services.documents.docx_to_txt_service import convert_docx_txt
from Blueprints.services.convertions_services.documents.docx_to_xlsx_service import convert_docx_xlsx
from Blueprints.services.convertions_services.documents.html_to_docx_service import convert_html_docx
from Blueprints.services.convertions_services.documents.html_to_pdf_service import convert_html_pdf
from Blueprints.services.convertions_services.documents.jpg_to_pdf_service import convert_jpg_pdf
from Blueprints.services.convertions_services.documents.json_to_csv_service import convert_json_csv
from Blueprints.services.convertions_services.documents.json_to_xlsx_service import convert_json_xlsx
from Blueprints.services.convertions_services.documents.md_to_docx_service import convert_markdown_docx
from Blueprints.services.convertions_services.documents.md_to_pdf_service import convert_markdown_pdf
from Blueprints.services.convertions_services.documents.odp_to_pdf_service import convert_odp_pdf
from Blueprints.services.convertions_services.documents.odp_to_pptx_service import convert_odp_pptx
from Blueprints.services.convertions_services.documents.ods_to_pdf_service import convert_ods_pdf
from Blueprints.services.convertions_services.documents.ods_to_xlsx_service import convert_ods_xlsx
from Blueprints.services.convertions_services.documents.odt_to_docx_service import convert_odt_docx
from Blueprints.services.convertions_services.documents.odt_to_pdf_service import convert_odt_pdf
from Blueprints.services.convertions_services.documents.pdf_compress_service import convert_pdf_compress
from Blueprints.services.convertions_services.documents.pdf_edit_service import convert_pdf_edit
from Blueprints.services.convertions_services.documents.pdf_extract_images_service import convert_pdf_extract_images
from Blueprints.services.convertions_services.documents.pdf_ocr_searchable_service import convert_pdf_ocr_searchable
from Blueprints.services.convertions_services.documents.pdf_protect_service import convert_pdf_protect
from Blueprints.services.convertions_services.documents.pdf_rotate_service import convert_pdf_rotate
from Blueprints.services.convertions_services.documents.pdf_split_service import convert_pdf_split
from Blueprints.services.convertions_services.documents.pdf_to_csv_service import convert_pdf_csv
from Blueprints.services.convertions_services.documents.pdf_to_docx_service import convert_pdf_docx
from Blueprints.services.convertions_services.documents.pdf_to_html_service import convert_pdf_html
from Blueprints.services.convertions_services.documents.pdf_to_jpg_service import convert_pdf_jpg
from Blueprints.services.convertions_services.documents.pdf_to_png_service import convert_pdf_png
from Blueprints.services.convertions_services.documents.pdf_to_pptx_service import convert_pdf_pptx
from Blueprints.services.convertions_services.documents.pdf_to_text_service import convert_pdf_txt
from Blueprints.services.convertions_services.documents.pdf_to_xlsx_service import convert_pdf_xlsx
from Blueprints.services.convertions_services.documents.pdf_unlock_service import convert_pdf_unlock
from Blueprints.services.convertions_services.documents.ppt_to_pdf_service import convert_ppt_pdf
from Blueprints.services.convertions_services.documents.ppt_to_pptx_service import convert_ppt_pptx
from Blueprints.services.convertions_services.documents.pptx_to_pdf_service import convert_pptx_pdf
from Blueprints.services.convertions_services.documents.txt_to_docx_service import convert_txt_docx
from Blueprints.services.convertions_services.documents.txt_to_pdf_service import convert_txt_pdf
from Blueprints.services.convertions_services.documents.xls_to_pdf_service import convert_xls_pdf
from Blueprints.services.convertions_services.documents.xls_to_xlsx_service import convert_xls_xlsx
from Blueprints.services.convertions_services.documents.xlsx_to_csv_service import convert_excel_csv
from Blueprints.services.convertions_services.documents.xlsx_to_docx_service import convert_excel_docx
from Blueprints.services.convertions_services.documents.xlsx_to_json_service import convert_excel_json
from Blueprints.services.convertions_services.documents.xlsx_to_pdf_service import convert_excel_pdf

from Blueprints.converter_routes.registry.models import SimpleConverterRoute


DOCUMENT_CONVERTER_ROUTES = (
    # Documents
    SimpleConverterRoute("csv_xlsx", "/convert/csv-to-xlsx", ("csv",), convert_csv_xlsx, "xlsx", "csv_to_xlsx"),
    SimpleConverterRoute("doc_docx", "/convert/doc-to-docx", ("doc",), convert_doc_docx, "docx", "doc_to_docx"),
    SimpleConverterRoute("doc_pdf", "/convert/doc-to-pdf", ("doc",), convert_doc_pdf, "pdf", "doc_to_pdf"),
    SimpleConverterRoute("docx_pdf", "/convert/docx-to-pdf", ("docx",), convert_docx_pdf, "pdf", "docx_to_pdf"),
    SimpleConverterRoute("docx_txt", "/convert/docx-to-txt", ("docx",), convert_docx_txt, "txt", "docx_to_txt"),
    SimpleConverterRoute("docx_xlsx", "/convert/docx-to-xlsx", ("docx",), convert_docx_xlsx, "xlsx", "docx_to_xlsx"),
    SimpleConverterRoute("html_docx", "/convert/html-to-docx", ("html", "htm"), convert_html_docx, "docx", "html_to_docx"),
    SimpleConverterRoute("html_pdf", "/convert/html-to-pdf", ("html", "htm"), convert_html_pdf, "pdf", "html_to_pdf"),
    SimpleConverterRoute("jpg_pdf", "/convert/jpg-to-pdf", ("jpg", "jpeg"), convert_jpg_pdf, "pdf", "jpg_to_pdf"),
    SimpleConverterRoute("json_csv", "/convert/json-to-csv", ("json",), convert_json_csv, "csv", "json_to_csv"),
    SimpleConverterRoute("json_xlsx", "/convert/json-to-xlsx", ("json",), convert_json_xlsx, "xlsx", "json_to_xlsx"),
    SimpleConverterRoute("md_docx", "/convert/md-to-docx", ("md",), convert_markdown_docx, "docx", "md_to_docx"),
    SimpleConverterRoute("md_pdf", "/convert/md-to-pdf", ("md",), convert_markdown_pdf, "pdf", "md_to_pdf"),
    SimpleConverterRoute("odp_pdf", "/convert/odp-to-pdf", ("odp",), convert_odp_pdf, "pdf", "odp_to_pdf"),
    SimpleConverterRoute("odp_pptx", "/convert/odp-to-pptx", ("odp",), convert_odp_pptx, "pptx", "odp_to_pptx"),
    SimpleConverterRoute("ods_pdf", "/convert/ods-to-pdf", ("ods",), convert_ods_pdf, "pdf", "ods_to_pdf"),
    SimpleConverterRoute("ods_xlsx", "/convert/ods-to-xlsx", ("ods",), convert_ods_xlsx, "xlsx", "ods_to_xlsx"),
    SimpleConverterRoute("odt_docx", "/convert/odt-to-docx", ("odt",), convert_odt_docx, "docx", "odt_to_docx"),
    SimpleConverterRoute("odt_pdf", "/convert/odt-to-pdf", ("odt",), convert_odt_pdf, "pdf", "odt_to_pdf"),
    SimpleConverterRoute("pdf_compress", "/convert/pdf-compress", ("pdf",), convert_pdf_compress, "pdf", "pdf_compress"),
    SimpleConverterRoute("pdf_edit", "/convert/pdf-edit", ("pdf",), convert_pdf_edit, "pdf", "pdf_edit"),
    SimpleConverterRoute("pdf_extract_images", "/convert/pdf-extract-images", ("pdf",), convert_pdf_extract_images, "zip", "pdf_extract_images"),
    SimpleConverterRoute("pdf_ocr_searchable", "/convert/pdf-ocr-searchable", ("pdf",), convert_pdf_ocr_searchable, "pdf", "pdf_ocr_searchable"),
    SimpleConverterRoute("pdf_protect", "/convert/pdf-protect", ("pdf",), convert_pdf_protect, "pdf", "pdf_protect"),
    SimpleConverterRoute("pdf_rotate", "/convert/pdf-rotate", ("pdf",), convert_pdf_rotate, "pdf", "pdf_rotate"),
    SimpleConverterRoute("pdf_split", "/convert/pdf-split", ("pdf",), convert_pdf_split, "zip", "pdf_split"),
    SimpleConverterRoute("pdf_csv", "/convert/pdf-to-csv", ("pdf",), convert_pdf_csv, "csv", "pdf_to_csv"),
    SimpleConverterRoute("pdf_docx", "/convert/pdf-to-docx", ("pdf",), convert_pdf_docx, "docx", "pdf_to_docx"),
    SimpleConverterRoute("pdf_html", "/convert/pdf-to-html", ("pdf",), convert_pdf_html, "html", "pdf_to_html"),
    SimpleConverterRoute("pdf_jpg", "/convert/pdf-to-jpg", ("pdf",), convert_pdf_jpg, "zip", "pdf_to_jpg"),
    SimpleConverterRoute("pdf_png", "/convert/pdf-to-png", ("pdf",), convert_pdf_png, "zip", "pdf_to_png"),
    SimpleConverterRoute("pdf_pptx", "/convert/pdf-to-pptx", ("pdf",), convert_pdf_pptx, "pptx", "pdf_to_pptx"),
    SimpleConverterRoute("pdf_txt", "/convert/pdf-to-txt", ("pdf",), convert_pdf_txt, "txt", "pdf_to_txt"),
    SimpleConverterRoute("pdf_xlsx", "/convert/pdf-to-xlsx", ("pdf",), convert_pdf_xlsx, "xlsx", "pdf_to_xlsx"),
    SimpleConverterRoute("pdf_unlock", "/convert/pdf-unlock", ("pdf",), convert_pdf_unlock, "pdf", "pdf_unlock"),
    SimpleConverterRoute("ppt_pdf", "/convert/ppt-to-pdf", ("ppt",), convert_ppt_pdf, "pdf", "ppt_to_pdf"),
    SimpleConverterRoute("ppt_pptx", "/convert/ppt-to-pptx", ("ppt",), convert_ppt_pptx, "pptx", "ppt_to_pptx"),
    SimpleConverterRoute("pptx_pdf", "/convert/pptx-to-pdf", ("pptx",), convert_pptx_pdf, "pdf", "pptx_to_pdf"),
    SimpleConverterRoute("txt_docx", "/convert/txt-to-docx", ("txt",), convert_txt_docx, "docx", "text_to_docx"),
    SimpleConverterRoute("txt_pdf", "/convert/txt-to-pdf", ("txt",), convert_txt_pdf, "pdf", "text_to_pdf"),
    SimpleConverterRoute("xls_pdf", "/convert/xls-to-pdf", ("xls",), convert_xls_pdf, "pdf", "xls_to_pdf"),
    SimpleConverterRoute("xls_xlsx", "/convert/xls-to-xlsx", ("xls",), convert_xls_xlsx, "xlsx", "xls_to_xlsx"),
    SimpleConverterRoute("xlsx_csv", "/convert/xlsx-to-csv", ("xlsx",), convert_excel_csv, "csv", "excel_to_csv"),
    SimpleConverterRoute("xlsx_docx", "/convert/xlsx-to-docx", ("xlsx",), convert_excel_docx, "docx", "excel_to_docx"),
    SimpleConverterRoute("xlsx_json", "/convert/xlsx-to-json", ("xlsx",), convert_excel_json, "json", "excel_to_json"),
    SimpleConverterRoute("xlsx_pdf", "/convert/xlsx-to-pdf", ("xlsx",), convert_excel_pdf, "pdf", "excel_to_pdf"),
)
