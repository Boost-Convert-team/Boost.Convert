import json
import os
import zipfile

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
    ,"svg": lambda data: b"<svg" in data.lower()
    ,"wav": lambda data: data.startswith(b"RIFF") and data[8:12] == b"WAVE"
    ,"webp": lambda data: data.startswith(b"RIFF") and data[8:12] == b"WEBP"
    ,"wma": lambda data: data.startswith(b"\x30\x26\xb2\x75\x8e\x66\xcf\x11")
    ,"xls": lambda data: data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    ,"zip": lambda data: data.startswith(b"PK")
}
ZIP_ROOTS = {"docx": "word/", "pptx": "ppt/", "xlsx": "xl/"}
TEXT_EXTENSIONS = {"csv", "html", "htm", "md", "txt"}

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
        with zipfile.ZipFile(path) as archive: names = archive.namelist()
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
            if archive.testzip() is not None: return False, "Arquivo ZIP invalido."
    except zipfile.BadZipFile:
        return False, "Arquivo ZIP invalido."
    return True, None

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
