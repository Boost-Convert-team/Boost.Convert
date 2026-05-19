import fitz
import os

def convert_pdf_merge(input_path, output_path, options=None):
    pdf_paths = [
        os.path.join(input_path, filename)
        for filename in sorted(os.listdir(input_path))
        if filename.lower().endswith(".pdf")
    ]

    if len(pdf_paths) < 2:
        raise ValueError("Envie pelo menos dois PDFs para juntar.")

    output = fitz.open()

    try:
        for pdf_path in pdf_paths:
            with fitz.open(pdf_path) as source:
                output.insert_pdf(source)

        output.save(output_path, garbage=4, deflate=True)
    finally:
        output.close()
