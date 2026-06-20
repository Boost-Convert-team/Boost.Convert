import json
import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

import requests
from requests import Response
from requests.exceptions import RequestException


OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_OPENROUTER_MODEL = "openai/gpt-oss-20b:free"
DEFAULT_OPENROUTER_FALLBACK_MODELS = (
    "google/gemma-4-26b-a4b-it:free",
    "qwen/qwen3-coder:free",
    "meta-llama/llama-3.3-70b-instruct:free",
)
OPENROUTER_SYSTEM_PROMPT = (
    "Voc\u00ea \u00e9 uma IA objetiva, precisa e \u00fatil. "
    "Responda de forma clara, sem inventar informa\u00e7\u00f5es."
)
OPENROUTER_RETRY_STATUS_CODES = {404, 429, 500, 502, 503}
OPENROUTER_TIMEOUT_SECONDS = 120
OPENROUTER_CONNECTION_ERROR = (
    "Erro de conexao com a IA: OpenRouter nao respondeu dentro do tempo esperado."
)

logger = logging.getLogger(__name__)


class OpenRouterPost(Protocol):
    def __call__(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json: Mapping[str, object],
        timeout: int,
    ) -> Response:
        ...


@dataclass(frozen=True)
class OpenRouterChatAttempt:
    model: str
    used_fallback: bool


@dataclass(frozen=True)
class OpenRouterChatSettings:
    system_prompt: str
    temperature: float
    max_tokens: int
    timeout_seconds: int


DEFAULT_OPENROUTER_CHAT_SETTINGS = OpenRouterChatSettings(
    OPENROUTER_SYSTEM_PROMPT,
    0.3,
    1200,
    OPENROUTER_TIMEOUT_SECONDS,
)


def call_openrouter_chat_completion(
    user_content: str,
    tool_name: str,
    request_post: OpenRouterPost = requests.post,
) -> str:
    """Call OpenRouter chat with free-model fallback.

    Example: call_openrouter_chat_completion("Resuma este texto", "youtube_analyzer")
    """
    return call_openrouter_chat_completion_with_settings(
        user_content,
        tool_name,
        DEFAULT_OPENROUTER_CHAT_SETTINGS,
        request_post,
    )


def call_openrouter_chat_completion_with_settings(
    user_content: str,
    tool_name: str,
    settings: OpenRouterChatSettings,
    request_post: OpenRouterPost = requests.post,
) -> str:
    """Call OpenRouter chat with custom payload settings and fallback.

    Example: call_openrouter_chat_completion_with_settings("Texto", "tool", settings)
    """
    api_key = get_openrouter_api_key()
    last_error = "Erro na IA: todos os modelos gratuitos retornaram resposta vazia."

    for attempt in build_openrouter_chat_attempts():
        response = post_openrouter_chat_attempt(
            api_key, user_content, tool_name, settings, attempt, request_post
        )
        attempt_error = get_openrouter_attempt_error(response, attempt.model)
        if attempt_error:
            last_error = attempt_error
            continue

        content = extract_openrouter_chat_content(response)
        if content:
            return content
        last_error = build_empty_response_error(attempt.model)

    raise RuntimeError(last_error)


def get_openrouter_attempt_error(response: Response, model: str) -> str:
    """Return a retryable error or raise for terminal OpenRouter failures.

    Example: get_openrouter_attempt_error(response, "qwen/qwen3-coder:free")
    """
    if response.status_code == 401:
        raise RuntimeError("Erro na IA: OPENROUTER_API_KEY invalida ou expirada.")
    if response.status_code in OPENROUTER_RETRY_STATUS_CODES:
        return build_status_error(response.status_code, model)
    if response.status_code >= 400:
        raise RuntimeError(build_status_error(response.status_code, model))
    return ""


def post_openrouter_chat_attempt(
    api_key: str,
    user_content: str,
    tool_name: str,
    settings: OpenRouterChatSettings,
    attempt: OpenRouterChatAttempt,
    request_post: OpenRouterPost,
) -> Response:
    """Post one chat attempt using the provided model and payload settings.

    Example: post_openrouter_chat_attempt(key, "Texto", "tool", settings, attempt, post)
    """
    payload = build_openrouter_chat_payload(
        user_content,
        attempt.model,
        settings.system_prompt,
        settings.temperature,
        settings.max_tokens,
    )
    return post_openrouter_json(
        api_key,
        OPENROUTER_CHAT_COMPLETIONS_URL,
        payload,
        tool_name,
        attempt.model,
        attempt.used_fallback,
        settings.timeout_seconds,
        request_post,
    )


def get_openrouter_api_key() -> str:
    """Read the OpenRouter API key from the environment.

    Example: get_openrouter_api_key()
    """
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if api_key:
        if is_placeholder_openrouter_api_key(api_key):
            raise RuntimeError(
                "Configure OPENROUTER_API_KEY com uma chave real. "
                f"Valor atual: {describe_openrouter_secret(api_key)}; "
                "esperado segredo da OpenRouter."
            )
        return api_key
    raise RuntimeError("Configure OPENROUTER_API_KEY para usar esta ferramenta.")


def is_placeholder_openrouter_api_key(api_key: str) -> bool:
    """Detect local placeholder values before calling OpenRouter.

    Example: is_placeholder_openrouter_api_key("cole_sua_chave_aqui")
    """
    normalized = api_key.strip().lower().replace("-", "_")
    placeholder_parts = ("cole_sua", "sua_chave", "your_api_key", "openrouter_api_key")
    return any(part in normalized for part in placeholder_parts)


def describe_openrouter_secret(api_key: str) -> str:
    """Describe a secret without exposing it in logs or UI errors.

    Example: describe_openrouter_secret("cole_sua_chave_aqui")
    """
    visible_prefix = api_key[:6] if api_key else ""
    return f"prefixo {visible_prefix!r}, tamanho {len(api_key)}"


def build_openrouter_chat_attempts() -> list[OpenRouterChatAttempt]:
    """Build the primary and fallback model order.

    Example: build_openrouter_chat_attempts()[0].model
    """
    primary_model = os.getenv("OPENROUTER_MODEL", "").strip()
    fallback_text = os.getenv("OPENROUTER_FALLBACK_MODELS", "").strip()
    if not primary_model:
        primary_model = DEFAULT_OPENROUTER_MODEL
    if not fallback_text:
        fallback_text = ",".join(DEFAULT_OPENROUTER_FALLBACK_MODELS)
    models = [primary_model, *split_openrouter_models(fallback_text)]
    return [
        OpenRouterChatAttempt(model, index > 0)
        for index, model in enumerate(remove_duplicate_models(models))
    ]


def split_openrouter_models(models_text: str) -> list[str]:
    """Split a comma-separated OpenRouter model list.

    Example: split_openrouter_models("a:free,b:free")
    """
    return [model.strip() for model in models_text.split(",") if model.strip()]


def remove_duplicate_models(models: list[str]) -> list[str]:
    """Keep the first occurrence of each valid free model slug.

    Example: remove_duplicate_models(["a:free", "a:free"])
    """
    unique_models: list[str] = []
    for model in models:
        validate_free_openrouter_model(model)
        if model not in unique_models:
            unique_models.append(model)
    return unique_models


def validate_free_openrouter_model(model: str) -> None:
    """Reject routers and paid model slugs.

    Example: validate_free_openrouter_model("qwen/qwen3-coder:free")
    """
    if model == "openrouter/free" or not model.endswith(":free"):
        raise RuntimeError(
            f"Erro na IA: modelo {model!r} invalido. "
            "Esperado slug especifico da OpenRouter com sufixo ':free'."
        )


def post_openrouter_json(
    api_key: str,
    url: str,
    payload: Mapping[str, object],
    tool_name: str,
    model: str,
    used_fallback: bool,
    timeout_seconds: int,
    request_post: OpenRouterPost = requests.post,
) -> Response:
    """Post one JSON payload to OpenRouter with safe logging.

    Example: post_openrouter_json(key, url, payload, "youtube_analyzer", model, False, 120, post)
    """
    try:
        response = request_post(
            url,
            headers=build_openrouter_headers(api_key),
            json=payload,
            timeout=timeout_seconds,
        )
    except RequestException:
        log_openrouter_attempt(tool_name, model, 0, used_fallback)
        raise RuntimeError(OPENROUTER_CONNECTION_ERROR)

    log_openrouter_attempt(tool_name, model, response.status_code, used_fallback)
    return response


def build_openrouter_headers(api_key: str) -> dict[str, str]:
    """Build OpenRouter auth headers without logging secrets.

    Example: build_openrouter_headers("sk-or-...")
    """
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def build_openrouter_chat_payload(
    user_content: str,
    model: str,
    system_prompt: str = OPENROUTER_SYSTEM_PROMPT,
    temperature: float = 0.3,
    max_tokens: int = 1200,
) -> dict[str, object]:
    """Build the standard Boost Convert chat payload.

    Example: build_openrouter_chat_payload("Explique", "qwen/qwen3-coder:free")
    """
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }


def extract_openrouter_chat_content(response: Response) -> str:
    """Extract choices[0].message.content from an OpenRouter response.

    Example: extract_openrouter_chat_content(response)
    """
    try:
        payload = response.json()
    except ValueError:
        return ""

    choices = payload.get("choices") if isinstance(payload, Mapping) else None
    if not isinstance(choices, list) or not choices:
        return ""
    return extract_openrouter_message_content(choices[0])


def extract_openrouter_message_content(choice: object) -> str:
    """Extract text content from one OpenRouter choice object.

    Example: extract_openrouter_message_content({"message": {"content": "ok"}})
    """
    if not isinstance(choice, Mapping):
        return ""
    message = choice.get("message")
    if not isinstance(message, Mapping):
        return ""
    content = message.get("content")
    return content.strip() if isinstance(content, str) else ""


def build_status_error(status_code: int, model: str) -> str:
    """Create a user-safe OpenRouter status message.

    Example: build_status_error(429, "qwen/qwen3-coder:free")
    """
    if status_code == 429:
        return f"Erro na IA: limite gratuito atingido no OpenRouter para modelo {model!r}."
    if status_code == 402:
        return f"Erro na IA: saldo insuficiente no OpenRouter para modelo {model!r}."
    if status_code == 404:
        return f"Erro na IA: modelo {model!r} indisponivel no OpenRouter."
    return f"Erro na IA: status {status_code} no OpenRouter para modelo {model!r}."


def build_empty_response_error(model: str) -> str:
    """Create a user-safe message for empty OpenRouter choices.

    Example: build_empty_response_error("qwen/qwen3-coder:free")
    """
    return (
        f"Erro na IA: resposta vazia do OpenRouter para modelo {model!r}. "
        "Esperado choices[0].message.content."
    )


def log_openrouter_attempt(
    tool_name: str,
    model: str,
    status_code: int,
    used_fallback: bool,
) -> None:
    """Log only safe OpenRouter attempt metadata.

    Example: log_openrouter_attempt("youtube_analyzer", "qwen/qwen3-coder:free", 200, False)
    """
    logger.info(
        json.dumps(
            {
                "ferramenta": tool_name,
                "modelo": model,
                "status_http": status_code,
                "fallback_usado": used_fallback,
            },
            ensure_ascii=False,
        )
    )
