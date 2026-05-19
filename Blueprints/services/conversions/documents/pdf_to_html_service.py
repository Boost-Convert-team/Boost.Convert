import fitz

def convert_pdf_html(input_path, output_path):
    doc = fitz.open(input_path)

    try:
        html_parts = [
             "<!DOCTYPE html>"
            ,"<html lang='pt-BR'>"
            ,"<head>"
            ,"<meta charset='UTF-8'>"
            ,"<title>PDF convertido</title>"
            ,"</head>"
            ,"<body>"
        ]

        for page in doc:
            html_parts.append(f"<section class='page' data-page='{page.number + 1}'>")
            html_parts.append(page.get_text("html"))
            html_parts.append("</section>")

        html_parts.extend([
             "</body>"
            ,"</html>"
        ])

        full_html = "\n".join(html_parts)

        with open(output_path, "w", encoding="utf-8") as file:
            file.write(full_html)

    finally: doc.close()