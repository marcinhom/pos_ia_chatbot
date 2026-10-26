"""Lógica do chat; não guarda histórico fora da sessão Gradio."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from typing import Any

from config_loader import AssistantConfig, load_config
from providers import ProviderError, ProviderResult, call_with_fallback


PROVIDER_SECRETS = {
    "openrouter": "OPENROUTER_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}
PROVIDER_LABELS = {
    "openrouter": "OpenRouter",
    "anthropic": "Anthropic",
    "openai": "OpenAI",
}


def api_keys_from_environment(environ: Mapping[str, str] | None = None) -> dict[str, str | None]:
    """Lê apenas os Secrets do Hugging Face; o YAML nunca contém chaves."""
    env = os.environ if environ is None else environ
    return {provider: env.get(secret) for provider, secret in PROVIDER_SECRETS.items()}


def _history_messages(history: Sequence[Any] | None) -> list[dict[str, str]]:
    """Converte o histórico de sessão Gradio para mensagens aceitas pelos provedores."""
    messages: list[dict[str, str]] = []
    if not isinstance(history, (list, tuple)):
        return messages

    for item in history:
        if isinstance(item, Mapping):
            role, content = item.get("role"), item.get("content")
            if role in ("user", "assistant") and isinstance(content, str) and content.strip():
                messages.append({"role": role, "content": content})
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            # Compatibilidade com o formato de pares usado por versões antigas do Gradio.
            user_message, assistant_message = item
            if isinstance(user_message, str) and user_message.strip():
                messages.append({"role": "user", "content": user_message})
            if isinstance(assistant_message, str) and assistant_message.strip():
                messages.append({"role": "assistant", "content": assistant_message})
    return messages


def answer_message(
    message: str,
    history: Sequence[Any] | None = None,
    *,
    config: AssistantConfig | None = None,
    api_keys: Mapping[str, str | None] | None = None,
    http_post=None,
) -> str:
    """Responde uma mensagem usando a sessão atual e a preferência do YAML."""
    if not isinstance(message, str) or not message.strip():
        return "Digite uma pergunta para começar."

    assistant_config = config or load_config()
    conversation = _history_messages(history)
    conversation.append({"role": "user", "content": message.strip()})

    try:
        result: ProviderResult = call_with_fallback(
            assistant_config.providers,
            api_keys_from_environment() if api_keys is None else api_keys,
            assistant_config.instructions,
            conversation,
            assistant_config.max_output_tokens,
            http_post=http_post,
        )
    except ProviderError as error:
        return f"⚠️ {error}"
    except Exception:
        # Evita mostrar dados internos, credenciais ou detalhes inesperados na interface.
        return "⚠️ Ocorreu um erro inesperado ao preparar sua resposta. Tente novamente."

    provider = PROVIDER_LABELS.get(result.provider, "provedor de IA")
    return f"{result.text}\n\n— *Respondido por {provider}*"
