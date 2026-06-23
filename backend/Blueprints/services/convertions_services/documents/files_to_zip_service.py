import os
import zipfile
from werkzeug.utils import secure_filename

def convert_files_zip(input_path, output_path, options=None):
    archive_filenames = (options or {}).get("archive_filenames", {})
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename in sorted(os.listdir(input_path)):
            path = os.path.join(input_path, filename)
            if os.path.abspath(path) == os.path.abspath(output_path):
                continue
            if os.path.isfile(path):
                archive.write(path, get_archive_filename(filename, archive_filenames))

def get_archive_filename(filename, archive_filenames):
    if filename in archive_filenames: return secure_archive_filename(archive_filenames[filename])
    if len(filename) > 4 and filename[:3].isdigit() and filename[3] == "_": return secure_archive_filename(filename[4:])
    return secure_archive_filename(filename)

def secure_archive_filename(filename: object) -> str:
    """Return a ZIP member name without user-controlled path segments.

    Example: secure_archive_filename("../report.pdf")
    """
    basename = os.path.basename(str(filename or "").replace("\\", "/"))
    return secure_filename(basename) or "arquivo"
