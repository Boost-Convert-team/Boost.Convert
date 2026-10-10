from html import escape

import pymupdf

# PyMuPDF writes each page as <div style="width;height"> and each line as
# <p style="top;left">, leaving the positioning to the stylesheet. Without it
# the browser ignores top/left and every line falls back into normal flow.
DOCUMENT_TEMPLATE = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body {{ margin: 0; padding: 24px 0; background: #ececef; }}
  body > div {{ position: relative; margin: 0 auto 24px; overflow: hidden; background: #fff; box-shadow: 0 1px 4px rgba(0, 0, 0, .18); }}
  body > div p {{ position: absolute; margin: 0; white-space: pre; }}
</style>
</head>
<body>
{pages}
</body>
</html>
"""


def convert_pdf_html(input_path, output_path):
    with pymupdf.open(input_path) as document:
        title = (document.metadata or {}).get("title") or "Documento convertido"
        pages = "\n".join(page.get_text("html") for page in document)
    with open(output_path, "w", encoding="utf-8") as file:
        file.write(DOCUMENT_TEMPLATE.format(title=escape(title), pages=pages))
