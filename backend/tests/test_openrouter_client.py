import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.services.ai import openrouter_client


class FakeOpenRouterResponse:
    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self.payload = payload

    def json(self) -> object:
        if isinstance(self.payload, ValueError):
            raise self.payload
        return self.payload


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
        self.calls.append(
            {"url": url, "headers": headers, "json": json, "timeout": timeout}
        )
        return self.responses.pop(0)


def build_chat_payload(content: str) -> dict[str, object]:
    return {"choices": [{"message": {"content": content}}]}


class OpenRouterClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clean_env = patch.dict(
            os.environ,
            {"OPENROUTER_API_KEY": "secret-key"},
            clear=False,
        )
        self.clean_env.start()
        os.environ.pop("OPENROUTER_MODEL", None)
        os.environ.pop("OPENROUTER_FALLBACK_MODELS", None)

    def tearDown(self) -> None:
        self.clean_env.stop()

    def test_call_openrouter_chat_completion_uses_default_free_payload(self) -> None:
        os.environ.pop("OPENROUTER_MODEL", None)
        os.environ.pop("OPENROUTER_FALLBACK_MODELS", None)
        fake_post = FakeOpenRouterPost([FakeOpenRouterResponse(200, build_chat_payload("ok"))])

        result = openrouter_client.call_openrouter_chat_completion(
            "Conteudo",
            "document_analyzer_ai",
            fake_post,
        )

        request_json = fake_post.calls[0]["json"]
        self.assertEqual(result, "ok")
        self.assertEqual(request_json["model"], "openai/gpt-oss-20b:free")
        self.assertEqual(request_json["max_tokens"], 1200)
        self.assertEqual(request_json["temperature"], 0.3)

    def test_call_openrouter_chat_completion_falls_back_in_order(self) -> None:
        os.environ["OPENROUTER_MODEL"] = "openai/gpt-oss-20b:free"
        os.environ["OPENROUTER_FALLBACK_MODELS"] = (
            "qwen/qwen3-coder:free,meta-llama/llama-3.3-70b-instruct:free"
        )
        fake_post = FakeOpenRouterPost(
            [
                FakeOpenRouterResponse(429, {"error": "limit"}),
                FakeOpenRouterResponse(200, build_chat_payload("")),
                FakeOpenRouterResponse(200, build_chat_payload("resumo")),
            ]
        )

    def test_call_openrouter_chat_completion_falls_back_from_missing_model(self) -> None:
        os.environ["OPENROUTER_MODEL"] = "missing/model:free"
        os.environ["OPENROUTER_FALLBACK_MODELS"] = "qwen/qwen3-coder:free"
        fake_post = FakeOpenRouterPost(
            [
                FakeOpenRouterResponse(404, {"error": "not found"}),
                FakeOpenRouterResponse(200, build_chat_payload("resumo")),
            ]
        )

        result = openrouter_client.call_openrouter_chat_completion("Conteudo", "tool", fake_post)

        self.assertEqual(result, "resumo")
        self.assertEqual(len(fake_post.calls), 2)

    def test_call_openrouter_chat_completion_uses_custom_settings(self) -> None:
        settings = openrouter_client.OpenRouterChatSettings("Sistema", 0.2, 1600, 90)
        fake_post = FakeOpenRouterPost([FakeOpenRouterResponse(200, build_chat_payload("ok"))])

        result = openrouter_client.call_openrouter_chat_completion_with_settings(
            "Conteudo",
            "document_analyzer_ai",
            settings,
            fake_post,
        )

        request_json = fake_post.calls[0]["json"]
        self.assertEqual(result, "ok")
        self.assertEqual(request_json["messages"][0]["content"], "Sistema")
        self.assertEqual(request_json["temperature"], 0.2)
        self.assertEqual(request_json["max_tokens"], 1600)
        self.assertEqual(fake_post.calls[0]["timeout"], 90)

    def test_call_openrouter_chat_completion_stops_on_invalid_key(self) -> None:
        fake_post = FakeOpenRouterPost([FakeOpenRouterResponse(401, {"error": "auth"})])

        with self.assertRaisesRegex(RuntimeError, "OPENROUTER_API_KEY invalida"):
            openrouter_client.call_openrouter_chat_completion("Conteudo", "tool", fake_post)

        self.assertEqual(len(fake_post.calls), 1)

    def test_get_openrouter_api_key_requires_value(self) -> None:
        os.environ.pop("OPENROUTER_API_KEY")

        with self.assertRaisesRegex(RuntimeError, "Configure OPENROUTER_API_KEY"):
            openrouter_client.get_openrouter_api_key()

    def test_get_openrouter_api_key_rejects_placeholder_value(self) -> None:
        os.environ["OPENROUTER_API_KEY"] = "cole_sua_chave_aqui"

        with self.assertRaisesRegex(RuntimeError, "Valor atual: prefixo 'cole_"):
            openrouter_client.get_openrouter_api_key()

    def test_is_placeholder_openrouter_api_key_matches_local_examples(self) -> None:
        self.assertTrue(openrouter_client.is_placeholder_openrouter_api_key("your_api_key"))
        self.assertFalse(openrouter_client.is_placeholder_openrouter_api_key("sk-real-value"))

    def test_describe_openrouter_secret_hides_secret_body(self) -> None:
        description = openrouter_client.describe_openrouter_secret("secret-value")

        self.assertEqual(description, "prefixo 'secret', tamanho 12")
        self.assertNotIn("value", description)

    def test_build_openrouter_chat_attempts_removes_duplicates(self) -> None:
        os.environ["OPENROUTER_MODEL"] = "qwen/qwen3-coder:free"
        os.environ["OPENROUTER_FALLBACK_MODELS"] = (
            "qwen/qwen3-coder:free,meta-llama/llama-3.3-70b-instruct:free"
        )

        attempts = openrouter_client.build_openrouter_chat_attempts()

        self.assertEqual([attempt.model for attempt in attempts], [
            "qwen/qwen3-coder:free",
            "meta-llama/llama-3.3-70b-instruct:free",
        ])
        self.assertFalse(attempts[0].used_fallback)
        self.assertTrue(attempts[1].used_fallback)

    def test_build_openrouter_chat_attempts_uses_defaults_when_env_empty(self) -> None:
        os.environ["OPENROUTER_MODEL"] = ""
        os.environ["OPENROUTER_FALLBACK_MODELS"] = ""

        attempts = openrouter_client.build_openrouter_chat_attempts()

        self.assertEqual(attempts[0].model, "openai/gpt-oss-20b:free")
        self.assertEqual(attempts[1].model, "google/gemma-4-26b-a4b-it:free")

    def test_split_openrouter_models_trims_empty_values(self) -> None:
        models = openrouter_client.split_openrouter_models(" a:free, ,b:free ")

        self.assertEqual(models, ["a:free", "b:free"])

    def test_validate_free_openrouter_model_rejects_router_and_paid_model(self) -> None:
        invalid_models = ("openrouter/free", "openai/gpt-4o")

        for model in invalid_models:
            with self.subTest(model=model):
                with self.assertRaisesRegex(RuntimeError, "sufixo ':free'"):
                    openrouter_client.validate_free_openrouter_model(model)

    def test_build_openrouter_headers_keeps_api_key_only_in_header(self) -> None:
        headers = openrouter_client.build_openrouter_headers("secret-key")

        self.assertEqual(headers["Authorization"], "Bearer secret-key")
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_build_openrouter_chat_payload_uses_standard_system_prompt(self) -> None:
        payload = openrouter_client.build_openrouter_chat_payload("Pergunta", "model:free")

        self.assertEqual(payload["model"], "model:free")
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertIn("sem inventar informa\u00e7\u00f5es", payload["messages"][0]["content"])

    def test_extract_openrouter_chat_content_handles_bad_shapes(self) -> None:
        responses = [
            FakeOpenRouterResponse(200, ValueError("bad json")),
            FakeOpenRouterResponse(200, {"choices": []}),
            FakeOpenRouterResponse(200, {"choices": [{"message": {}}]}),
        ]

        for response in responses:
            with self.subTest(payload=response.payload):
                self.assertEqual(openrouter_client.extract_openrouter_chat_content(response), "")

    def test_extract_openrouter_message_content_strips_text(self) -> None:
        content = openrouter_client.extract_openrouter_message_content(
            {"message": {"content": "  texto  "}}
        )

        self.assertEqual(content, "texto")

    def test_build_status_and_empty_response_errors_are_user_safe(self) -> None:
        status_error = openrouter_client.build_status_error(429, "model:free")
        empty_error = openrouter_client.build_empty_response_error("model:free")

        self.assertIn("limite gratuito", status_error)
        self.assertIn("resposta vazia", empty_error)

    def test_get_openrouter_attempt_error_returns_retryable_error(self) -> None:
        response = FakeOpenRouterResponse(404, {"error": "missing"})

        message = openrouter_client.get_openrouter_attempt_error(response, "model:free")

        self.assertIn("indisponivel", message)

    def test_log_openrouter_attempt_contains_only_safe_metadata(self) -> None:
        with self.assertLogs(openrouter_client.logger, level="INFO") as records:
            openrouter_client.log_openrouter_attempt("tool", "model:free", 200, True)

        log_text = records.output[0]
        logged = json.loads(log_text[log_text.index("{"):])
        self.assertEqual(
            set(logged),
            {"ferramenta", "modelo", "status_http", "fallback_usado"},
        )
        self.assertEqual(logged["modelo"], "model:free")


if __name__ == "__main__":
    unittest.main()
