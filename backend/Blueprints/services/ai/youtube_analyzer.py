import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import ParseResult, parse_qs, urlparse

import requests
from youtube_transcript_api import (
    CouldNotRetrieveTranscript,
    InvalidVideoId,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    VideoUnplayable,
    YouTubeTranscriptApi,
)

from Blueprints.services.ai.openrouter_client import (
    OpenRouterPost,
    call_openrouter_chat_completion,
)


YOUTUBE_ANALYZER_TOOL_NAME = "youtube_analyzer"
YOUTUBE_TRANSCRIPT_MAX_CHARS = 24000
PREFERRED_TRANSCRIPT_LANGUAGES = ("pt", "pt-BR", "en")
YOUTUBE_VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}
NO_PUBLIC_TRANSCRIPT_MESSAGE = (
    "Este v\u00eddeo n\u00e3o possui legenda p\u00fablica dispon\u00edvel para an\u00e1lise gratuita."
)
TRANSCRIPT_UNAVAILABLE_MESSAGE = (
    "A transcri\u00e7\u00e3o p\u00fablica est\u00e1 indispon\u00edvel no momento. Tente novamente mais tarde."
)


class TranscriptReference(Protocol):
    def fetch(self, preserve_formatting: bool = False) -> Iterable[object]:
        """Fetch one transcript reference.

        Example: transcript.fetch()
        """
        ...


class TranscriptApi(Protocol):
    def fetch(
        self,
        video_id: str,
        languages: Iterable[str] = PREFERRED_TRANSCRIPT_LANGUAGES,
        preserve_formatting: bool = False,
    ) -> Iterable[object]:
        """Fetch a transcript for the requested language order.

        Example: transcript_api.fetch(video_id, languages=("pt", "en"))
        """
        ...

    def list(self, video_id: str) -> Iterable[TranscriptReference]:
        """List every public transcript reference for a video.

        Example: transcript_api.list(video_id)
        """
        ...


@dataclass(frozen=True)
class YoutubeAnalysisResult:
    title: str
    summary: str


def analyze_youtube_video(
    url: str,
    transcript_api: TranscriptApi | None = None,
    request_post: OpenRouterPost = requests.post,
) -> YoutubeAnalysisResult:
    """Analyze a YouTube URL using public captions only.

    Example: analyze_youtube_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    """
    video_id = extract_youtube_video_id(url)
    transcript = fetch_youtube_transcript_text(video_id, transcript_api or YouTubeTranscriptApi())
    summary = summarize_youtube_transcript(transcript, request_post)
    return YoutubeAnalysisResult(f"Video do YouTube: {video_id}", summary)


def extract_youtube_video_id(url: str) -> str:
    """Extract the video id from a regular YouTube or Shorts URL.

    Example: extract_youtube_video_id("https://youtube.com/shorts/dQw4w9WgXcQ")
    """
    parsed_url = parse_youtube_url(url)
    host = (parsed_url.hostname or "").lower()
    if host == "youtu.be":
        return validate_youtube_video_id(first_path_part(parsed_url.path))
    if host in YOUTUBE_HOSTS:
        return extract_video_id_from_youtube_url(parsed_url.path, parsed_url.query)
    raise ValueError(build_invalid_youtube_url_message(url))


def parse_youtube_url(url: str) -> ParseResult:
    """Parse URLs with or without an explicit scheme.

    Example: parse_youtube_url("youtube.com/watch?v=dQw4w9WgXcQ")
    """
    cleaned_url = url.strip()
    if not cleaned_url:
        raise ValueError(build_invalid_youtube_url_message(url))
    parse_target = cleaned_url if "://" in cleaned_url else f"https://{cleaned_url}"
    return urlparse(parse_target)


def extract_video_id_from_youtube_url(path: str, query: str) -> str:
    """Read the video id from watch, shorts, embed, or live URLs.

    Example: extract_video_id_from_youtube_url("/watch", "v=dQw4w9WgXcQ")
    """
    parts = split_youtube_path(path)
    if parts and parts[0] in {"shorts", "embed", "live"}:
        return validate_youtube_video_id(parts[1] if len(parts) > 1 else "")
    query_video_ids = parse_qs(query).get("v", [""])
    return validate_youtube_video_id(query_video_ids[0])


def split_youtube_path(path: str) -> list[str]:
    """Split a YouTube path into non-empty parts.

    Example: split_youtube_path("/shorts/dQw4w9WgXcQ")
    """
    return [part for part in path.split("/") if part]


def first_path_part(path: str) -> str:
    """Return the first non-empty URL path part.

    Example: first_path_part("/dQw4w9WgXcQ")
    """
    parts = split_youtube_path(path)
    return parts[0] if parts else ""


def validate_youtube_video_id(video_id: str) -> str:
    """Validate the expected YouTube video id shape.

    Example: validate_youtube_video_id("dQw4w9WgXcQ")
    """
    if YOUTUBE_VIDEO_ID_PATTERN.fullmatch(video_id):
        return video_id
    raise ValueError(
        f"Video ID invalido: valor com {len(video_id)} caracteres; "
        "esperado 11 caracteres com letras, numeros, '-' ou '_'."
    )


def build_invalid_youtube_url_message(url: str) -> str:
    """Build a user-safe validation message without echoing full URLs.

    Example: build_invalid_youtube_url_message("https://example.com")
    """
    parsed_url = parse_youtube_url_for_description(url)
    host = parsed_url.hostname or "ausente"
    return (
        f"URL invalida: host {host!r}, tamanho {len(url.strip())}; "
        "esperado URL normal do YouTube ou Shorts."
    )


def parse_youtube_url_for_description(url: str) -> ParseResult:
    """Parse URL details for error descriptions only.

    Example: parse_youtube_url_for_description("youtube.com/watch")
    """
    cleaned_url = url.strip()
    parse_target = cleaned_url if "://" in cleaned_url else f"https://{cleaned_url}"
    return urlparse(parse_target)


def fetch_youtube_transcript_text(video_id: str, transcript_api: TranscriptApi) -> str:
    """Fetch preferred public captions and return one plain text string.

    Example: fetch_youtube_transcript_text("dQw4w9WgXcQ", YouTubeTranscriptApi())
    """
    try:
        transcript = transcript_api.fetch(video_id, languages=PREFERRED_TRANSCRIPT_LANGUAGES)
    except NoTranscriptFound:
        transcript = fetch_any_youtube_transcript(video_id, transcript_api)
    except TranscriptsDisabled as exc:
        raise RuntimeError(NO_PUBLIC_TRANSCRIPT_MESSAGE) from exc
    except (InvalidVideoId, VideoUnavailable, VideoUnplayable) as exc:
        raise ValueError(build_invalid_youtube_video_message(video_id)) from exc
    except CouldNotRetrieveTranscript as exc:
        raise RuntimeError(TRANSCRIPT_UNAVAILABLE_MESSAGE) from exc
    return join_transcript_text(transcript)


def fetch_any_youtube_transcript(
    video_id: str,
    transcript_api: TranscriptApi,
) -> Iterable[object]:
    """Fetch the first available transcript when preferred languages fail.

    Example: fetch_any_youtube_transcript("dQw4w9WgXcQ", YouTubeTranscriptApi())
    """
    transcript_list = list_available_transcripts(video_id, transcript_api)
    for transcript in transcript_list:
        fetched = fetch_transcript_reference(transcript)
        if fetched is not None:
            return fetched
    raise RuntimeError(TRANSCRIPT_UNAVAILABLE_MESSAGE)


def list_available_transcripts(
    video_id: str,
    transcript_api: TranscriptApi,
) -> list[TranscriptReference]:
    """List public transcripts or raise the free-analysis no-caption message.

    Example: list_available_transcripts("dQw4w9WgXcQ", YouTubeTranscriptApi())
    """
    try:
        transcripts = list(transcript_api.list(video_id))
    except (NoTranscriptFound, TranscriptsDisabled) as exc:
        raise RuntimeError(NO_PUBLIC_TRANSCRIPT_MESSAGE) from exc
    except (InvalidVideoId, VideoUnavailable, VideoUnplayable) as exc:
        raise ValueError(build_invalid_youtube_video_message(video_id)) from exc
    except CouldNotRetrieveTranscript as exc:
        raise RuntimeError(TRANSCRIPT_UNAVAILABLE_MESSAGE) from exc
    if not transcripts:
        raise RuntimeError(NO_PUBLIC_TRANSCRIPT_MESSAGE)
    return transcripts


def fetch_transcript_reference(transcript: TranscriptReference) -> Iterable[object] | None:
    """Fetch one transcript reference, returning None for retryable failures.

    Example: fetch_transcript_reference(transcript)
    """
    try:
        return transcript.fetch()
    except CouldNotRetrieveTranscript:
        return None


def build_invalid_youtube_video_message(video_id: str) -> str:
    """Build a safe message for invalid or unavailable video ids.

    Example: build_invalid_youtube_video_message("dQw4w9WgXcQ")
    """
    return (
        f"Video do YouTube indisponivel: id com {len(video_id)} caracteres; "
        "esperado um video publico com legenda acessivel."
    )


def join_transcript_text(transcript: Iterable[object]) -> str:
    """Join transcript snippets into one normalized text.

    Example: join_transcript_text([{'text': 'ola'}, {'text': 'mundo'}])
    """
    text_parts = [extract_transcript_snippet_text(snippet) for snippet in transcript]
    transcript_text = normalize_transcript_text(" ".join(part for part in text_parts if part))
    if transcript_text:
        return transcript_text
    raise RuntimeError(NO_PUBLIC_TRANSCRIPT_MESSAGE)


def extract_transcript_snippet_text(snippet: object) -> str:
    """Extract text from dict-like or object transcript snippets.

    Example: extract_transcript_snippet_text({'text': 'conteudo'})
    """
    text = snippet.get("text") if isinstance(snippet, Mapping) else getattr(snippet, "text", "")
    return text.strip() if isinstance(text, str) else ""


def normalize_transcript_text(text: str) -> str:
    """Normalize transcript whitespace before sending it to chat completion.

    Example: normalize_transcript_text("linha 1\\n linha 2")
    """
    return re.sub(r"\s+", " ", text).strip()


def summarize_youtube_transcript(
    transcript_text: str,
    request_post: OpenRouterPost = requests.post,
) -> str:
    """Send the transcript to OpenRouter chat completions.

    Example: summarize_youtube_transcript("conteudo transcrito")
    """
    return call_openrouter_chat_completion(
        build_youtube_analysis_prompt(transcript_text),
        YOUTUBE_ANALYZER_TOOL_NAME,
        request_post,
    )


def build_youtube_analysis_prompt(transcript_text: str) -> str:
    """Build the YouTube Analyzer prompt used by OpenRouter chat.

    Example: build_youtube_analysis_prompt("texto do video")
    """
    return (
        "Gere uma an\u00e1lise clara do v\u00eddeo com:\n"
        "- resumo geral;\n"
        "- t\u00f3picos principais;\n"
        "- ideias importantes;\n"
        "- conclus\u00e3o.\n"
        "Use apenas o conte\u00fado da transcri\u00e7\u00e3o fornecida. "
        "N\u00e3o invente informa\u00e7\u00f5es.\n\n"
        f"Transcri\u00e7\u00e3o:\n{transcript_text[:YOUTUBE_TRANSCRIPT_MAX_CHARS]}"
    )
