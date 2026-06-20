import base64
import os
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path
from flask import Blueprint, render_template, request
from flask.typing import ResponseReturnValue
from pytubefix import YouTube
from requests import Response

from Blueprints.services.convertions_services.conversion_errors import get_user_friendly_conversion_error
from Blueprints.services.ai.openrouter_client import (
    call_openrouter_chat_completion,
    get_openrouter_api_key,
    post_openrouter_json,
)
from Blueprints.services.ai.document_analyzer import (
    DOCUMENT_ANALYZER_ACTIONS,
    DocumentAnalysisResult,
    analyze_uploaded_document,
    get_document_accept_attribute,
)

ai_tools_bp = Blueprint("ai_tools", __name__)

OPENROUTER_AUDIO_TRANSCRIPTION_URL = "https://openrouter.ai/api/v1/audio/transcriptions"
DEFAULT_OPENROUTER_TRANSCRIPTION_MODEL = "qwen/qwen3-asr-flash-2026-02-10"


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


@ai_tools_bp.route("/tools/ai/document-analyzer", methods=["GET", "POST"])
def document_analyzer() -> ResponseReturnValue:
    if request.method == "GET":
        return render_document_analyzer_template()

    uploaded_file = request.files.get("file")
    action = (request.form.get("analysis_type") or "summary").strip()
    question = (request.form.get("question") or "").strip()
    if uploaded_file is None or not uploaded_file.filename:
        return render_document_analyzer_template(error="Envie um documento para analisar.")

    try:
        result = analyze_uploaded_document(uploaded_file, action, question)
        return render_document_analyzer_template(result=result, selected_action=action, question=question)
    except Exception as exc:
        error = get_user_friendly_conversion_error(exc)
        return render_document_analyzer_template(error=error, selected_action=action, question=question)


def render_document_analyzer_template(
    error: str = "",
    result: DocumentAnalysisResult | None = None,
    selected_action: str = "summary",
    question: str = "",
) -> str:
    return render_template(
        "document_analyzer.html",
        actions=DOCUMENT_ANALYZER_ACTIONS,
        accept_attribute=get_document_accept_attribute(),
        error=error,
        result=result,
        selected_action=selected_action,
        question=question,
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
        return transcribe_file_with_openrouter(audio_path, "youtube_analyzer")

def transcribe_file_with_openrouter(file_path: str | Path, tool_name: str) -> str:
    api_key = get_openrouter_api_key()
    model = get_openrouter_transcription_model()
    response = post_openrouter_json(
        api_key,
        OPENROUTER_AUDIO_TRANSCRIPTION_URL,
        build_openrouter_transcription_payload(file_path, model),
        tool_name,
        model,
        False,
        180,
    )

    if response.status_code == 401:
        raise RuntimeError("Erro na transcricao: OPENROUTER_API_KEY invalida ou expirada.")
    if response.status_code == 402:
        raise RuntimeError(build_openrouter_transcription_payment_error(response))
    if response.status_code >= 400:
        raise RuntimeError(build_openrouter_transcription_status_error(response))

    if response.headers.get("content-type", "").startswith("application/json"):
        return response.json().get("text", "").strip()

    return response.text.strip()

def get_openrouter_transcription_model() -> str:
    """Read the STT model slug, falling back to a current OpenRouter model.

    Example: get_openrouter_transcription_model()
    """
    configured_model = os.getenv("OPENROUTER_TRANSCRIPTION_MODEL", "").strip()
    return configured_model or DEFAULT_OPENROUTER_TRANSCRIPTION_MODEL

def build_openrouter_transcription_payment_error(response: Response) -> str:
    """Create a user-safe message for OpenRouter audio billing failures.

    Example: build_openrouter_transcription_payment_error(response)
    """
    return (
        "Erro na transcricao: saldo insuficiente na OpenRouter para audio. "
        f"Status {response.status_code}; esperado pelo menos US$0.50 de saldo."
    )

def build_openrouter_transcription_status_error(response: Response) -> str:
    """Create a user-safe status message for transcription failures.

    Example: build_openrouter_transcription_status_error(response)
    """
    detail = extract_openrouter_error_message(response)
    if detail:
        return f"Erro na transcricao: status {response.status_code} no OpenRouter. Detalhe: {detail}"
    return f"Erro na transcricao: status {response.status_code} no OpenRouter."

def extract_openrouter_error_message(response: Response) -> str:
    """Extract a safe OpenRouter error message from a JSON response.

    Example: extract_openrouter_error_message(response)
    """
    try:
        payload = response.json()
    except ValueError:
        return ""
    error = payload.get("error") if isinstance(payload, Mapping) else None
    if not isinstance(error, Mapping):
        return ""
    message = error.get("message")
    return message.strip()[:160] if isinstance(message, str) else ""

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
    return call_openrouter_chat_completion(
        build_summary_prompt(text, title),
        "youtube_analyzer",
    )

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

