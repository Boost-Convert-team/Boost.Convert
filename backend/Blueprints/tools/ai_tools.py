import base64
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

OPENROUTER_AUDIO_TRANSCRIPTION_URL = "https://openrouter.ai/api/v1/audio/transcriptions"
OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"


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
        return transcribe_file_with_openrouter(audio_path)

def transcribe_uploaded_mp4(uploaded_file):
    with tempfile.TemporaryDirectory(prefix="boost_mp4_text_") as temp_dir:
        original_filename = secure_filename(uploaded_file.filename)
        input_path = Path(temp_dir) / f"input_{uuid.uuid4().hex}.mp4"
        uploaded_file.save(input_path)

        saved_valid, saved_message = validate_saved_file(input_path, "mp4")
        if not saved_valid:
            raise RuntimeError(saved_message)

        text = transcribe_file_with_openrouter(input_path)
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

def transcribe_file_with_openrouter(file_path: str | Path) -> str:
    api_key = get_required_openrouter_env("OPENROUTER_API_KEY")
    model = get_required_openrouter_env("OPENROUTER_TRANSCRIPTION_MODEL")
    response = requests.post(
        OPENROUTER_AUDIO_TRANSCRIPTION_URL,
        headers=build_openrouter_headers(api_key),
        json=build_openrouter_transcription_payload(file_path, model),
        timeout=180,
    )

    if response.status_code >= 400:
        raise RuntimeError(f"Erro na transcricao: status {response.status_code} no OpenRouter.")

    if response.headers.get("content-type", "").startswith("application/json"):
        return response.json().get("text", "").strip()

    return response.text.strip()

def get_required_openrouter_env(name: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    raise RuntimeError(f"Configure {name} para usar esta ferramenta.")

def build_openrouter_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

def build_openrouter_transcription_payload(file_path: str | Path, model: str) -> dict[str, object]:
    audio_path = Path(file_path)
    return {
        "model": model,
        "input_audio": {
            "data": base64.b64encode(audio_path.read_bytes()).decode("ascii"),
            "format": get_audio_format(audio_path),
        },
    }

def get_audio_format(audio_path: Path) -> str:
    suffix = audio_path.suffix.lower().lstrip(".")
    if suffix:
        return suffix
    raise RuntimeError("Formato de audio ausente. Esperado arquivo com extensao mp4, mp3 ou wav.")

def summarize_text(text: str, title: str) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("OPENROUTER_SUMMARY_MODEL")
    if not api_key or not model:
        return build_local_summary(text)

    response = requests.post(
        OPENROUTER_CHAT_COMPLETIONS_URL,
        headers=build_openrouter_headers(api_key),
        json=build_openrouter_summary_payload(text, title, model),
        timeout=120,
    )

    if response.status_code >= 400:
        raise RuntimeError(f"Erro na IA: status {response.status_code} no OpenRouter.")

    choices = response.json().get("choices", [])
    if not choices:
        raise RuntimeError("A IA nao retornou resumo.")

    return choices[0]["message"]["content"].strip()

def build_openrouter_summary_payload(text: str, title: str, model: str) -> dict[str, object]:
    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "Resuma videos em portugues do Brasil com linguagem simples, objetiva e organizada.",
            },
            {
                "role": "user",
                "content": build_summary_prompt(text, title),
            },
        ],
        "temperature": 0.3,
    }

def build_summary_prompt(text: str, title: str) -> str:
    return (
        f"Titulo: {title}\n\n"
        "Crie um resumo com: resumo geral, topicos principais, pontos importantes e conclusao pratica.\n\n"
        f"Transcricao:\n{text[:24000]}"
    )

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
