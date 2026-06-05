import fitz

PDF_ENCRYPT_NONE = getattr(fitz, "PDF_ENCRYPT_NONE")

def convert_pdf_unlock(input_path, output_path, options=None):
    password = (options or {}).get("pdf_password", "").strip()

    with fitz.open(input_path) as document:
        if document.needs_pass:
            if not password: raise ValueError("Informe a senha do PDF.")
            if not document.authenticate(password): raise ValueError("Senha do PDF invalida.")

        document.save(
             output_path
            ,garbage=4
            ,deflate=True
            ,encryption=PDF_ENCRYPT_NONE
        )
