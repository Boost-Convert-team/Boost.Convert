from pdf2docx import Converter

def convert_pdf_docx(input_path, output_path):
    try:
        converter = Converter(input_path)
        try:
            converter.convert(output_path)
        finally: converter.close()

    except Exception as exc:
        raise RuntimeError(
            f"Nao foi possivel preservar o layout do PDF em DOCX: {input_path}; esperado PDF compativel com pdf2docx."
        ) from exc
