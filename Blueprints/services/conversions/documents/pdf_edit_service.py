import fitz

def convert_pdf_edit(input_path, output_path, options=None):
    options = options or {}
    edit_text = options.get("edit_text", "").strip()

    if not edit_text:
        raise ValueError("Informe um texto para adicionar ao PDF.")

    page_number = int(options.get("edit_page", "1"))
    x_position = int(options.get("x_position", "72"))
    y_position = int(options.get("y_position", "72"))
    font_size = int(options.get("font_size", "14"))

    with fitz.open(input_path) as document:
        if page_number < 1 or page_number > document.page_count:
            raise ValueError("Pagina informada nao existe no PDF.")

        page = document[page_number - 1]
        page.insert_text(
            (x_position, y_position),
            edit_text,
            fontsize=font_size,
            color=(0, 0, 0),
        )

        document.save(output_path, garbage=4, deflate=True)
