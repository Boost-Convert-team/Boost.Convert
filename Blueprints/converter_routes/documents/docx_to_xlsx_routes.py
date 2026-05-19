from flask import Blueprint
from Blueprints.services.conversions.documents.docx_to_xlsx_service import convert_docx_xlsx
from Blueprints.handler_convertions import handle_conversion

docx_xlsx_bp = Blueprint("docx_xlsx",__name__)
@docx_xlsx_bp.route("/convert/docx-to-xlsx", methods=["POST"])
def docx_to_xlsx():
    return handle_conversion(
         allowed_extension=["docx"]
        ,convert_function=convert_docx_xlsx
        ,output_extension="xlsx"
        ,tool_name="docx_to_xlsx"
    )
