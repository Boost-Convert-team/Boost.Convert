from flask import Blueprint
from Blueprints.services.conversions.documents.md_to_docx_service import convert_markdown_docx
from Blueprints.handler_convertions import handle_conversion

md_docx_bp = Blueprint("md_docx",__name__)
@md_docx_bp.route("/convert/md-to-docx", methods=["POST"])
def md_to_docx():
    return handle_conversion(
         allowed_extension=["md"]
        ,convert_function=convert_markdown_docx
        ,output_extension="docx"
        ,tool_name="md_to_docx"
    )