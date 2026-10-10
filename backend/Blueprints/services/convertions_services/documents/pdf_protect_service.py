import pymupdf

def convert_pdf_protect(input_path, output_path, options=None):
    password = (options or {}).get("pdf_password", "").strip()

    if not password: raise ValueError("Informe uma senha para proteger o PDF.")

    with pymupdf.open(input_path) as document:
        document.save(
             output_path
            ,garbage=4
            ,deflate=True
            ,encryption=pymupdf.PDF_ENCRYPT_AES_256
            ,owner_pw=password
            ,user_pw=password
        )
