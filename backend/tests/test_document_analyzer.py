import os
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.services.ai import document_analyzer


class FakeOpenRouterResponse:
    def __init__(self, status_code: int, content: str) -> None:
        self.status_code = status_code
        self.content = content

    def json(self) -> dict[str, object]:
        return {"choices": [{"message": {"content": self.content}}]}


class FakeOpenRouterPost:
    def __init__(self, responses: list[FakeOpenRouterResponse]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def __call__(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
        timeout: int,
    ) -> FakeOpenRouterResponse:
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return self.responses.pop(0)


class DocumentAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clean_env = patch.dict(
            os.environ,
            {
                "OPENROUTER_API_KEY": "secret-key",
                "OPENROUTER_MODEL": "model:free",
                "OPENROUTER_FALLBACK_MODELS": "",
            },
            clear=False,
        )
        self.clean_env.start()

    def tearDown(self) -> None:
        self.clean_env.stop()

    def test_build_document_prompt_uses_selected_action(self) -> None:
        prompt = document_analyzer.build_document_prompt("summary", "Texto", "")

        self.assertIn("Gere um resumo claro", prompt)
        self.assertIn("Conteudo do documento:\nTexto", prompt)

    def test_get_uploaded_document_extension_reads_filename_suffix(self) -> None:
        upload = FileStorage(BytesIO(b"conteudo"), filename="notas.pdf")

        extension = document_analyzer.get_uploaded_document_extension(upload)

        self.assertEqual(extension, "pdf")

    def test_validate_uploaded_document_rejects_bad_header(self) -> None:
        upload = FileStorage(BytesIO(b"nao e pdf"), filename="notas.pdf")

        with self.assertRaisesRegex(ValueError, "conteudo do arquivo"):
            document_analyzer.validate_uploaded_document(upload, "pdf")

    def test_save_document_upload_writes_temp_file(self) -> None:
        upload = FileStorage(BytesIO(b"conteudo"), filename="notas.txt")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = document_analyzer.save_document_upload(upload, Path(temp_dir), "txt")

            self.assertEqual(path.read_bytes(), b"conteudo")

    def test_validate_saved_document_checks_office_container(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.docx"
            path.write_bytes(b"bad")

            with self.assertRaisesRegex(ValueError, "Arquivo Office invalido"):
                document_analyzer.validate_saved_document(path, "docx")

    def test_build_document_prompt_includes_user_question(self) -> None:
        prompt = document_analyzer.build_document_prompt("question", "Texto", "Qual prazo?")

        self.assertIn("Pergunta do usuario: Qual prazo?", prompt)

    def test_validate_document_action_requires_known_action(self) -> None:
        with self.assertRaisesRegex(ValueError, "Acao invalida"):
            document_analyzer.validate_document_action("outra", "")

    def test_validate_document_action_requires_question_text(self) -> None:
        with self.assertRaisesRegex(ValueError, "Informe uma pergunta"):
            document_analyzer.validate_document_action("question", "")

    def test_split_document_chunks_splits_large_text(self) -> None:
        text = "a" * (document_analyzer.DOCUMENT_ANALYZER_CHUNK_CHARS + 3)

        chunks = document_analyzer.split_document_chunks(text)

        self.assertEqual(len(chunks), 2)
        self.assertEqual(len(chunks[0]), document_analyzer.DOCUMENT_ANALYZER_CHUNK_CHARS)

    def test_analyze_document_text_uses_direct_prompt_for_short_text(self) -> None:
        fake_post = FakeOpenRouterPost([FakeOpenRouterResponse(200, "analise")])

        answer = document_analyzer.analyze_document_text("conteudo", "summary", "", fake_post)

        self.assertEqual(answer, "analise")
        self.assertEqual(len(fake_post.calls), 1)
        self.assertEqual(fake_post.calls[0]["json"]["temperature"], 0.2)
        self.assertEqual(fake_post.calls[0]["json"]["max_tokens"], 1600)

    def test_analyze_document_text_summarizes_large_text_first(self) -> None:
        fake_post = FakeOpenRouterPost(
            [
                FakeOpenRouterResponse(200, "parte 1"),
                FakeOpenRouterResponse(200, "parte 2"),
                FakeOpenRouterResponse(200, "final"),
            ]
        )
        text = "a" * (document_analyzer.DOCUMENT_ANALYZER_DIRECT_CHARS + 1)

        answer = document_analyzer.analyze_document_text(text, "summary", "", fake_post)

        self.assertEqual(answer, "final")
        self.assertEqual(len(fake_post.calls), 3)

    def test_summarize_document_chunks_calls_each_chunk(self) -> None:
        fake_post = FakeOpenRouterPost(
            [FakeOpenRouterResponse(200, "parte 1"), FakeOpenRouterResponse(200, "parte 2")]
        )

        summaries = document_analyzer.summarize_document_chunks(["a", "b"], fake_post)

        self.assertEqual(summaries, ["parte 1", "parte 2"])
        self.assertEqual(len(fake_post.calls), 2)

    def test_build_chunk_summary_prompt_includes_part_number(self) -> None:
        prompt = document_analyzer.build_chunk_summary_prompt("Texto", 3)

        self.assertIn("parte 3", prompt)
        self.assertIn("Texto", prompt)

    def test_request_document_analysis_uses_document_tool_name(self) -> None:
        fake_post = FakeOpenRouterPost([FakeOpenRouterResponse(200, "analise")])

        answer = document_analyzer.request_document_analysis("Texto", fake_post)

        self.assertEqual(answer, "analise")
        self.assertEqual(fake_post.calls[0]["json"]["messages"][0]["content"], document_analyzer.DOCUMENT_ANALYZER_SYSTEM_PROMPT)

    def test_get_action_label_returns_configured_label(self) -> None:
        label = document_analyzer.get_action_label("quiz")

        self.assertEqual(label, "Quiz")

    def test_analyze_uploaded_document_removes_temporary_file(self) -> None:
        saved_paths: list[Path] = []
        upload = FileStorage(BytesIO(b"conteudo"), filename="../notas.txt", content_type="text/plain")
        fake_post = FakeOpenRouterPost([FakeOpenRouterResponse(200, "analise")])

        def fake_extract(path: Path, extension: str) -> str:
            saved_paths.append(path)
            self.assertTrue(path.exists())
            self.assertEqual(extension, "txt")
            return "conteudo"

        with patch.object(document_analyzer, "extract_document_text", side_effect=fake_extract):
            result = document_analyzer.analyze_uploaded_document(upload, "summary", "", fake_post)

        self.assertEqual(result.answer, "analise")
        self.assertEqual(result.filename, "notas.txt")
        self.assertFalse(saved_paths[0].exists())

    def test_get_document_accept_attribute_lists_allowed_extensions(self) -> None:
        accept_attribute = document_analyzer.get_document_accept_attribute()

        self.assertIn(".pdf", accept_attribute)
        self.assertIn(".docx", accept_attribute)

    def test_log_document_analyzer_call_uses_safe_metadata(self) -> None:
        with self.assertLogs(document_analyzer.logger, level="INFO") as records:
            document_analyzer.log_document_analyzer_call("pdf")

        self.assertIn('"ferramenta": "document_analyzer_ai"', records.output[0])
        self.assertIn('"tipo_arquivo": "pdf"', records.output[0])


if __name__ == "__main__":
    unittest.main()
