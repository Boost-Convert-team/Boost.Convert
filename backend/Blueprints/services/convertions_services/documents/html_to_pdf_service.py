from .html_conversion import PathLike, convert_html_to_pdf


def convert_html_pdf(input_path: PathLike, output_path: PathLike) -> None:
    convert_html_to_pdf(input_path, output_path)
