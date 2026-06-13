from .libreoffice_service import (
    PathLike,
    find_converted_file,
    find_office_converter,
    run_libreoffice_conversion,
)


def convert_ppt_pdf(input_path: PathLike, output_path: PathLike) -> None:
    run_libreoffice_conversion(input_path, output_path, "pdf")
