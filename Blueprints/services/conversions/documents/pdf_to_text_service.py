import fitz

def convert_pdf_txt(input_path, output_path):
    doc = fitz.open(input_path)
    try:
        text_parts = []

        for page in doc:
            page_text = page.get_text("text", sort=True)
            text_parts.append(f"\n\n--- Página {page.number + 1} ---\n\n")
            text_parts.append(page_text)
        
        full_text = "".join(text_parts)

        with open(output_path, "w", encoding="utf-8") as file:
            file.write(full_text)

    finally: doc.close()
