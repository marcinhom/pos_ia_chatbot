"""Testes de segurança para garantir que segredos não apareçam em erros."""

from providers import _redact


def test_chaves_dos_provedores_sao_ocultadas_em_mensagens_de_erro():
    openrouter_key = "sk" + "-or-v1-" + "A1b2C3d4E5f6G7h8I9j0"
    anthropic_key = "sk" + "-ant-api03-" + "A1b2C3d4E5f6G7h8I9j0"
    openai_key = "sk" + "-proj-" + "A1b2C3d4E5f6G7h8I9j0"

    for key in (openrouter_key, anthropic_key, openai_key):
        message = _redact(f"Falha de autenticação: {key}", "")
        assert key not in message
        assert "[chave ocultada]" in message


def test_cabecalho_bearer_e_ocultado_mesmo_sem_conhecer_a_chave():
    message = _redact("Falha: Bearer valor-falso-123456789", "")

    assert "valor-falso-123456789" not in message
    assert "Bearer [chave ocultada]" in message
