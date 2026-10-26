"""Adaptadores HTTP e fallback para OpenRouter, Anthropic e OpenAI."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import requests


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_TIMEOUT_SECONDS = 30
MAX_OUTPUT_TOKENS = 1024

HttpPost = Callable[..., Any]


class ProviderError(Exception):
    """Falha de chamada a um provedor, sem incluir cabeçalhos ou chaves."""

    def __init__(self, provider: str, message: str, status_code: int | None = None):
        self.provider = provider
        self.status_code = status_code
        self.message = message
        super().__init__(message)


def _validate_inputs(
    provider: str,
    api_key: str,
    model: str,
    messages: Sequence[Mapping[str, Any]],
    max_output_tokens: int,
    system_prompt: str,
    timeout: int,
) -> tuple[str, list[dict[str, str]], str]:
    key = api_key.strip() if isinstance(api_key, str) else ""
    if not key:
        raise ProviderError(provider, "A chave deste provedor está ausente.")
    if not isinstance(model, str) or not model.strip():
        raise ProviderError(provider, "O identificador do modelo está vazio.")
    if isinstance(max_output_tokens, bool) or not isinstance(max_output_tokens, int):
        raise ProviderError(provider, "O limite de resposta precisa ser um número inteiro.")
    if not 1 <= max_output_tokens <= MAX_OUTPUT_TOKENS:
        raise ProviderError(
            provider,
            f"O limite de resposta precisa estar entre 1 e {MAX_OUTPUT_TOKENS} tokens.",
        )
    if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout < 1:
        raise ProviderError(provider, "O tempo limite precisa ser um inteiro positivo.")
    if not isinstance(system_prompt, str):
        raise ProviderError(provider, "As instruções do assistente precisam ser texto.")
    if not isinstance(messages, (list, tuple)):
        raise ProviderError(provider, "As mensagens precisam ser uma lista.")

    normalized: list[dict[str, str]] = []
    for index, message in enumerate(messages, start=1):
        if not isinstance(message, Mapping):
            raise ProviderError(provider, f"A mensagem {index} está em formato inválido.")
        role = message.get("role")
        content = message.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str):
            raise ProviderError(
                provider,
                f"A mensagem {index} deve ter papel user ou assistant e conteúdo em texto.",
            )
        normalized.append({"role": role, "content": content})
    if not normalized:
        raise ProviderError(provider, "Envie pelo menos uma mensagem para o assistente.")
    return key, normalized, model.strip()


def _redact(text: str, api_key: str) -> str:
    if api_key:
        text = text.replace(api_key, "[chave ocultada]")
    text = re.sub(r"(?i)\bBearer\s+\S+", "Bearer [chave ocultada]", text)
    text = re.sub(r"\bsk-(?:or-v1-|ant-api\d{2}-)?[A-Za-z0-9_-]{8,}\b", "[chave ocultada]", text)
    return text[:500]


def _response_json(response: Any) -> dict[str, Any] | None:
    try:
        data = response.json()
    except (ValueError, AttributeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _error_detail(response: Any, api_key: str) -> str:
    data = _response_json(response)
    if data is None:
        return "O provedor retornou uma resposta de erro sem detalhes."
    error = data.get("error")
    if isinstance(error, Mapping):
        detail = error.get("message") or error.get("detail") or error.get("type")
    elif isinstance(error, str):
        detail = error
    else:
        detail = data.get("message") or data.get("detail")
    if not isinstance(detail, str) or not detail.strip():
        return "O provedor retornou uma resposta de erro sem detalhes."
    return _redact(detail.strip(), api_key)


def _post_json(
    provider: str,
    url: str,
    api_key: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: int,
    http_post: HttpPost | None,
) -> dict[str, Any]:
    post = http_post or requests.post
    try:
        response = post(
            url,
            headers=headers,
            json=payload,
            timeout=timeout,
        )
    except requests.Timeout:
        raise ProviderError(provider, "A chamada excedeu o tempo limite.") from None
    except requests.ConnectionError:
        raise ProviderError(provider, "Não foi possível conectar ao provedor.") from None
    except requests.RequestException:
        raise ProviderError(provider, "Falha de comunicação com o provedor.") from None

    status = getattr(response, "status_code", None)
    if not isinstance(status, int):
        raise ProviderError(provider, "O provedor retornou uma resposta inválida.")
    if not 200 <= status < 300:
        detail = _error_detail(response, api_key)
        raise ProviderError(provider, f"HTTP {status}: {detail}", status_code=status)

    data = _response_json(response)
    if data is None:
        raise ProviderError(provider, "O provedor retornou JSON inválido.")
    return data


def _chat_completion_text(data: dict[str, Any], provider: str) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
        raise ProviderError(provider, "A resposta não contém uma escolha de texto.")
    message = choices[0].get("message")
    if not isinstance(message, Mapping):
        raise ProviderError(provider, "A resposta não contém a mensagem do assistente.")
    content = message.get("content")
    if isinstance(content, str):
        result = content.strip()
    elif isinstance(content, list):
        result = "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, Mapping) and isinstance(block.get("text"), str)
        ).strip()
    else:
        result = ""
    if not result:
        raise ProviderError(provider, "A resposta do provedor não contém texto.")
    return result


def _anthropic_text(data: dict[str, Any]) -> str:
    content = data.get("content")
    if not isinstance(content, list):
        raise ProviderError("anthropic", "A resposta não contém blocos de conteúdo.")
    result = "".join(
        block.get("text", "")
        for block in content
        if isinstance(block, Mapping)
        and block.get("type") == "text"
        and isinstance(block.get("text"), str)
    ).strip()
    if not result:
        raise ProviderError("anthropic", "A resposta do provedor não contém texto.")
    return result


def call_openrouter(
    api_key: str,
    model: str,
    system_prompt: str,
    messages: Sequence[Mapping[str, Any]],
    max_output_tokens: int,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    http_post: HttpPost | None = None,
) -> str:
    """Envia uma conversa diretamente ao endpoint OpenRouter."""
    key, normalized, model_name = _validate_inputs(
        "openrouter", api_key, model, messages, max_output_tokens, system_prompt, timeout
    )
    request_messages: list[dict[str, str]] = []
    if system_prompt.strip():
        request_messages.append({"role": "system", "content": system_prompt})
    request_messages.extend(normalized)
    data = _post_json(
        "openrouter",
        OPENROUTER_URL,
        key,
        {
            "model": model_name,
            "messages": request_messages,
            "max_completion_tokens": max_output_tokens,
        },
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        timeout,
        http_post,
    )
    return _chat_completion_text(data, "openrouter")


def call_anthropic(
    api_key: str,
    model: str,
    system_prompt: str,
    messages: Sequence[Mapping[str, Any]],
    max_output_tokens: int,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    http_post: HttpPost | None = None,
) -> str:
    """Envia uma conversa diretamente à Messages API da Anthropic."""
    key, normalized, model_name = _validate_inputs(
        "anthropic", api_key, model, messages, max_output_tokens, system_prompt, timeout
    )
    payload: dict[str, Any] = {
        "model": model_name,
        "max_tokens": max_output_tokens,
        "messages": normalized,
    }
    if system_prompt.strip():
        payload["system"] = system_prompt
    data = _post_json(
        "anthropic",
        ANTHROPIC_URL,
        key,
        payload,
        {
            "x-api-key": key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        },
        timeout,
        http_post,
    )
    return _anthropic_text(data)


def call_openai(
    api_key: str,
    model: str,
    system_prompt: str,
    messages: Sequence[Mapping[str, Any]],
    max_output_tokens: int,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    http_post: HttpPost | None = None,
) -> str:
    """Envia uma conversa diretamente à Chat Completions API da OpenAI."""
    key, normalized, model_name = _validate_inputs(
        "openai", api_key, model, messages, max_output_tokens, system_prompt, timeout
    )
    request_messages: list[dict[str, str]] = []
    if system_prompt.strip():
        request_messages.append({"role": "developer", "content": system_prompt})
    request_messages.extend(normalized)
    data = _post_json(
        "openai",
        OPENAI_URL,
        key,
        {
            "model": model_name,
            "messages": request_messages,
            "max_completion_tokens": max_output_tokens,
            "store": False,
        },
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        timeout,
        http_post,
    )
    return _chat_completion_text(data, "openai")


_ADAPTERS: dict[str, Callable[..., str]] = {
    "openrouter": call_openrouter,
    "anthropic": call_anthropic,
    "openai": call_openai,
}


def call_provider(
    provider: str,
    api_key: str,
    model: str,
    system_prompt: str,
    messages: Sequence[Mapping[str, Any]],
    max_output_tokens: int,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    http_post: HttpPost | None = None,
) -> str:
    """Seleciona um adaptador pelo nome; não executa fallback."""
    adapter = _ADAPTERS.get(provider)
    if adapter is None:
        raise ProviderError(provider, f"Provedor não suportado: {provider}.")
    return adapter(
        api_key=api_key,
        model=model,
        system_prompt=system_prompt,
        messages=messages,
        max_output_tokens=max_output_tokens,
        timeout=timeout,
        http_post=http_post,
    )


@dataclass(frozen=True)
class ProviderResult:
    """Resposta do provedor que funcionou; permite à interface informar a origem."""

    text: str
    provider: str


class NoAvailableProvidersError(ProviderError):
    """Nenhum dos provedores configurados tem uma chave disponível."""

    def __init__(self, required_secrets: Sequence[str]):
        self.required_secrets = tuple(required_secrets)
        if self.required_secrets:
            names = ", ".join(self.required_secrets)
            message = (
                "Nenhum provedor configurado tem chave. Adicione pelo menos um destes "
                f"Secrets nas configurações do Hugging Face Space: {names}."
            )
        else:
            message = "Nenhum provedor está configurado para uso."
        super().__init__("nenhum", message)


@dataclass(frozen=True)
class ProviderFailure:
    provider: str
    reason: str


class AllProvidersFailedError(ProviderError):
    """Todos os provedores com chave falharam; contém motivos já sanitizados."""

    def __init__(self, failures: Sequence[ProviderFailure]):
        self.failures = tuple(failures)
        details = "\n".join(f"- {_provider_label(f.provider)}: {f.reason}" for f in self.failures)
        super().__init__("todos", "Não foi possível obter uma resposta. Falhas encontradas:\n" + details)


_PROVIDER_LABELS = {
    "openrouter": "OpenRouter",
    "anthropic": "Anthropic",
    "openai": "OpenAI",
}
_PROVIDER_SECRETS = {
    "openrouter": "OPENROUTER_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}


def _provider_label(provider: str) -> str:
    return _PROVIDER_LABELS.get(provider, provider)


def _provider_value(item: Any, field: str) -> Any:
    if isinstance(item, Mapping):
        return item.get(field)
    return getattr(item, field, None)


def _failure_reason(error: ProviderError) -> str:
    """Traduz os erros mais comuns e mantém detalhes úteis sem revelar credenciais."""
    status = error.status_code
    detail = _redact(error.message, "")
    if status == 401:
        return "chave inválida ou sem autenticação (HTTP 401)."
    if status == 402:
        return "sem crédito ou saldo insuficiente (HTTP 402)."
    if status == 403:
        return "acesso negado para esta conta, modelo ou operação (HTTP 403)."
    if status == 429:
        return "limite de uso atingido; tente novamente mais tarde (HTTP 429)."
    if status is not None and status >= 500:
        return f"provedor temporariamente indisponível (HTTP {status})."
    if status is not None:
        return f"o provedor recusou a solicitação (HTTP {status}): {detail}"
    return detail


def call_with_fallback(
    providers: Sequence[Any],
    api_keys: Mapping[str, str | None],
    system_prompt: str,
    messages: Sequence[Mapping[str, Any]],
    max_output_tokens: int,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    http_post: HttpPost | None = None,
) -> ProviderResult:
    """Tenta, na ordem configurada, somente provedores com a própria chave.

    ``providers`` aceita os objetos ProviderConfig ou dicionários do YAML.
    ``api_keys`` mapeia os nomes de provedor a valores vindos dos Secrets.
    """
    eligible: list[tuple[str, str, str]] = []
    required_secrets: list[str] = []
    for item in providers:
        name = _provider_value(item, "name")
        model = _provider_value(item, "model")
        if not isinstance(name, str):
            continue
        secret_name = _PROVIDER_SECRETS.get(name)
        key = api_keys.get(name)
        if not isinstance(key, str) or not key.strip():
            if secret_name and secret_name not in required_secrets:
                required_secrets.append(secret_name)
            continue
        if isinstance(model, str) and model.strip():
            eligible.append((name, key, model))

    if not eligible:
        raise NoAvailableProvidersError(required_secrets)

    failures: list[ProviderFailure] = []
    for name, key, model in eligible:
        try:
            answer = call_provider(
                name,
                key,
                model,
                system_prompt,
                messages,
                max_output_tokens,
                timeout=timeout,
                http_post=http_post,
            )
            return ProviderResult(text=answer, provider=name)
        except ProviderError as error:
            failures.append(ProviderFailure(name, _failure_reason(error)))

    raise AllProvidersFailedError(failures)


