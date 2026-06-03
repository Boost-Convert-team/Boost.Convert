from flask import Blueprint
from Blueprints.handlers.conversion_handlers import handle_file_collection_conversion
from Blueprints.services.convertions_services.documents.files_to_zip_service import convert_files_zip

files_zip_bp = Blueprint("files_zip", __name__, url_prefix="/convert")

@files_zip_bp.route("/files-to-zip", methods=["POST"])
def files_zip():
    return handle_file_collection_conversion(
         allowed_extensions=['aac', 'avi', 'csv', 'doc', 'docx', 'flac', 'heic', 'html', 'htm', 'jpeg', 'jpg', 'json', 'md', 'mkv', 'mov', 'mp3', 'mp4', 'odp', 'ods', 'odt', 'ogg', 'pdf', 'png', 'ppt', 'pptx', 'svg', 'txt', 'wav', 'webm', 'webp', 'wma', 'xls', 'xlsx', 'zip']
        ,convert_function=convert_files_zip
        ,output_extension="zip"
        ,tool_name="files_to_zip"
        ,output_filename="boost_converter_arquivos.zip"
        ,original_label="Arquivos para ZIP"
    )
