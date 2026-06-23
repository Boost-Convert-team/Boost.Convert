import json
import os
import zipfile

MAX_ZIP_ENTRIES = 1000
MAX_ZIP_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
MAX_ZIP_RATIO_ENTRY_BYTES = 10 * 1024 * 1024
MAX_ZIP_COMPRESSION_RATIO = 100
SIGNATURES = {
     "aac": lambda data: len(data) >= 2 and data[0] == 0xFF and data[1] in (0xF1, 0xF9)
    ,"avi": lambda data: data.startswith(b"RIFF") and data[8:12] == b"AVI "
    ,"doc": lambda data: data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    ,"flac": lambda data: data.startswith(b"fLaC")
    ,"heic": lambda data: data[4:8] == b"ftyp" and data[8:12] in (b"heic", b"heix", b"hevc", b"mif1", b"msf1")
    ,"jpg": lambda data: data.startswith(b"\xff\xd8\xff")
    ,"jpeg": lambda data: data.startswith(b"\xff\xd8\xff")
    ,"mkv": lambda data: data.startswith(b"\x1a\x45\xdf\xa3")
    ,"mov": lambda data: data[4:8] == b"ftyp"
    ,"mp3": lambda data: data.startswith(b"ID3") or (len(data) >= 2 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0)
    ,"mp4": lambda data: data[4:8] == b"ftyp"
    ,"odp": lambda data: data.startswith(b"PK")
    ,"ods": lambda data: data.startswith(b"PK")
    ,"odt": lambda data: data.startswith(b"PK")
    ,"ogg": lambda data: data.startswith(b"OggS")
    ,"pdf": lambda data: data.startswith(b"%PDF")
    ,"png": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")
    ,"ppt": lambda data: data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    ,"pptx": lambda data: data.startswith(b"PK")
    ,"rtf": lambda data: data.lstrip().startswith(b"{\\rtf")
    ,"svg": lambda data: b"<svg" in data.lower()
    ,"wav": lambda data: data.startswith(b"RIFF") and data[8:12] == b"WAVE"
    ,"webp": lambda data: data.startswith(b"RIFF") and data[8:12] == b"WEBP"
    ,"wma": lambda data: data.startswith(b"\x30\x26\xb2\x75\x8e\x66\xcf\x11")
    ,"xls": lambda data: data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    ,"zip": lambda data: data.startswith(b"PK")
}
ZIP_ROOTS = {"docx": "word/", "pptx": "ppt/", "xlsx": "xl/"}
TEXT_EXTENSIONS = {"csv", "html", "htm", "md", "rtf", "txt"}
GENERIC_MIME_TYPES = {"", "application/octet-stream", "binary/octet-stream"}
ALLOWED_MIME_TYPES = {
    "aac": {"audio/aac", "audio/x-aac", "audio/vnd.dlna.adts"},
    "avi": {"video/x-msvideo", "video/avi"},
    "csv": {"text/csv", "application/csv", "application/vnd.ms-excel"},
    "doc": {"application/msword", "application/octet-stream"},
    "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip"},
    "flac": {"audio/flac", "audio/x-flac"},
    "heic": {"image/heic", "image/heif"},
    "html": {"text/html"},
    "htm": {"text/html"},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "json": {"application/json", "text/json"},
    "md": {"text/markdown", "text/plain"},
    "mkv": {"video/x-matroska"},
    "mov": {"video/quicktime"},
    "mp3": {"audio/mpeg", "audio/mp3"},
    "mp4": {"video/mp4", "audio/mp4", "application/mp4"},
    "odp": {"application/vnd.oasis.opendocument.presentation", "application/zip"},
    "ods": {"application/vnd.oasis.opendocument.spreadsheet", "application/zip"},
    "odt": {"application/vnd.oasis.opendocument.text", "application/zip"},
    "ogg": {"audio/ogg", "application/ogg"},
    "pdf": {"application/pdf"},
    "png": {"image/png"},
    "ppt": {"application/vnd.ms-powerpoint", "application/octet-stream"},
    "pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation", "application/zip"},
    "rtf": {"application/rtf", "application/x-rtf", "text/rtf", "text/plain"},
    "svg": {"image/svg+xml", "text/xml", "application/xml"},
    "txt": {"text/plain"},
    "wav": {"audio/wav", "audio/x-wav"},
    "webm": {"video/webm", "audio/webm"},
    "webp": {"image/webp"},
    "wma": {"audio/x-ms-wma"},
    "xls": {"application/vnd.ms-excel", "application/octet-stream"},
    "xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/zip"},
    "zip": {"application/zip", "application/x-zip-compressed"},
}

def validate_upload_mime(file, extension):
    extension = extension.lower()
    mimetype = (getattr(file, "mimetype", "") or "").split(";")[0].strip().lower()
    if mimetype in GENERIC_MIME_TYPES:
        return True, None
    if extension in TEXT_EXTENSIONS and mimetype.startswith("text/"):
        return True, None
    if mimetype in ALLOWED_MIME_TYPES.get(extension, set()):
        return True, None
    return False, "O tipo MIME do arquivo nao corresponde ao formato enviado."

def validate_upload_header(file, extension):
    extension = extension.lower()
    current_position = file.stream.tell()
    header = file.stream.read(8192)
    file.stream.seek(current_position)
    if extension in SIGNATURES and not SIGNATURES[extension](header): return False, "O conteudo do arquivo nao parece bater com a extensao enviada."
    if extension in TEXT_EXTENSIONS and b"\x00" in header: return False, "Arquivo de texto invalido."
    return True, None

def validate_saved_file(path, extension):
    extension = extension.lower()
    if extension in ZIP_ROOTS: return validate_office_file(path, ZIP_ROOTS[extension])
    if extension == "json": return validate_json_file(path)
    if extension == "svg": return validate_svg_file(path)
    if extension == "zip": return validate_zip_file(path)
    return True, None

def validate_office_file(path, required_root):
    try:
        with zipfile.ZipFile(path) as archive:
            archive_valid, archive_message = validate_zip_archive(archive)
            if not archive_valid: return False, archive_message
            names = archive.namelist()
    except zipfile.BadZipFile:
        return False, "Arquivo Office invalido."
    
    if "[Content_Types].xml" not in names: return False, "Arquivo Office sem estrutura esperada."
    if not any(name.startswith(required_root) for name in names): return False, "Arquivo Office nao corresponde ao formato esperado."

    return True, None

def validate_json_file(path):
    try:
        with open(path, "r", encoding="utf-8") as file: json.load(file)
    except Exception:
        return False, "JSON invalido."
    return True, None

def validate_svg_file(path):
    try:
        with open(path, "r", encoding="utf-8") as file: content = file.read(4096).lower()
    except UnicodeDecodeError:
        return False, "SVG invalido."
    if "<svg" not in content: return False, "SVG sem tag principal."
    return True, None

def validate_zip_file(path):
    try:
        with zipfile.ZipFile(path) as archive:
            archive_valid, archive_message = validate_zip_archive(archive)
            if not archive_valid: return False, archive_message
            if archive.testzip() is not None: return False, "Arquivo ZIP invalido."
    except zipfile.BadZipFile:
        return False, "Arquivo ZIP invalido."
    return True, None

def validate_zip_archive(archive: zipfile.ZipFile) -> tuple[bool, str | None]:
    """Validate ZIP structure before accepting user-controlled archives.

    Example: validate_zip_archive(archive)
    """
    infos = archive.infolist()
    if len(infos) > MAX_ZIP_ENTRIES: return False, "Arquivo ZIP contem entradas demais."
    paths_valid, paths_message = validate_zip_member_paths(infos)
    if not paths_valid: return False, paths_message
    size_valid, size_message = validate_zip_uncompressed_size(infos)
    if not size_valid: return False, size_message
    return True, None

def validate_zip_member_paths(infos: list[zipfile.ZipInfo]) -> tuple[bool, str | None]:
    for info in infos:
        if is_unsafe_zip_member_name(info.filename):
            return False, "Arquivo ZIP contem caminho inseguro."
    return True, None

def is_unsafe_zip_member_name(filename: object) -> bool:
    normalized = str(filename or "").replace("\\", "/").strip("/")
    if not normalized or ":" in normalized:
        return True
    return any(part in {"", ".", ".."} for part in normalized.split("/"))

def validate_zip_uncompressed_size(infos: list[zipfile.ZipInfo]) -> tuple[bool, str | None]:
    total_size = sum(info.file_size for info in infos)
    if total_size > MAX_ZIP_UNCOMPRESSED_BYTES: return False, "Arquivo ZIP expande alem do limite permitido."
    if any(has_dangerous_zip_ratio(info) for info in infos): return False, "Arquivo ZIP possui compressao suspeita."
    return True, None

def has_dangerous_zip_ratio(info: zipfile.ZipInfo) -> bool:
    if info.file_size < MAX_ZIP_RATIO_ENTRY_BYTES or info.compress_size <= 0:
        return False
    return (info.file_size / info.compress_size) > MAX_ZIP_COMPRESSION_RATIO

def remove_file_quietly(path):
    try:
        if path and os.path.exists(path): os.remove(path)
    except OSError: pass

def remove_job_input_quietly(input_path, output_path=None):
    if not input_path: return
    
    if os.path.isfile(input_path):
        remove_file_quietly(input_path)
        return
    if os.path.isdir(input_path):
        for filename in os.listdir(input_path):
            file_path = os.path.join(input_path, filename)

            if output_path and os.path.abspath(file_path) == os.path.abspath(output_path): continue

            remove_file_quietly(file_path)
