import os
import tempfile
import zipfile
import fitz

def convert_pdf_split(input_path, output_path, options=None):
    with fitz.open(input_path) as source_pdf:
        page_groups = parse_page_ranges((options or {}).get("page_ranges"), source_pdf.page_count)

        with tempfile.TemporaryDirectory() as temp_dir:
            split_paths = []

            for index, page_indexes in enumerate(page_groups, start=1):
                split_pdf = fitz.open()

                try:
                    for page_index in page_indexes:
                        split_pdf.insert_pdf(source_pdf, from_page=page_index, to_page=page_index)

                    split_path = os.path.join(temp_dir, f"pdf_{index}.pdf")
                    split_pdf.save(split_path, garbage=4, deflate=True)
                    split_paths.append(split_path)

                finally: split_pdf.close()

            with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in split_paths:
                    archive.write(path, os.path.basename(path))


def parse_page_ranges(page_ranges, page_count):
    if not page_ranges: return [[page_index] for page_index in range(page_count)]

    ranges = []

    for part in page_ranges.split(","):
        part = part.strip()

        if not part: continue

        if "-" in part:
            start, end = [
                parse_page_number(value, page_count)
                for value in part.split("-", 1)
            ]

            if start > end: start, end = end, start

            ranges.append(list(range(start, end + 1)))

        else: ranges.append([parse_page_number(part, page_count)])

    return ranges or [[page_index] for page_index in range(page_count)]


def parse_page_number(value, page_count):
    page_number = int(value.strip())

    if page_number < 1 or page_number > page_count: raise ValueError(f"Pagina fora do intervalo permitido: {page_number}")

    return page_number - 1
