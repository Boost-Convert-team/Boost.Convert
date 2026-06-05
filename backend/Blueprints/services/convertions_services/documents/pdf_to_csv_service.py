import csv
import fitz

def convert_pdf_csv(input_path, output_path):
    with fitz.open(input_path) as document:
        rows = [
            [page.number + 1, page.get_text("text", sort=True)]
            for page in document
        ]

    with open(output_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["pagina", "texto"])
        writer.writerows(rows)
