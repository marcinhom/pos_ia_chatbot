"""Testes do validador de configuração (Tarefa 2): T1, T2 e T11.

Não usam rede, chaves reais nem o ``config/assistant.yaml`` do projeto
(exceto o teste que confirma que o exemplo versionado é válido).
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from config_loader import (
    CONTRASTE_MINIMO,
    AssistantConfig,
    ConfigError,
    load_config,
    main,
    razao_de_contraste,
    validate_config,
)

RAIZ_REPO = Path(__file__).resolve().parent.parent

# Configuração mínima válida: só campos obrigatórios e um provedor.
MINIMA = {
    "assistant": {
        "name": "Assistente de Teste",
        "description": "Descrição curta.",
        "instructions": "Responda em português do Brasil, de forma didática.",
    },
    "appearance": {"primary_color": "#2563EB", "background_color": "#F3F4F6"},
    "providers": [{"name": "openrouter", "model": "vendor/modelo"}],
}


def cfg_dict(**mudancas):
    """Cópia da configuração mínima, com seções substituídas."""
    d = copy.deepcopy(MINIMA)
    d.update(copy.deepcopy(mudancas))
    return d


def escrever(raiz: Path, dados) -> Path:
    arq = raiz / "config" / "assistant.yaml"
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(yaml.safe_dump(dados, allow_unicode=True), encoding="utf-8")
    return arq


def mensagens(exc: pytest.ExceptionInfo) -> str:
    return "\n".join(exc.value.errors)


# ---------------------------------------------------------------------------
# T1 — Configuração válida mínima
# ---------------------------------------------------------------------------


def test_t1_configuracao_minima_com_um_provedor_e_aceita_e_aplica_padroes(tmp_path):
    arq = escrever(tmp_path, MINIMA)

    cfg = load_config(arq, raiz=tmp_path)

    assert isinstance(cfg, AssistantConfig)
    assert cfg.name == "Assistente de Teste"
    assert [(p.name, p.model) for p in cfg.providers] == [("openrouter", "vendor/modelo")]
    # padrões da seção 4
    assert cfg.logo is None and cfg.logo_path is None
    assert cfg.logo_height_px == 64
    assert cfg.max_output_tokens == 1024
    assert cfg.example_questions == ()


def test_t1_validate_config_aceita_dicionario_direto():
    cfg = validate_config(MINIMA, raiz=RAIZ_REPO)
    assert cfg.primary_color == "#2563EB"


def test_t1_configuracao_completa_preserva_valores_e_ordem_dos_provedores(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "logo.png").write_bytes(b"png")
    dados = cfg_dict(
        providers=[
            {"name": "anthropic", "model": "modelo-a"},
            {"name": "openai", "model": "modelo-b"},
            {"name": "openrouter", "model": "vendor/modelo-c"},
        ],
        generation={"max_output_tokens": 300},
    )
    dados["assistant"].update(
        logo="assets/logo.png",
        logo_height_px=100,
        example_questions=["Pergunta 1?", "Pergunta 2?"],
    )

    cfg = validate_config(dados, raiz=tmp_path)

    assert [p.name for p in cfg.providers] == ["anthropic", "openai", "openrouter"]
    assert cfg.max_output_tokens == 300
    assert cfg.logo == "assets/logo.png"
    assert cfg.logo_height_px == 100
    assert cfg.example_questions == ("Pergunta 1?", "Pergunta 2?")


def test_t1_cores_sao_normalizadas_para_maiusculas():
    dados = cfg_dict(appearance={"primary_color": "#2563eb", "background_color": "#f3f4f6"})
    cfg = validate_config(dados, raiz=RAIZ_REPO)
    assert (cfg.primary_color, cfg.background_color) == ("#2563EB", "#F3F4F6")


def test_exemplo_versionado_do_repositorio_e_valido():
    cfg = load_config()  # config/assistant.yaml ao lado de config_loader.py
    assert cfg.providers and cfg.max_output_tokens <= 1024


def test_cli_retorna_zero_para_valido_e_um_para_invalido(tmp_path, capsys):
    ok = escrever(tmp_path, MINIMA)
    assert main([str(ok)]) == 0
    assert "Configuração válida" in capsys.readouterr().out

    ruim = tmp_path / "ruim.yaml"
    ruim.write_text("assistant: 1\n", encoding="utf-8")
    assert main([str(ruim)]) == 1
    assert "Configuração inválida" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# T2 — Configuração inválida: erro identifica o campo e bloqueia
# ---------------------------------------------------------------------------


def _sem(secao, campo):
    d = cfg_dict()
    del d[secao][campo]
    return d


@pytest.mark.parametrize(
    "dados, campo",
    [
        (_sem("assistant", "name"), "assistant.name"),
        (_sem("assistant", "description"), "assistant.description"),
        (_sem("assistant", "instructions"), "assistant.instructions"),
        (_sem("appearance", "primary_color"), "appearance.primary_color"),
        (_sem("appearance", "background_color"), "appearance.background_color"),
        ({k: v for k, v in MINIMA.items() if k != "providers"}, "providers"),
        ({k: v for k, v in MINIMA.items() if k != "assistant"}, "assistant"),
        ({k: v for k, v in MINIMA.items() if k != "appearance"}, "appearance"),
    ],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_t2_campo_obrigatorio_ausente_e_apontado(dados, campo):
    with pytest.raises(ConfigError) as exc:
        validate_config(dados, raiz=RAIZ_REPO)
    assert any(e.startswith(campo) for e in exc.value.errors), mensagens(exc)


@pytest.mark.parametrize(
    "secao, campo, valor",
    [
        ("assistant", "name", 123),
        ("assistant", "name", None),
        ("assistant", "name", "   "),
        ("assistant", "name", "x" * 61),
        ("assistant", "description", "x" * 181),
        ("assistant", "instructions", ["lista"]),
        ("assistant", "logo_height_px", "64"),
        ("assistant", "logo_height_px", True),
        ("assistant", "logo_height_px", 23),
        ("assistant", "logo_height_px", 161),
        ("assistant", "example_questions", "uma pergunta só"),
        ("appearance", "primary_color", 255),
        ("appearance", "primary_color", None),
    ],
)
def test_t2_tipo_ou_limite_incorreto_e_apontado(secao, campo, valor):
    dados = cfg_dict()
    dados[secao][campo] = valor
    with pytest.raises(ConfigError) as exc:
        validate_config(dados, raiz=RAIZ_REPO)
    assert any(e.startswith(f"{secao}.{campo}") for e in exc.value.errors), mensagens(exc)


@pytest.mark.parametrize("cor", ["#FFF", "2563EB", "#GGGGGG", "azul", "#2563EB0", "rgb(1,2,3)", ""])
def test_t2_cor_fora_do_formato_e_rejeitada_com_dica(cor):
    dados = cfg_dict(appearance={"primary_color": cor, "background_color": "#F3F4F6"})
    with pytest.raises(ConfigError) as exc:
        validate_config(dados, raiz=RAIZ_REPO)
    msg = mensagens(exc)
    assert "appearance.primary_color" in msg
    assert "#2563EB" in msg  # a dica mostra um exemplo de formato correto


def test_t2_cor_sem_aspas_no_yaml_vira_comentario_e_a_mensagem_explica(tmp_path):
    arq = tmp_path / "a.yaml"
    arq.write_text(
        "assistant:\n  name: A\n  description: B\n  instructions: C\n"
        "appearance:\n  primary_color: #2563EB\n  background_color: '#F3F4F6'\n"
        "providers:\n  - name: openai\n    model: m\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError) as exc:
        load_config(arq, raiz=tmp_path)
    assert "entre aspas" in mensagens(exc)


def test_t2_campos_desconhecidos_em_todos_os_niveis_sao_rejeitados():
    dados = cfg_dict(extra=1)
    dados["assistant"]["nmae"] = "x"
    dados["appearance"]["cor"] = "#000000"
    dados["providers"][0]["api_key"] = "nao-pode"
    dados["generation"] = {"max_output_tokens": 10, "temperature": 1}
    with pytest.raises(ConfigError) as exc:
        validate_config(dados, raiz=RAIZ_REPO)
    msg = mensagens(exc)
    for esperado in ("extra", "assistant.nmae", "appearance.cor",
                     "providers[1].api_key", "generation.temperature"):
        assert f"{esperado}: campo desconhecido" in msg
    assert "Você quis dizer 'name'" in msg  # sugestão para erro de digitação


def test_t2_chaves_de_api_nao_sao_campos_do_yaml():
    dados = cfg_dict(OPENROUTER_API_KEY="sk-fake")
    with pytest.raises(ConfigError) as exc:
        validate_config(dados, raiz=RAIZ_REPO)
    assert "OPENROUTER_API_KEY: campo desconhecido" in mensagens(exc)


@pytest.mark.parametrize(
    "providers, trecho",
    [
        ([], "providers: 0 provedores"),
        ([{"name": n, "model": "m"} for n in ("openai", "openai")], "já aparece em providers[1]"),
        (
            [{"name": n, "model": "m"} for n in ("openrouter", "anthropic", "openai")]
            + [{"name": "openai", "model": "m"}],
            "providers: 4 provedores",
        ),
        ([{"name": "gemini", "model": "m"}], "provedor 'gemini' não é suportado"),
        ([{"name": "OpenAI", "model": "m"}], "em minúsculas"),
        ([{"name": "openai"}], "providers[1].model: campo obrigatório ausente"),
        ([{"model": "m"}], "providers[1].name: campo obrigatório ausente"),
        ([{"name": "openai", "model": "  "}], "providers[1].model"),
        ([{"name": "openai", "model": 5}], "providers[1].model: esperado texto"),
        (["openai"], "providers[1]: esperado um bloco"),
        ("openai", "providers: esperado uma lista"),
    ],
)
def test_t2_regras_da_lista_de_provedores(providers, trecho):
    dados = cfg_dict(providers=providers)
    with pytest.raises(ConfigError) as exc:
        validate_config(dados, raiz=RAIZ_REPO)
    assert trecho in mensagens(exc)


@pytest.mark.parametrize("tokens", [0, -1, 1025, 100000, 1.5, "1024", True])
def test_t2_limite_de_tokens_fora_de_1_a_1024_bloqueia(tokens):
    dados = cfg_dict(generation={"max_output_tokens": tokens})
    with pytest.raises(ConfigError) as exc:
        validate_config(dados, raiz=RAIZ_REPO)
    assert "generation.max_output_tokens" in mensagens(exc)


@pytest.mark.parametrize("tokens", [1, 512, 1024])
def test_limite_de_tokens_nos_extremos_validos_e_aceito(tokens):
    cfg = validate_config(cfg_dict(generation={"max_output_tokens": tokens}), raiz=RAIZ_REPO)
    assert cfg.max_output_tokens == tokens


def test_t2_perguntas_sugeridas_limites():
    dados = cfg_dict()
    dados["assistant"]["example_questions"] = [f"P{i}?" for i in range(7)]
    with pytest.raises(ConfigError) as exc:
        validate_config(dados, raiz=RAIZ_REPO)
    assert "7 perguntas; o máximo é 6" in mensagens(exc)

    dados["assistant"]["example_questions"] = ["ok?", "", "x" * 121, 5]
    with pytest.raises(ConfigError) as exc:
        validate_config(dados, raiz=RAIZ_REPO)
    msg = mensagens(exc)
    assert "example_questions[2]" in msg and "example_questions[3]" in msg
    assert "example_questions[4]" in msg and "example_questions[1]" not in msg

    dados["assistant"]["example_questions"] = []
    assert validate_config(dados, raiz=RAIZ_REPO).example_questions == ()


def test_t2_todos_os_problemas_sao_reportados_de_uma_vez():
    dados = cfg_dict(providers=[], generation={"max_output_tokens": 5000})
    dados["assistant"]["name"] = ""
    dados["appearance"]["primary_color"] = "vermelho"
    with pytest.raises(ConfigError) as exc:
        validate_config(dados, raiz=RAIZ_REPO)
    assert len(exc.value.errors) == 4
    assert "4 problemas" in str(exc.value)


@pytest.mark.parametrize(
    "conteudo, trecho",
    [
        ("", "O arquivo está vazio"),
        ("- a\n- b\n", "blocos nomeados"),
        ("assistant: [\n", "YAML malformado"),
        ("assistant:\n  name: A\n  name: B\n", "aparece mais de uma vez"),
    ],
)
def test_t2_yaml_vazio_malformado_ou_com_chave_duplicada(tmp_path, conteudo, trecho):
    arq = tmp_path / "a.yaml"
    arq.write_text(conteudo, encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        load_config(arq, raiz=tmp_path)
    assert trecho in mensagens(exc)


def test_t2_arquivo_inexistente_e_pasta(tmp_path):
    with pytest.raises(ConfigError) as exc:
        load_config(tmp_path / "nao-existe.yaml", raiz=tmp_path)
    assert "não encontrado" in mensagens(exc)
    with pytest.raises(ConfigError) as exc:
        load_config(tmp_path, raiz=tmp_path)
    assert "é uma pasta" in mensagens(exc)


# ---------------------------------------------------------------------------
# T11 — Logo e cores
# ---------------------------------------------------------------------------


@pytest.fixture()
def repo(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "config").mkdir()
    for nome in ("logo.png", "foto.jpg", "foto.jpeg", "capa.webp", "MAIUSCULA.PNG",
                 "vetor.svg", "anim.gif", "doc.txt", "semextensao"):
        (tmp_path / "assets" / nome).write_bytes(b"x")
    (tmp_path / "config" / "fora.png").write_bytes(b"x")
    (tmp_path / "fora-da-raiz.png").write_bytes(b"x")
    (tmp_path / "assets" / "pasta.png").mkdir()
    return tmp_path


def com_logo(valor):
    d = cfg_dict()
    d["assistant"]["logo"] = valor
    return d


@pytest.mark.parametrize(
    "logo",
    ["assets/logo.png", "assets/foto.jpg", "assets/foto.jpeg", "assets/capa.webp",
     "assets/MAIUSCULA.PNG", "assets\\logo.png", "assets/./logo.png"],
)
def test_t11_logo_existente_em_assets_com_extensao_permitida_e_aceito(repo, logo):
    cfg = validate_config(com_logo(logo), raiz=repo)
    assert cfg.logo_path is not None and cfg.logo_path.is_file()
    assert cfg.logo_path.is_relative_to((repo / "assets").resolve())
    assert not Path(cfg.logo).is_absolute()


def test_t11_logo_null_ou_ausente_e_aceito(repo):
    assert validate_config(com_logo(None), raiz=repo).logo is None
    assert validate_config(cfg_dict(), raiz=repo).logo_path is None


def test_t11_logo_inexistente_e_rejeitado(repo):
    with pytest.raises(ConfigError) as exc:
        validate_config(com_logo("assets/nao-existe.png"), raiz=repo)
    assert "assistant.logo" in mensagens(exc) and "não encontrado" in mensagens(exc)


@pytest.mark.parametrize(
    "logo",
    ["config/fora.png", "fora-da-raiz.png", "../fora.png", "assets/../config/fora.png",
     "assets/../../etc/passwd", "assetsfake/logo.png", "/etc/passwd", "C:\\logo.png"],
)
def test_t11_logo_fora_de_assets_e_rejeitado(repo, logo):
    with pytest.raises(ConfigError) as exc:
        validate_config(com_logo(logo), raiz=repo)
    assert any(e.startswith("assistant.logo") for e in exc.value.errors), mensagens(exc)


def test_t11_logo_via_link_simbolico_para_fora_de_assets_e_rejeitado(repo):
    try:
        (repo / "assets" / "atalho.png").symlink_to(repo / "fora-da-raiz.png")
    except (OSError, NotImplementedError):
        pytest.skip("sistema sem suporte a links simbólicos")
    with pytest.raises(ConfigError) as exc:
        validate_config(com_logo("assets/atalho.png"), raiz=repo)
    assert "fora da pasta assets/" in mensagens(exc)


@pytest.mark.parametrize("logo", ["assets/vetor.svg", "assets/anim.gif", "assets/doc.txt",
                                  "assets/semextensao"])
def test_t11_logo_com_extensao_proibida_e_rejeitado(repo, logo):
    with pytest.raises(ConfigError) as exc:
        validate_config(com_logo(logo), raiz=repo)
    assert "extensão" in mensagens(exc) and "PNG, JPG, JPEG, WEBP" in mensagens(exc)


@pytest.mark.parametrize("logo", ["", "   ", 5, ["assets/logo.png"], True])
def test_t11_logo_vazio_ou_de_tipo_errado_e_rejeitado(repo, logo):
    with pytest.raises(ConfigError) as exc:
        validate_config(com_logo(logo), raiz=repo)
    assert "assistant.logo" in mensagens(exc)


def test_t11_logo_apontando_para_pasta_e_rejeitado(repo):
    with pytest.raises(ConfigError) as exc:
        validate_config(com_logo("assets/pasta.png"), raiz=repo)
    assert "não encontrado" in mensagens(exc)
    with pytest.raises(ConfigError):
        validate_config(com_logo("assets"), raiz=repo)


@pytest.mark.parametrize("cor", ["#2563EB", "#2563eb", "#000000", "#1E3A8A"])
def test_t11_cores_validas_de_seis_digitos_sao_aceitas(cor):
    dados = cfg_dict(appearance={"primary_color": cor, "background_color": "#F3F4F6"})
    assert validate_config(dados, raiz=RAIZ_REPO).primary_color == cor.upper()


@pytest.mark.parametrize("campo", ["primary_color", "background_color"])
@pytest.mark.parametrize("cor", ["#FFF", "2563EB", "#GGGGGG", "blue", "#12345", "#1234567"])
def test_t11_cor_fora_do_formato_e_rejeitada_em_ambos_os_campos(campo, cor):
    ap = {"primary_color": "#2563EB", "background_color": "#F3F4F6"}
    ap[campo] = cor
    with pytest.raises(ConfigError) as exc:
        validate_config(cfg_dict(appearance=ap), raiz=RAIZ_REPO)
    assert f"appearance.{campo}" in mensagens(exc)


def test_t11_contraste_insuficiente_e_rejeitado_com_mensagem_de_correcao():
    # amarelo claro com texto branco; fundo escuro com texto escuro
    ap = {"primary_color": "#FFFF00", "background_color": "#222222"}
    with pytest.raises(ConfigError) as exc:
        validate_config(cfg_dict(appearance=ap), raiz=RAIZ_REPO)
    msg = mensagens(exc)
    assert "primary_color: contraste" in msg and "mais escura" in msg
    assert "background_color: contraste" in msg and "mais clara" in msg
    assert f"{CONTRASTE_MINIMO}:1" in msg


def test_razao_de_contraste_confere_com_valores_conhecidos():
    assert razao_de_contraste("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert razao_de_contraste("#FFFFFF", "#FFFFFF") == pytest.approx(1.0)
    assert razao_de_contraste("#777777", "#FFFFFF") == pytest.approx(4.48, abs=0.01)


@pytest.mark.parametrize("logo", ["/etc/passwd", "/tmp/logo.png", "C:\\logo.png", "c:/logo.png"])
def test_t11_caminho_absoluto_recebe_mensagem_especifica(repo, logo):
    with pytest.raises(ConfigError) as exc:
        validate_config(com_logo(logo), raiz=repo)
    assert "caminho absoluto" in mensagens(exc)
