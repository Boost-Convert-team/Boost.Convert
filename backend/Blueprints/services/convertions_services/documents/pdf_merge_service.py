import os
import fitz

def convert_pdf_merge(input_path, output_path):
    merged_pdf = fitz.open()

    try:
        for filename in sorted(os.listdir(input_path)):
            path = os.path.join(input_path, filename)

            if os.path.isfile(path) and path.lower().endswith(".pdf"):
                with fitz.open(path) as source_pdf:
                    merged_pdf.insert_pdf(source_pdf)

        if merged_pdf.page_count == 0: raise ValueError("Envie pelo menos dois PDFs para juntar.")

        merged_pdf.save(output_path, garbage=4, deflate=True)

    finally: merged_pdf.close()
