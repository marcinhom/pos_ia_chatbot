"""Testes simulados do fallback e diagnóstico (Tarefa 4: T5 a T10 e T18)."""

from __future__ import annotations

import pytest
import requests

from providers import (
    ANTHROPIC_URL,
    OPENAI_URL,
    OPENROUTER_URL,
    AllProvidersFailedError,
    NoAvailableProvidersError,
    call_with_fallback,
)


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self.body = body

    def json(self):
        return self.body


MESSAGES = [{"role": "user", "content": "Pergunta de teste"}]
PROVIDERS = [
    {"name": "openrouter", "model": "or-model"},
    {"name": "anthropic", "model": "claude-model"},
    {"name": "openai", "model": "gpt-model"},
]
KEYS = {
    "openrouter": "fake-or-key",
    "anthropic": "fake-anthropic-key",
    "openai": "fake-openai-key",
}


def success(provider, text="resposta"):
    if provider == "anthropic":
        return FakeResponse(200, {"content": [{"type": "text", "text": text}]})
    return FakeResponse(200, {"choices": [{"message": {"content": text}}]})


def test_t5_provedores_sem_chave_sao_ignorados_e_so_chave_disponivel_e_chamada():
    calls = []

    def fake_post(url, **kwargs):
        calls.append(url)
        return success("openai", "resposta OpenAI")

    result = call_with_fallback(
        PROVIDERS,
        {"openai": KEYS["openai"]},
        "instruções",
        MESSAGES,
        100,
        http_post=fake_post,
    )

    assert result.text == "resposta OpenAI"
    assert result.provider == "openai"
    assert calls == [OPENAI_URL]


def test_t6_sucesso_no_primeiro_provedor_nao_chama_o_proximo():
    calls = []

    def fake_post(url, **kwargs):
        calls.append(url)
        return success("openrouter", "primeira resposta")

    result = call_with_fallback(
        PROVIDERS,
        KEYS,
        "instruções",
        MESSAGES,
        100,
        http_post=fake_post,
    )

    assert result.text == "primeira resposta"
    assert result.provider == "openrouter"
    assert calls == [OPENROUTER_URL]


@pytest.mark.parametrize("status", [402, 429])
def test_t7_falha_de_credito_ou_limite_tenta_proximo_provedor(status):
    calls = []

    def fake_post(url, **kwargs):
        calls.append(url)
        if url == OPENROUTER_URL:
            return FakeResponse(status, {"error": {"message": "erro de cota"}})
        return success("anthropic", "resposta Anthropic")

    result = call_with_fallback(
        PROVIDERS[:2], KEYS, "instruções", MESSAGES, 100, http_post=fake_post
    )

    assert result.provider == "anthropic"
    assert result.text == "resposta Anthropic"
    assert calls == [OPENROUTER_URL, ANTHROPIC_URL]


@pytest.mark.parametrize("first_error", [requests.Timeout("secreto"), FakeResponse(503, {})])
def test_t8_timeout_ou_indisponibilidade_tenta_proximo_provedor(first_error):
    calls = []

    def fake_post(url, **kwargs):
        calls.append(url)
        if url == OPENROUTER_URL:
            if isinstance(first_error, Exception):
                raise first_error
            return first_error
        return success("anthropic")

    result = call_with_fallback(
        PROVIDERS[:2], KEYS, "instruções", MESSAGES, 100, http_post=fake_post
    )

    assert result.provider == "anthropic"
    assert calls == [OPENROUTER_URL, ANTHROPIC_URL]


def test_t9_falha_total_lista_provedores_e_motivos_sem_segredos():
    key = "sk" + "-or-v1-" + "this-is-secret"

    def fake_post(url, **kwargs):
        if url == OPENROUTER_URL:
            return FakeResponse(402, {"error": {"message": f"crédito insuficiente: {key}"}})
        if url == ANTHROPIC_URL:
            return FakeResponse(429, {"error": {"message": "too many requests"}})
        return FakeResponse(401, {"error": {"message": "unauthorized"}})

    with pytest.raises(AllProvidersFailedError) as exc:
        call_with_fallback(
            PROVIDERS,
            {**KEYS, "openrouter": key},
            "instruções",
            MESSAGES,
            100,
            http_post=fake_post,
        )

    message = str(exc.value)
    assert "OpenRouter" in message and "Anthropic" in message and "OpenAI" in message
    assert "saldo insuficiente" in message
    assert "limite de uso" in message
    assert "chave inválida" in message
    assert key not in message
    assert len(exc.value.failures) == 3


def test_t10_nenhuma_chave_pede_secret_correto_e_nao_faz_requisicao():
    calls = []

    with pytest.raises(NoAvailableProvidersError) as exc:
        call_with_fallback(
            PROVIDERS,
            {},
            "instruções",
            MESSAGES,
            100,
            http_post=lambda *args, **kwargs: calls.append(args),
        )

    assert "OPENROUTER_API_KEY" in str(exc.value)
    assert "ANTHROPIC_API_KEY" in str(exc.value)
    assert "OPENAI_API_KEY" in str(exc.value)
    assert calls == []


def test_t5_secret_de_provedor_fora_da_lista_nao_e_usado():
    calls = []

    with pytest.raises(NoAvailableProvidersError):
        call_with_fallback(
            PROVIDERS[:1],
            {"openai": KEYS["openai"]},
            "instruções",
            MESSAGES,
            100,
            http_post=lambda *args, **kwargs: calls.append(args),
        )

    assert calls == []
