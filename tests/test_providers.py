"""Testes simulados dos adaptadores HTTP (Tarefa 3: T3, T4 e T13)."""

from __future__ import annotations

from typing import Any

import pytest
import requests

from providers import (
    ANTHROPIC_URL,
    ANTHROPIC_VERSION,
    OPENAI_URL,
    OPENROUTER_URL,
    ProviderError,
    call_anthropic,
    call_openai,
    call_openrouter,
    call_provider,
)


class FakeResponse:
    def __init__(self, status_code: int, body: Any):
        self.status_code = status_code
        self.body = body

    def json(self):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body


MESSAGES = [{"role": "user", "content": "O que é um pipeline de dados?"}]
SYSTEM = "Explique de forma didática."


@pytest.mark.parametrize(
    ("provider", "adapter", "key", "model", "expected_url"),
    [
        ("openrouter", call_openrouter, "or-test-key", "vendor/model", OPENROUTER_URL),
        ("anthropic", call_anthropic, "anthropic-test-key", "claude-test", ANTHROPIC_URL),
        ("openai", call_openai, "openai-test-key", "gpt-test", OPENAI_URL),
    ],
)
def test_t3_cada_provedor_funciona_com_apenas_a_propria_chave(
    provider, adapter, key, model, expected_url
):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        if provider == "anthropic":
            return FakeResponse(200, {"content": [{"type": "text", "text": "Resposta Anthropic"}]})
        return FakeResponse(
            200,
            {"choices": [{"message": {"content": f"Resposta {provider}"}}]},
        )

    result = adapter(
        api_key=key,
        model=model,
        system_prompt=SYSTEM,
        messages=MESSAGES,
        max_output_tokens=321,
        http_post=fake_post,
    )

    expected = "Resposta Anthropic" if provider == "anthropic" else f"Resposta {provider}"
    assert result == expected
    assert captured["url"] == expected_url
    assert captured["timeout"] == 30
    assert captured["headers"]["Content-Type"] == "application/json"
    assert key in str(captured["headers"])
    assert "openrouter-test-key" not in str(captured["headers"]) if provider != "openrouter" else True
    assert "anthropic-test-key" not in str(captured["headers"]) if provider != "anthropic" else True
    assert "openai-test-key" not in str(captured["headers"]) if provider != "openai" else True


def test_t3_openrouter_traduz_modelo_instrucao_mensagens_e_limite():
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return FakeResponse(
            200,
            {"choices": [{"message": {"content": "  resposta OpenRouter  "}}]},
        )

    answer = call_provider(
        "openrouter",
        "only-openrouter-secret",
        "vendor/model",
        SYSTEM,
        MESSAGES,
        300,
        http_post=fake_post,
    )

    assert answer == "resposta OpenRouter"
    assert captured["url"] == OPENROUTER_URL
    assert captured["headers"]["Authorization"] == "Bearer only-openrouter-secret"
    assert captured["json"] == {
        "model": "vendor/model",
        "messages": [
            {"role": "system", "content": SYSTEM},
            *MESSAGES,
        ],
        "max_completion_tokens": 300,
    }


def test_t3_anthropic_usa_chave_e_formato_messages_da_propria_api():
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return FakeResponse(
            200,
            {"content": [
                {"type": "thinking", "thinking": "interno"},
                {"type": "text", "text": "Resposta "},
                {"type": "text", "text": "Anthropic"},
            ]},
        )

    answer = call_anthropic(
        api_key="only-anthropic-secret",
        model="claude-test",
        system_prompt=SYSTEM,
        messages=MESSAGES,
        max_output_tokens=100,
        http_post=fake_post,
    )

    assert answer == "Resposta Anthropic"
    assert captured["url"] == ANTHROPIC_URL
    assert captured["headers"]["x-api-key"] == "only-anthropic-secret"
    assert captured["headers"]["anthropic-version"] == ANTHROPIC_VERSION
    assert captured["json"] == {
        "model": "claude-test",
        "max_tokens": 100,
        "system": SYSTEM,
        "messages": MESSAGES,
    }


def test_t3_openai_usa_chave_propria_com_limite_atual_e_sem_armazenar_conversa():
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return FakeResponse(
            200,
            {"choices": [{"message": {"content": "Resposta OpenAI"}}]},
        )

    answer = call_openai(
        api_key="only-openai-secret",
        model="gpt-test",
        system_prompt=SYSTEM,
        messages=MESSAGES,
        max_output_tokens=512,
        http_post=fake_post,
    )

    assert answer == "Resposta OpenAI"
    assert captured["url"] == OPENAI_URL
    assert captured["headers"]["Authorization"] == "Bearer only-openai-secret"
    assert captured["json"] == {
        "model": "gpt-test",
        "messages": [
            {"role": "developer", "content": SYSTEM},
            *MESSAGES,
        ],
        "max_completion_tokens": 512,
        "store": False,
    }


@pytest.mark.parametrize(
    ("adapter", "key"),
    [
        (call_openrouter, "or-key"),
        (call_anthropic, "anthropic-key"),
        (call_openai, "openai-key"),
    ],
)
@pytest.mark.parametrize("limit", [1, 1024])
def test_t13_limite_de_tokens_e_enviado_sem_alteracao(adapter, key, limit):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(kwargs)
        if adapter is call_anthropic:
            return FakeResponse(200, {"content": [{"type": "text", "text": "ok"}]})
        return FakeResponse(200, {"choices": [{"message": {"content": "ok"}}]})

    adapter(
        api_key=key,
        model="modelo-teste",
        system_prompt=SYSTEM,
        messages=MESSAGES,
        max_output_tokens=limit,
        http_post=fake_post,
    )

    token_field = "max_tokens" if adapter is call_anthropic else "max_completion_tokens"
    assert captured["json"][token_field] == limit


@pytest.mark.parametrize(
    ("adapter", "key"),
    [
        (call_openrouter, ""),
        (call_anthropic, "  "),
        (call_openai, ""),
    ],
)
def test_adaptador_sem_chave_falha_sem_fazer_requisicao(adapter, key):
    calls = []

    with pytest.raises(ProviderError, match="chave"):
        adapter(
            api_key=key,
            model="modelo-teste",
            system_prompt=SYSTEM,
            messages=MESSAGES,
            max_output_tokens=32,
            http_post=lambda *args, **kwargs: calls.append((args, kwargs)),
        )

    assert calls == []


@pytest.mark.parametrize("limit", [0, 1025, True, 1.5])
def test_adaptador_rejeita_limite_fora_do_contrato_sem_rede(limit):
    calls = []
    with pytest.raises(ProviderError, match="limite"):
        call_openai(
            api_key="fake-key",
            model="modelo-teste",
            system_prompt=SYSTEM,
            messages=MESSAGES,
            max_output_tokens=limit,
            http_post=lambda *args, **kwargs: calls.append((args, kwargs)),
        )
    assert calls == []


def test_erro_http_mostra_motivo_sem_expor_chave():
    key = "sk-or-v1-very-secret-value"
    response = FakeResponse(
        402,
        {"error": {"message": f"Crédito insuficiente (token {key})"}},
    )

    with pytest.raises(ProviderError) as exc:
        call_openrouter(
            api_key=key,
            model="vendor/model",
            system_prompt=SYSTEM,
            messages=MESSAGES,
            max_output_tokens=64,
            http_post=lambda *args, **kwargs: response,
        )

    assert exc.value.status_code == 402
    assert "Crédito insuficiente" in str(exc.value)
    assert key not in str(exc.value)
    assert "[chave ocultada]" in str(exc.value)


def test_timeout_vira_erro_do_provedor_sem_detalhe_de_segredo():
    def fake_post(*args, **kwargs):
        raise requests.Timeout("secret should not be shown")

    with pytest.raises(ProviderError, match="tempo limite") as exc:
        call_openai(
            api_key="fake-openai-key",
            model="gpt-test",
            system_prompt=SYSTEM,
            messages=MESSAGES,
            max_output_tokens=64,
            http_post=fake_post,
        )

    assert "secret should not be shown" not in str(exc.value)


def test_resposta_malformada_vira_erro_claro():
    with pytest.raises(ProviderError, match="JSON inválido"):
        call_openai(
            api_key="fake-openai-key",
            model="gpt-test",
            system_prompt=SYSTEM,
            messages=MESSAGES,
            max_output_tokens=64,
            http_post=lambda *args, **kwargs: FakeResponse(200, ValueError("malformed")),
        )


def test_resposta_de_chat_com_blocos_de_texto_e_concatenada():
    response = FakeResponse(
        200,
        {"choices": [{"message": {"content": [
            {"type": "text", "text": "Olá "},
            {"type": "text", "text": "mundo"},
        ]}}]},
    )
    result = call_openrouter(
        "or-key",
        "vendor/model",
        "",
        MESSAGES,
        64,
        http_post=lambda *args, **kwargs: response,
    )
    assert result == "Olá mundo"

