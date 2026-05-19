import fitz
import os
import tempfile
import zipfile

def convert_pdf_split(input_path, output_path, options=None):
    options = options or {}

    with fitz.open(input_path) as source:
        ranges = parse_page_ranges(options.get("page_ranges"), source.page_count)

        with tempfile.TemporaryDirectory() as temp_dir:
            split_paths = []

            for index, page_indexes in enumerate(ranges, start=1):
                split_doc = fitz.open()

                try:
                    for page_index in page_indexes:
                        split_doc.insert_pdf(source, from_page=page_index, to_page=page_index)

                    page_label = build_page_label(page_indexes)
                    split_path = os.path.join(temp_dir, f"pdf_{index}_{page_label}.pdf")
                    split_doc.save(split_path, garbage=4, deflate=True)
                    split_paths.append(split_path)
                finally:
                    split_doc.close()

            with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
                for split_path in split_paths:
                    zip_file.write(split_path, os.path.basename(split_path))

def parse_page_ranges(page_ranges, page_count):
    if not page_ranges:
        return [[page_index] for page_index in range(page_count)]

    ranges = []

    for part in page_ranges.split(","):
        part = part.strip()

        if not part:
            continue

        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start = parse_page_number(start_text, page_count)
            end = parse_page_number(end_text, page_count)

            if start > end:
                start, end = end, start

            ranges.append(list(range(start, end + 1)))
        else:
            page = parse_page_number(part, page_count)
            ranges.append([page])

    if not ranges:
        return [[page_index] for page_index in range(page_count)]

    return ranges

def parse_page_number(value, page_count):
    page_number = int(value.strip())

    if page_number < 1 or page_number > page_count:
        raise ValueError(f"Pagina fora do intervalo permitido: {page_number}")

    return page_number - 1

def build_page_label(page_indexes):
    first_page = page_indexes[0] + 1
    last_page = page_indexes[-1] + 1

    if first_page == last_page:
        return f"pagina_{first_page}"

    return f"paginas_{first_page}_a_{last_page}"
