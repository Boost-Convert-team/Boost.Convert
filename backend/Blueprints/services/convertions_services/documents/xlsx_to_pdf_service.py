from .libreoffice_service import (
    PathLike,
    find_converted_file,
    find_office_converter,
    run_libreoffice_conversion,
)
from .office_pdf_fallback import convert_xlsx_to_pdf_fallback


def convert_excel_pdf(input_path: PathLike, output_path: PathLike) -> None:
    try:
        convert_xlsx_to_pdf_fallback(input_path, output_path)
        return
    except Exception:
        run_libreoffice_conversion(input_path, output_path, "pdf")
