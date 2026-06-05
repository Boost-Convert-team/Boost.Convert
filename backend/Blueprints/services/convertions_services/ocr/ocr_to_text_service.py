import base64
import os
import tempfile

import fitz
import requests
from PIL import Image

OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"

def convert_pdf_ocr_txt(input_path, output_path):
    with fitz.open(input_path) as document: text = "".join(str(document[page_index].get_text("text", sort=True)) for page_index in range(document.page_count))

    with open(output_path, "w", encoding="utf-8") as file: file.write(text)

def convert_image_ocr_txt(input_path, output_path):
    text = extract_text_from_image(input_path)
    if not text.strip(): raise RuntimeError("OCR nao encontrou texto.")

    with open(output_path, "w", encoding="utf-8") as file: file.write(text)

def extract_text_from_image(input_path):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Configure OPENAI_API_KEY para usar OCR.")

    image_data_url = build_image_data_url(input_path)
    response = requests.post(
        OPENAI_CHAT_COMPLETIONS_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": os.getenv("OPENAI_OCR_MODEL", "gpt-4o-mini"),
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extraia somente o texto visivel da imagem. Se nao houver texto, responda vazio.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": image_data_url},
                        },
                    ],
                },
            ],
            "temperature": 0,
        },
        timeout=120,
    )

    if response.status_code >= 400:
        raise RuntimeError("Erro no OCR.")

    choices = response.json().get("choices", [])
    if not choices:
        raise RuntimeError("OCR nao encontrou texto.")

    return choices[0]["message"]["content"].strip()

def build_image_data_url(input_path):
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
        temp_path = temp_file.name

    try:
        with Image.open(input_path) as image:
            image.convert("RGB").save(temp_path, "PNG")

        with open(temp_path, "rb") as file:
            encoded_image = base64.b64encode(file.read()).decode("ascii")

        return f"data:image/png;base64,{encoded_image}"
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass
