import fitz

def convert_pdf_compress(input_path, output_path, options=None):
    with fitz.open(input_path) as document:
        document.save(
             output_path
            ,garbage=4
            ,deflate=True
        )
