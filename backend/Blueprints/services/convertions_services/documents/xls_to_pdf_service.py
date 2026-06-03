import os
import shutil
import subprocess
import tempfile

def convert_xls_pdf(input_path, output_path): run_libreoffice_conversion(input_path, output_path, "pdf")

def run_libreoffice_conversion(input_path, output_path, output_extension):
    converter = find_office_converter()

    with tempfile.TemporaryDirectory() as temp_dir:
        command = [
             converter
            ,"--headless"
            ,"--convert-to"
            ,output_extension
            ,"--outdir"
            ,temp_dir
            ,input_path
        ]

        try:
            subprocess.run(
                 command
                ,stdout=subprocess.PIPE
                ,stderr=subprocess.PIPE
                ,check=True
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                "Nao foi possivel converter este arquivo com LibreOffice. "
                "Verifique se o arquivo abre normalmente e tente novamente."
            ) from exc

        converted_path = find_converted_file(temp_dir, input_path, output_extension)
        shutil.move(converted_path, output_path)

def find_office_converter():
    for command in ("soffice", "libreoffice"):
        converter = shutil.which(command)

        if converter: return converter

    for path in [
         r"C:\Program Files\LibreOffice\program\soffice.exe"
        ,r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"
    ]:
        if os.path.exists(path): return path

    raise RuntimeError("LibreOffice nao encontrado. Instale LibreOffice no servidor para converter arquivos Office.")


def find_converted_file(temp_dir, input_path, output_extension):
    expected_path = os.path.join(
         temp_dir
        ,f"{os.path.splitext(os.path.basename(input_path))[0]}.{output_extension}"
    )

    if os.path.exists(expected_path): return expected_path

    for filename in os.listdir(temp_dir):
        if filename.lower().endswith(f".{output_extension.lower()}"): return os.path.join(temp_dir, filename)

    raise RuntimeError("Arquivo final nao foi criado.")
