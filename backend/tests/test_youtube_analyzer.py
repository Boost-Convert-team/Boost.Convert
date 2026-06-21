import os
import sys
import unittest
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from youtube_transcript_api import CouldNotRetrieveTranscript, NoTranscriptFound


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.services.ai import youtube_analyzer


VIDEO_ID = "dQw4w9WgXcQ"


@dataclass(frozen=True)
class FakeTranscriptSnippet:
    text: str


class FakeTranscriptReference:
    def __init__(self, transcript: list[object], error: Exception | None = None) -> None:
        self.transcript = transcript
        self.error = error
        self.fetch_count = 0

    def fetch(self, preserve_formatting: bool = False) -> Iterable[object]:
        self.fetch_count += 1
        if self.error is not None:
            raise self.error
        return self.transcript


class FakeTranscriptApi:
    def __init__(
        self,
        preferred_transcript: list[object] | None = None,
        transcript_references: list[FakeTranscriptReference] | None = None,
        fetch_error: Exception | None = None,
        list_error: Exception | None = None,
    ) -> None:
        self.preferred_transcript = preferred_transcript or []
        self.transcript_references = transcript_references or []
        self.fetch_error = fetch_error
        self.list_error = list_error
        self.fetch_languages: list[tuple[str, ...]] = []
        self.listed_video_id = ""

    def fetch(
        self,
        video_id: str,
        languages: Iterable[str] = youtube_analyzer.PREFERRED_TRANSCRIPT_LANGUAGES,
        preserve_formatting: bool = False,
    ) -> Iterable[object]:
        self.fetch_languages.append(tuple(languages))
        if self.fetch_error is not None:
            raise self.fetch_error
        return self.preferred_transcript

    def list(self, video_id: str) -> Iterable[FakeTranscriptReference]:
        self.listed_video_id = video_id
        if self.list_error is not None:
            raise self.list_error
        return self.transcript_references


class FakeOpenRouterResponse:
    def __init__(self, status_code: int, payload: Mapping[str, object]) -> None:
        self.status_code = status_code
        self.payload = payload

    def json(self) -> Mapping[str, object]:
        return self.payload


class FakeOpenRouterPost:
    def __init__(self, response: FakeOpenRouterResponse) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def __call__(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json: Mapping[str, object],
        timeout: int,
    ) -> FakeOpenRouterResponse:
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return self.response


def build_no_transcript_error() -> NoTranscriptFound:
    return NoTranscriptFound(VIDEO_ID, youtube_analyzer.PREFERRED_TRANSCRIPT_LANGUAGES, None)


def build_chat_payload(content: str) -> dict[str, object]:
    return {"choices": [{"message": {"content": content}}]}


class YoutubeAnalyzerTests(unittest.TestCase):
    def test_extract_youtube_video_id_accepts_regular_shorts_and_short_urls(self) -> None:
        urls = {
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ": VIDEO_ID,
            "https://youtube.com/shorts/dQw4w9WgXcQ?feature=share": VIDEO_ID,
            "https://youtu.be/dQw4w9WgXcQ?t=12": VIDEO_ID,
        }

        for url, expected_video_id in urls.items():
            with self.subTest(url=url):
                self.assertEqual(youtube_analyzer.extract_youtube_video_id(url), expected_video_id)

    def test_extract_youtube_video_id_rejects_other_hosts(self) -> None:
        with self.assertRaisesRegex(ValueError, "esperado URL normal do YouTube ou Shorts"):
            youtube_analyzer.extract_youtube_video_id("https://example.com/watch?v=dQw4w9WgXcQ")

    def test_fetch_youtube_transcript_text_uses_preferred_language_order(self) -> None:
        api = FakeTranscriptApi(
            preferred_transcript=[
                FakeTranscriptSnippet(" Olá "),
                {"text": "mundo\nnovo"},
            ]
        )

        text = youtube_analyzer.fetch_youtube_transcript_text(VIDEO_ID, api)

        self.assertEqual(text, "Olá mundo novo")
        self.assertEqual(api.fetch_languages, [("pt", "pt-BR", "en")])

    def test_fetch_youtube_transcript_text_falls_back_to_any_available(self) -> None:
        failed_reference = FakeTranscriptReference([], CouldNotRetrieveTranscript(VIDEO_ID))
        working_reference = FakeTranscriptReference([FakeTranscriptSnippet("fallback ok")])
        api = FakeTranscriptApi(
            fetch_error=build_no_transcript_error(),
            transcript_references=[failed_reference, working_reference],
        )

        text = youtube_analyzer.fetch_youtube_transcript_text(VIDEO_ID, api)

        self.assertEqual(text, "fallback ok")
        self.assertEqual(api.listed_video_id, VIDEO_ID)
        self.assertEqual(failed_reference.fetch_count, 1)
        self.assertEqual(working_reference.fetch_count, 1)

    def test_fetch_youtube_transcript_text_returns_public_caption_message(self) -> None:
        api = FakeTranscriptApi(fetch_error=build_no_transcript_error())

        with self.assertRaisesRegex(RuntimeError, youtube_analyzer.NO_PUBLIC_TRANSCRIPT_MESSAGE):
            youtube_analyzer.fetch_youtube_transcript_text(VIDEO_ID, api)

    def test_build_youtube_analysis_prompt_uses_requested_instruction(self) -> None:
        prompt = youtube_analyzer.build_youtube_analysis_prompt("conteudo")

        self.assertIn("Gere uma análise clara do vídeo com:", prompt)
        self.assertIn("- resumo geral;", prompt)
        self.assertIn("Não invente informações.", prompt)
        self.assertIn("Transcrição:\nconteudo", prompt)

    def test_summarize_youtube_transcript_posts_chat_completion(self) -> None:
        fake_post = FakeOpenRouterPost(FakeOpenRouterResponse(200, build_chat_payload("resumo")))

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "secret-key"}):
            result = youtube_analyzer.summarize_youtube_transcript("conteudo", fake_post)

        request = fake_post.calls[0]
        request_json = request["json"]
        self.assertEqual(result, "resumo")
        self.assertIn("/chat/completions", str(request["url"]))
        self.assertNotIn("/audio/transcriptions", str(request["url"]))
        self.assertIsInstance(request_json, Mapping)
        self.assertEqual(request_json["model"], "openai/gpt-oss-20b:free")

    def test_analyze_youtube_video_returns_summary_from_transcript_and_chat(self) -> None:
        api = FakeTranscriptApi([FakeTranscriptSnippet("conteudo do video")])
        fake_post = FakeOpenRouterPost(FakeOpenRouterResponse(200, build_chat_payload("analise")))

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "secret-key"}):
            result = youtube_analyzer.analyze_youtube_video(
                f"https://www.youtube.com/watch?v={VIDEO_ID}",
                api,
                fake_post,
            )

        self.assertEqual(result.title, f"Video do YouTube: {VIDEO_ID}")
        self.assertEqual(result.summary, "analise")


if __name__ == "__main__":
    unittest.main()
