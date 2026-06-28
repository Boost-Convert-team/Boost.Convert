import math
import os
from datetime import date, datetime, time
from pathlib import Path
from typing import Iterable, Sequence

import fitz
from docx import Document
from openpyxl import load_workbook
from openpyxl.cell.cell import Cell
from openpyxl.utils import get_column_letter


PathLike = str | os.PathLike[str]

A4 = fitz.paper_rect("a4")
A4_LANDSCAPE = fitz.Rect(0, 0, A4.height, A4.width)
MARGIN = 42
TEXT_COLOR = (0.12, 0.14, 0.18)
BORDER_COLOR = (0.78, 0.80, 0.84)
HEADER_FILL = (0.94, 0.95, 0.97)


class PdfWriter:
    def __init__(self, document: fitz.Document, page_rect: fitz.Rect = A4):
        self.document = document
        self.page_rect = page_rect
        self.page = self.document.new_page(width=page_rect.width, height=page_rect.height)
        self.y = MARGIN

    @property
    def usable_width(self) -> float:
        return self.page_rect.width - (MARGIN * 2)

    @property
    def bottom(self) -> float:
        return self.page_rect.height - MARGIN

    def ensure_space(self, height: float) -> None:
        if self.y + height <= self.bottom:
            return
        self.page = self.document.new_page(width=self.page_rect.width, height=self.page_rect.height)
        self.y = MARGIN

    def draw_heading(self, text: str, size: float = 18) -> None:
        height = max(32, estimate_text_height(text, size, self.usable_width))
        self.ensure_space(height)
        self.page.insert_textbox(
            fitz.Rect(MARGIN, self.y, self.page_rect.width - MARGIN, self.y + height),
            text,
            fontsize=size,
            fontname="hebo",
            color=TEXT_COLOR,
        )
        self.y += height + 8

    def draw_paragraph(self, text: str, size: float = 11) -> None:
        text = normalize_text(text)
        if not text:
            self.y += 8
            return

        height = max(28, estimate_text_height(text, size, self.usable_width) + 8)
        self.ensure_space(height)
        self.page.insert_textbox(
            fitz.Rect(MARGIN, self.y, self.page_rect.width - MARGIN, self.y + height),
            text,
            fontsize=size,
            fontname="helv",
            color=TEXT_COLOR,
        )
        self.y += height + 6

    def draw_table(self, rows: Sequence[Sequence[str]], header: bool = False) -> None:
        rows = [[normalize_text(cell) for cell in row] for row in rows if any(normalize_text(cell) for cell in row)]
        if not rows:
            return

        column_count = max(len(row) for row in rows)
        column_width = self.usable_width / max(1, column_count)

        self.y += 4
        for row_index, row in enumerate(rows):
            row_values = list(row) + [""] * (column_count - len(row))
            row_height = max(
                24,
                max(estimate_text_height(value, 9.2, column_width - 10) for value in row_values) + 16,
            )
            self.ensure_space(row_height)
            x = MARGIN
            fill = HEADER_FILL if header and row_index == 0 else None
            for value in row_values:
                rect = fitz.Rect(x, self.y, x + column_width, self.y + row_height)
                self.page.draw_rect(rect, color=BORDER_COLOR, fill=fill, width=0.45)
                self.page.insert_textbox(
                    rect + (5, 5, -5, -4),
                    value,
                    fontsize=9.2,
                    fontname="helv",
                    color=TEXT_COLOR,
                )
                x += column_width
            self.y += row_height
        self.y += 10


def convert_docx_to_pdf_fallback(input_path: PathLike, output_path: PathLike) -> None:
    source = Document(input_path)
    pdf = fitz.open()
    writer = PdfWriter(pdf)

    if source.core_properties.title:
        writer.draw_heading(source.core_properties.title)

    for block in iter_docx_blocks(source):
        if isinstance(block, list):
            writer.draw_table(block, header=True)
            continue

        text, style_name = block
        if style_name.startswith("heading 1") or style_name.startswith("titulo 1"):
            writer.draw_heading(text, 18)
        elif style_name.startswith("heading") or style_name.startswith("titulo"):
            writer.draw_heading(text, 14)
        else:
            writer.draw_paragraph(text)

    save_pdf(pdf, output_path)


def convert_xlsx_to_pdf_fallback(input_path: PathLike, output_path: PathLike) -> None:
    workbook = load_workbook(input_path, data_only=True)
    pdf = fitz.open()

    for sheet in workbook.worksheets:
        if sheet.sheet_state != "visible":
            continue
        rows = get_sheet_rows(sheet)
        if not rows:
            continue

        writer = PdfWriter(pdf, A4_LANDSCAPE)
        writer.draw_heading(sheet.title, 16)
        draw_sheet_table(writer, sheet, rows)

    if pdf.page_count == 0:
        writer = PdfWriter(pdf, A4_LANDSCAPE)
        writer.draw_paragraph("Planilha sem dados visiveis.")

    save_pdf(pdf, output_path)


def iter_docx_blocks(document: Document) -> Iterable[tuple[str, str] | list[list[str]]]:
    body = document.element.body
    paragraph_map = {paragraph._element: paragraph for paragraph in document.paragraphs}
    table_map = {table._element: table for table in document.tables}

    for child in body.iterchildren():
        if child in paragraph_map:
            paragraph = paragraph_map[child]
            text = paragraph.text.strip()
            style_name = (paragraph.style.name if paragraph.style else "").strip().lower()
            if text:
                yield text, style_name
        elif child in table_map:
            table = table_map[child]
            yield [[cell.text.strip() for cell in row.cells] for row in table.rows]


def get_sheet_rows(sheet) -> list[list[Cell]]:
    rows = []
    for row in sheet.iter_rows():
        if any(cell.value not in (None, "") for cell in row):
            rows.append(list(row))

    while rows and not any(cell.value not in (None, "") for cell in rows[-1]):
        rows.pop()

    if not rows:
        return []

    last_column = max(
        index
        for row in rows
        for index, cell in enumerate(row)
        if cell.value not in (None, "")
    )
    return [row[: last_column + 1] for row in rows]


def draw_sheet_table(writer: PdfWriter, sheet, rows: Sequence[Sequence[Cell]]) -> None:
    widths = get_scaled_column_widths(sheet, len(rows[0]), writer.usable_width)
    for row_index, row in enumerate(rows):
        values = [format_cell_value(cell) for cell in row]
        heights = [
            estimate_text_height(value, 8.5, max(24, widths[index] - 8)) + 14
            for index, value in enumerate(values)
        ]
        row_height = max(22, min(78, max(heights) if heights else 22))
        writer.ensure_space(row_height)

        x = MARGIN
        for column_index, cell in enumerate(row):
            width = widths[column_index]
            rect = fitz.Rect(x, writer.y, x + width, writer.y + row_height)
            fill = get_cell_fill(cell, row_index)
            writer.page.draw_rect(rect, color=BORDER_COLOR, fill=fill, width=0.45)
            writer.page.insert_textbox(
                rect + (4, 4, -4, -3),
                values[column_index],
                fontsize=8.5,
                fontname="hebo" if row_index == 0 else "helv",
                color=TEXT_COLOR,
            )
            x += width
        writer.y += row_height


def get_scaled_column_widths(sheet, column_count: int, usable_width: float) -> list[float]:
    widths = []
    for index in range(1, column_count + 1):
        letter = get_column_letter(index)
        configured_width = sheet.column_dimensions[letter].width or 10
        widths.append(max(42, min(150, configured_width * 6.2)))

    total_width = sum(widths) or 1
    scale = usable_width / total_width
    return [width * scale for width in widths]


def format_cell_value(cell: Cell) -> str:
    value = cell.value
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, time):
        return value.strftime("%H:%M")
    if isinstance(value, float):
        if math.isfinite(value) and value.is_integer():
            return str(int(value))
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def get_cell_fill(cell: Cell, row_index: int) -> tuple[float, float, float] | None:
    color = cell.fill.fgColor
    rgb = color.rgb if color and color.type == "rgb" else None
    if rgb and len(rgb) == 8 and rgb[:2] != "00":
        try:
            return tuple(int(rgb[index : index + 2], 16) / 255 for index in (2, 4, 6))
        except ValueError:
            return HEADER_FILL if row_index == 0 else None
    return HEADER_FILL if row_index == 0 else None


def estimate_text_height(text: str, font_size: float, width: float) -> float:
    if not text:
        return font_size * 1.35
    average_char_width = max(1, font_size * 0.48)
    chars_per_line = max(8, int(width / average_char_width))
    lines = sum(max(1, math.ceil(len(line) / chars_per_line)) for line in text.splitlines() or [text])
    return lines * font_size * 1.65


def normalize_text(value) -> str:
    return str(value or "").replace("\t", " ").strip()


def save_pdf(pdf: fitz.Document, output_path: PathLike) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(path)
    pdf.close()

    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError("Arquivo final nao foi criado.")
