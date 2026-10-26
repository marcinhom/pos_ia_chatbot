"""Testes de interface e integração lógica do chat (Tarefa 5: T12 e T16)."""

from __future__ import annotations

import json
from dataclasses import replace

import gradio as gr

from app import create_demo
from chat import answer_message, api_keys_from_environment
from config_loader import ProviderConfig, load_config


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self.body = body

    def json(self):
        return self.body


def test_chat_lê_secrets_com_nomes_exatos_sem_aceitar_chaves_do_yaml():
    keys = api_keys_from_environment(
        {
            "OPENROUTER_API_KEY": "fake-openrouter",
            "ANTHROPIC_API_KEY": "fake-anthropic",
            "OPENAI_API_KEY": "fake-openai",
            "OUTRA_CHAVE": "ignorar",
        }
    )

    assert keys == {
        "openrouter": "fake-openrouter",
        "anthropic": "fake-anthropic",
        "openai": "fake-openai",
    }


def test_chat_envia_pergunta_e_historico_da_sessao_e_indica_provedor():
    config = load_config()
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return FakeResponse(200, {"choices": [{"message": {"content": "Uma resposta didática."}}]})

    answer = answer_message(
        "E o que é um data lake?",
        [
            {"role": "user", "content": "O que é um pipeline?"},
            {"role": "assistant", "content": "É um fluxo de processamento."},
        ],
        config=config,
        api_keys={"openrouter": "fake-key"},
        http_post=fake_post,
    )

    assert answer.startswith("Uma resposta didática.")
    assert "OpenRouter" in answer
    assert [m["role"] for m in captured["json"]["messages"]] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert captured["json"]["messages"][-1]["content"] == "E o que é um data lake?"
    assert captured["json"]["messages"][0]["content"] == config.instructions
    assert captured["json"]["max_completion_tokens"] == config.max_output_tokens


def test_chat_sem_secret_mostra_instrucao_em_portugues_sem_chamar_provedor():
    calls = []
    answer = answer_message(
        "Minha pergunta",
        config=load_config(),
        api_keys={},
        http_post=lambda *args, **kwargs: calls.append(args),
    )

    assert "Nenhum provedor configurado tem chave" in answer
    assert "OPENROUTER_API_KEY" in answer
    assert calls == []


def test_chat_retorna_diagnostico_de_falha_total_sem_expor_secret():
    config = load_config()
    config = replace(
        config,
        providers=(
            ProviderConfig("openrouter", "or-model"),
            ProviderConfig("openai", "gpt-model"),
        ),
    )

    def fake_post(url, **kwargs):
        return FakeResponse(402 if "openrouter" in url else 429, {"error": {"message": "falha simulada"}})

    answer = answer_message(
        "Pergunta",
        config=config,
        api_keys={"openrouter": "fake-key-one", "openai": "fake-key-two"},
        http_post=fake_post,
    )

    assert "OpenRouter" in answer and "OpenAI" in answer
    assert "saldo insuficiente" in answer and "limite de uso" in answer
    assert "fake-key" not in answer


def test_t12_perguntas_configuradas_aparecem_como_exemplos_clicaveis():
    config = load_config()
    demo = create_demo(config)
    datasets = [c for c in demo.blocks.values() if isinstance(c, gr.Dataset)]

    assert isinstance(demo, gr.Blocks)
    assert len(datasets) == 1
    assert datasets[0].samples == [
        ["O que é um pipeline de dados?"],
        ["Qual é a diferença entre IA e aprendizado de máquina?"],
    ]


def test_t12_lista_vazia_nao_cria_perguntas_sugeridas():
    demo = create_demo(replace(load_config(), example_questions=()))
    datasets = [c for c in demo.blocks.values() if isinstance(c, gr.Dataset)]

    assert datasets == []


def test_t16_cabecalho_placeholders_e_acoes_estao_em_portugues():
    demo = create_demo()
    serializado = json.dumps(demo.config, ensure_ascii=False, default=str)

    assert "Assistente de Engenharia de Dados e IA" in serializado
    assert "Escreva sua pergunta e pressione Enviar" in serializado
    assert "Enviar" in serializado
    assert "Conversa" in serializado
