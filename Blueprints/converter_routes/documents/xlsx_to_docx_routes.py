from flask import Blueprint
from Blueprints.services.conversions.documents.xlsx_to_docx_service import convert_excel_docx
from Blueprints.handler_convertions import handle_conversion

xlsx_docx_bp = Blueprint("xlsx_docx",__name__)
@xlsx_docx_bp.route("/convert/xlsx-to-docx", methods=["POST"])
def xlsx_to_docx():
    return handle_conversion(
         allowed_extension=["xlsx"]
        ,convert_function=convert_excel_docx
        ,output_extension="docx"
        ,tool_name="excel_to_docx"
    )