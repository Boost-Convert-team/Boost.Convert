import json
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path

import requests
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from Blueprints.services.ai.document_text_extractor import (
    ALLOWED_DOCUMENT_ANALYZER_EXTENSIONS,
    extract_document_text,
    validate_document_extension,
)
from Blueprints.services.ai.openrouter_client import (
    OpenRouterChatSettings,
    OpenRouterPost,
    call_openrouter_chat_completion_with_settings,
)
from Blueprints.services.convertions_services.file_security import (
    validate_saved_file,
    validate_upload_header,
    validate_upload_mime,
)


DOCUMENT_ANALYZER_TOOL_NAME = "document_analyzer_ai"
DOCUMENT_ANALYZER_SYSTEM_PROMPT = (
    "Você é uma IA objetiva e precisa para análise de documentos. "
    "Responda apenas com base no conteúdo fornecido. "
    "Se o documento não tiver informação suficiente, diga isso claramente. "
    "Não invente dados."
)
DOCUMENT_ANALYZER_CHAT_SETTINGS = OpenRouterChatSettings(
    DOCUMENT_ANALYZER_SYSTEM_PROMPT,
    0.2,
    1600,
    120,
)
DOCUMENT_ANALYZER_CHUNK_CHARS = 12000
DOCUMENT_ANALYZER_DIRECT_CHARS = 16000
DOCUMENT_ANALYZER_ACTIONS = {
    "summary": "Resumo inteligente",
    "simple": "Linguagem simples",
    "key_points": "Pontos principais",
    "flashcards": "Flashcards",
    "quiz": "Quiz",
    "question": "Pergunte ao documento",
    "data_extraction": "Extração de dados importantes",
}
DOCUMENT_ANALYZER_PROMPTS = {
    "summary": "Gere um resumo claro e organizado do documento, destacando objetivo, pontos principais, conclusões e informações relevantes.",
    "simple": "Explique o conteúdo do documento em linguagem simples, como se fosse para uma pessoa leiga.",
    "key_points": "Liste os principais pontos do documento em tópicos objetivos.",
    "flashcards": "Crie flashcards de estudo com pergunta e resposta com base no documento.",
    "quiz": "Crie questões objetivas com alternativas, gabarito e justificativa com base no documento.",
    "question": "Responda à pergunta do usuário usando apenas o conteúdo do documento. Se não houver base no documento, diga que o documento não informa isso.",
    "data_extraction": "Extraia informações importantes do documento, como nomes, datas, valores, prazos, obrigações, riscos e conclusões.",
}

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DocumentAnalysisResult:
    filename: str
    action_label: str
    answer: str


def analyze_uploaded_document(
    uploaded_file: FileStorage,
    action: str,
    question: str,
    request_post: OpenRouterPost = requests.post,
) -> DocumentAnalysisResult:
    """Analyze one uploaded document without persisting its content.

    Example: analyze_uploaded_document(file, "summary", "")
    """
    extension = get_uploaded_document_extension(uploaded_file)
    validate_uploaded_document(uploaded_file, extension)
    log_document_analyzer_call(extension)
    with tempfile.TemporaryDirectory(prefix="boost_document_analyzer_") as temp_dir:
        input_path = save_document_upload(uploaded_file, Path(temp_dir), extension)
        validate_saved_document(input_path, extension)
        text = extract_document_text(input_path, extension)
        answer = analyze_document_text(text, action, question, request_post)
    display_name = secure_filename(uploaded_file.filename or "documento") or "documento"
    return DocumentAnalysisResult(display_name, get_action_label(action), answer)


def get_uploaded_document_extension(uploaded_file: FileStorage) -> str:
    """Read and validate the uploaded document extension.

    Example: get_uploaded_document_extension(file)
    """
    filename = uploaded_file.filename or ""
    extension = Path(filename).suffix.lower().lstrip(".")
    validate_document_extension(extension)
    return extension


def validate_uploaded_document(uploaded_file: FileStorage, extension: str) -> None:
    """Validate MIME and header before saving the upload.

    Example: validate_uploaded_document(file, "pdf")
    """
    mime_valid, mime_message = validate_upload_mime(uploaded_file, extension)
    if not mime_valid:
        raise ValueError(mime_message or "Arquivo invalido.")
    header_valid, header_message = validate_upload_header(uploaded_file, extension)
    if not header_valid:
        raise ValueError(header_message or "Arquivo invalido.")


def save_document_upload(uploaded_file: FileStorage, temp_dir: Path, extension: str) -> Path:
    """Save the uploaded file in a temporary directory.

    Example: save_document_upload(file, Path("tmp"), "pdf")
    """
    safe_stem = Path(secure_filename(uploaded_file.filename or "documento")).stem
    input_path = temp_dir / f"{safe_stem or 'documento'}.{extension}"
    uploaded_file.save(input_path)
    return input_path


def validate_saved_document(file_path: Path, extension: str) -> None:
    """Validate saved Office containers before text extraction.

    Example: validate_saved_document(Path("texto.docx"), "docx")
    """
    if extension not in {"docx", "odt"}:
        return
    valid, message = validate_saved_file(file_path, extension)
    if not valid:
        raise ValueError(message or "Arquivo invalido.")


def analyze_document_text(
    text: str,
    action: str,
    question: str,
    request_post: OpenRouterPost = requests.post,
) -> str:
    """Generate an AI answer for the selected document action.

    Example: analyze_document_text("Contrato...", "summary", "")
    """
    validate_document_action(action, question)
    if len(text) <= DOCUMENT_ANALYZER_DIRECT_CHARS:
        return request_document_analysis(build_document_prompt(action, text, question), request_post)
    summaries = summarize_document_chunks(split_document_chunks(text), request_post)
    consolidated_text = "\n\n".join(summaries)
    return request_document_analysis(build_document_prompt(action, consolidated_text, question), request_post)


def validate_document_action(action: str, question: str) -> None:
    """Validate the selected analyzer action and its required fields.

    Example: validate_document_action("question", "Qual e o prazo?")
    """
    if action not in DOCUMENT_ANALYZER_ACTIONS:
        raise ValueError(f"Acao invalida: {action!r}; esperado uma acao do Document Analyzer AI.")
    if action == "question" and not question.strip():
        raise ValueError("Informe uma pergunta para usar Pergunte ao documento.")


def build_document_prompt(action: str, document_text: str, question: str) -> str:
    """Build the user prompt for one analyzer action.

    Example: build_document_prompt("summary", "Texto", "")
    """
    prompt = DOCUMENT_ANALYZER_PROMPTS[action]
    if action == "question":
        prompt = f"{prompt}\n\nPergunta do usuario: {question.strip()}"
    return f"{prompt}\n\nConteudo do documento:\n{document_text}"


def split_document_chunks(text: str) -> list[str]:
    """Split large extracted text into OpenRouter-sized parts.

    Example: split_document_chunks("texto longo")
    """
    return [
        text[index : index + DOCUMENT_ANALYZER_CHUNK_CHARS]
        for index in range(0, len(text), DOCUMENT_ANALYZER_CHUNK_CHARS)
    ]


def summarize_document_chunks(
    chunks: list[str],
    request_post: OpenRouterPost = requests.post,
) -> list[str]:
    """Summarize document chunks before the final consolidated answer.

    Example: summarize_document_chunks(["parte 1"])
    """
    return [
        request_document_analysis(build_chunk_summary_prompt(chunk, index), request_post)
        for index, chunk in enumerate(chunks, start=1)
    ]


def build_chunk_summary_prompt(chunk: str, index: int) -> str:
    """Build a summarization prompt for one document chunk.

    Example: build_chunk_summary_prompt("Texto", 1)
    """
    return (
        f"Resuma a parte {index} do documento preservando fatos, nomes, datas, "
        f"valores, obrigações, riscos e conclusões.\n\nParte {index}:\n{chunk}"
    )


def request_document_analysis(
    prompt: str,
    request_post: OpenRouterPost = requests.post,
) -> str:
    """Send one Document Analyzer prompt to OpenRouter.

    Example: request_document_analysis("Resuma o documento")
    """
    return call_openrouter_chat_completion_with_settings(
        prompt,
        DOCUMENT_ANALYZER_TOOL_NAME,
        DOCUMENT_ANALYZER_CHAT_SETTINGS,
        request_post,
    )


def get_action_label(action: str) -> str:
    """Return the user-facing label for an analyzer action.

    Example: get_action_label("summary")
    """
    return DOCUMENT_ANALYZER_ACTIONS.get(action, DOCUMENT_ANALYZER_ACTIONS["summary"])


def get_document_accept_attribute() -> str:
    """Return the upload accept attribute for the analyzer template.

    Example: get_document_accept_attribute()
    """
    extensions = sorted(ALLOWED_DOCUMENT_ANALYZER_EXTENSIONS)
    return ",".join(f".{extension}" for extension in extensions)


def log_document_analyzer_call(extension: str) -> None:
    """Log only safe metadata for the uploaded document type.

    Example: log_document_analyzer_call("pdf")
    """
    logger.info(
        json.dumps(
            {"ferramenta": DOCUMENT_ANALYZER_TOOL_NAME, "tipo_arquivo": extension},
            ensure_ascii=False,
        )
    )
