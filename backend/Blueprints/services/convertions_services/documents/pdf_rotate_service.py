import fitz

def convert_pdf_rotate(input_path, output_path, options=None):
    options = options or {}
    angle = int(options.get("rotation_angle", "90"))

    if angle not in {90, 180, 270}:
        raise ValueError("Rotacao invalida.")

    with fitz.open(input_path) as document:
        pages = sorted(
            {
                page_index
                for page_group in parse_page_ranges(options.get("page_ranges"), document.page_count)
                for page_index in page_group
            }
        )

        for page_index in pages:
            page = document[page_index]
            page.set_rotation((page.rotation + angle) % 360)

        document.save(output_path, garbage=4, deflate=True)


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

        else:
            ranges.append([parse_page_number(part, page_count)])

    return ranges or [[page_index] for page_index in range(page_count)]


def parse_page_number(value, page_count):
    page_number = int(value.strip())
    if page_number < 1 or page_number > page_count: raise ValueError(f"Pagina fora do intervalo permitido: {page_number}")
    
    return page_number - 1
