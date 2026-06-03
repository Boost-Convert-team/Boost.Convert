import os
import zipfile

def convert_files_zip(input_path, output_path):
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename in sorted(os.listdir(input_path)):
            path = os.path.join(input_path, filename)
            if os.path.isfile(path):
                archive.write(path, get_archive_filename(filename))

def get_archive_filename(filename):
    if len(filename) > 4 and filename[:3].isdigit() and filename[3] == "_": return filename[4:]
    return filename
