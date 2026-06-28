import os

from .libreoffice_service import (
    PathLike,
    find_converted_file,
    find_office_converter,
    run_libreoffice_conversion,
)
from .office_pdf_fallback import convert_docx_to_pdf_fallback


def convert_docx_pdf(input_path: PathLike, output_path: PathLike) -> None:
    try:
        convert_docx_to_pdf_fallback(input_path, output_path)
        if _has_pdf_output(output_path):
            return
    except Exception:
        pass

    try:
        run_libreoffice_conversion(input_path, output_path, "pdf")
        if _has_pdf_output(output_path):
            return
    except Exception:
        pass

    try:
        from docx2pdf import convert

        convert(input_path, output_path)
        if _has_pdf_output(output_path):
            return
    except Exception:
        pass

    raise RuntimeError("Arquivo final nao foi criado.")


def _has_pdf_output(output_path: PathLike) -> bool:
    return os.path.exists(output_path) and os.path.getsize(output_path) > 0
