from .html_conversion import PathLike, convert_html_to_docx


def convert_html_docx(input_path: PathLike, output_path: PathLike) -> None:
    convert_html_to_docx(input_path, output_path)
