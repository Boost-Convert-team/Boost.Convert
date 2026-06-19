from os import PathLike
from typing import Union


TextPath = Union[str, PathLike[str]]


def read_utf8_lines_preserving_text(input_path: TextPath) -> list[str]:
    """Read text without silently dropping undecodable bytes.

    Example: lines = read_utf8_lines_preserving_text("notes.md")
    """
    try:
        with open(input_path, "r", encoding="utf-8") as file:
            return file.readlines()
    except UnicodeDecodeError as exc:
        raise ValueError(f"Texto invalido: {input_path}; esperado UTF-8 preservavel.") from exc


def encode_latin1_pdf_line(line: str, input_path: TextPath) -> str:
    """Prepare text for the current FPDF backend without replacement.

    Example: pdf.multi_cell(0, 8, encode_latin1_pdf_line(line, path))
    """
    try:
        return line.encode("latin-1").decode("latin-1")
    except UnicodeEncodeError as exc:
        preview = line[:40]
        raise ValueError(f"Texto fora de Latin-1: {preview!r} em {input_path}; esperado caracteres Latin-1.") from exc
