import os
import re
import tempfile
import uuid
from pathlib import Path
import requests
from flask import Blueprint, current_app, render_template, request
from pytubefix import YouTube
from werkzeug.utils import secure_filename

from Blueprints.services.convertions_services.file_security import (
    remove_file_quietly,
    validate_saved_file,
    validate_upload_header,
    validate_upload_mime,
)
from Blueprints.services.convertions_services.conversion_errors import get_user_friendly_conversion_error
from Blueprints.services.privacy.download_stream import stream_private_download

ai_tools_bp = Blueprint("ai_tools", __name__)

OPENAI_AUDIO_TRANSCRIPTION_URL = "https://api.openai.com/v1/audio/transcriptions"
OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"


@ai_tools_bp.route("/tools/ai/youtube-analyzer", methods=["GET", "POST"])
def youtube_analyzer():
    if request.method == "GET":
        return render_template("youtube_analyzer.html")

    url = (request.form.get("url") or "").strip()
    if not url:
        return render_template("youtube_analyzer.html", url=url, error="Envie uma URL do YouTube.")

    try:
        result = analyze_youtube_video(url)
        return render_template("youtube_analyzer.html", url=url, result=result)
    except Exception as exc:
        return render_template("youtube_analyzer.html", url=url, error=get_user_friendly_conversion_error(exc))


@ai_tools_bp.route("/tools/ai/mp4-to-text", methods=["GET", "POST"])
def mp4_to_text():
    if request.method == "GET":
        return render_template("mp4_to_text.html")

    uploaded_file = request.files.get("file")
    if uploaded_file is None or not uploaded_file.filename:
        return render_template("mp4_to_text.html", error="Envie um arquivo MP4.")

    try:
        validate_uploaded_mp4(uploaded_file)
        result = transcribe_uploaded_mp4(uploaded_file)
        return render_template("mp4_to_text.html", result=result)
    except Exception as exc:
        return render_template("mp4_to_text.html", error=get_user_friendly_conversion_error(exc))

@ai_tools_bp.route("/tools/ai/mp4-to-text/download/<filename>")
def mp4_to_text_download(filename):
    safe_filename = secure_filename(filename)
    transcript_path = get_transcript_dir() / safe_filename

    if safe_filename != filename or not transcript_path.exists():
        return "Arquivo nao encontrado.", 404

    return stream_private_download(
        transcript_path,
        safe_filename,
        lambda: remove_file_quietly(transcript_path),
    )

def analyze_youtube_video(url):
    yt = YouTube(url)
    transcript = get_youtube_caption_text(yt)

    if not transcript:
        transcript = transcribe_youtube_audio(yt)

    summary = summarize_text(transcript, yt.title)
    return {"title": yt.title, "summary": summary}

def get_youtube_caption_text(yt):
    caption = find_caption(yt)
    if caption is None:
        return ""

    raw_caption = caption_to_text(caption)
    return clean_caption_text(raw_caption)

def find_caption(yt):
    preferred_languages = ("pt-BR", "pt", "a.pt", "en", "a.en")

    for language in preferred_languages:
        caption = yt.captions.get_by_language_code(language)
        if caption is not None:
            return caption

    captions = list(yt.captions)
    return captions[0] if captions else None

def caption_to_text(caption):
    if hasattr(caption, "generate_srt_captions"):
        return caption.generate_srt_captions()
    if hasattr(caption, "xml_captions"):
        return caption.xml_captions
    return str(caption)


def clean_caption_text(text):
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\d+\s*\n", "\n", text)
    text = re.sub(r"\d{2}:\d{2}:\d{2}[^\n]*", "\n", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def transcribe_youtube_audio(yt):
    with tempfile.TemporaryDirectory(prefix="boost_youtube_audio_") as temp_dir:
        audio = yt.streams.get_audio_only()
        if audio is None:
            raise RuntimeError("Nao encontrei audio disponivel para este video.")

        audio_path = audio.download(output_path=temp_dir, filename="audio.mp4")
        return transcribe_file_with_openai(audio_path)

def transcribe_uploaded_mp4(uploaded_file):
    with tempfile.TemporaryDirectory(prefix="boost_mp4_text_") as temp_dir:
        original_filename = secure_filename(uploaded_file.filename)
        input_path = Path(temp_dir) / f"input_{uuid.uuid4().hex}.mp4"
        uploaded_file.save(input_path)

        saved_valid, saved_message = validate_saved_file(input_path, "mp4")
        if not saved_valid:
            raise RuntimeError(saved_message)

        text = transcribe_file_with_openai(input_path)
        if not text.strip():
            raise RuntimeError("A transcricao voltou vazia.")

        txt_filename = save_transcript_file(original_filename, text)
        return {"filename": original_filename, "txt_filename": txt_filename, "text": text}

def validate_uploaded_mp4(uploaded_file):
    if not uploaded_file.filename.lower().endswith(".mp4"):
        raise ValueError("Formato invalido. Envie um arquivo .mp4.")

    mime_valid, mime_message = validate_upload_mime(uploaded_file, "mp4")
    if not mime_valid:
        raise ValueError(mime_message)

    header_valid, header_message = validate_upload_header(uploaded_file, "mp4")
    if not header_valid:
        raise ValueError(header_message)

def transcribe_file_with_openai(file_path):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Configure OPENAI_API_KEY para usar esta ferramenta.")

    with open(file_path, "rb") as file:
        response = requests.post(
            OPENAI_AUDIO_TRANSCRIPTION_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            data={"model": os.getenv("OPENAI_TRANSCRIPTION_MODEL", "whisper-1")},
            files={"file": file},
            timeout=180,
        )

    if response.status_code >= 400:
        raise RuntimeError("Erro na transcricao.")

    if response.headers.get("content-type", "").startswith("application/json"):
        return response.json().get("text", "").strip()

    return response.text.strip()

def summarize_text(text, title):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return build_local_summary(text)

    response = requests.post(
        OPENAI_CHAT_COMPLETIONS_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": os.getenv("OPENAI_SUMMARY_MODEL", "gpt-4o-mini"),
            "messages": [
                {
                    "role": "system",
                    "content": "Resuma videos em portugues do Brasil com linguagem simples, objetiva e organizada.",
                },
                {
                    "role": "user",
                    "content": (
                        f"Titulo: {title}\n\n"
                        "Crie um resumo com: resumo geral, topicos principais, pontos importantes e conclusao pratica.\n\n"
                        f"Transcricao:\n{text[:24000]}"
                    ),
                },
            ],
            "temperature": 0.3,
        },
        timeout=120,
    )

    if response.status_code >= 400:
        raise RuntimeError("Erro na IA.")

    choices = response.json().get("choices", [])
    if not choices:
        raise RuntimeError("A IA nao retornou resumo.")

    return choices[0]["message"]["content"].strip()

def build_local_summary(text):
    sentences = split_sentences(text)
    if not sentences:
        raise RuntimeError("Nao encontrei texto suficiente para resumir.")

    selected = sentences[:8]
    return "\n".join(
        [
            "Resumo automatico baseado na transcricao disponivel.",
            "",
            "Topicos principais:",
            *[f"- {sentence}" for sentence in selected],
        ]
    )

def split_sentences(text):
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [sentence.strip() for sentence in sentences if len(sentence.strip()) > 30]

def save_transcript_file(original_filename, text):
    transcript_dir = get_transcript_dir()
    transcript_dir.mkdir(parents=True, exist_ok=True)

    txt_filename = secure_filename(f"transcricao_{uuid.uuid4().hex}.txt")
    transcript_path = transcript_dir / txt_filename
    transcript_path.write_text(text, encoding="utf-8")
    return txt_filename

def get_transcript_dir():
    return Path(current_app.instance_path) / "ai_tools" / "transcripts"
