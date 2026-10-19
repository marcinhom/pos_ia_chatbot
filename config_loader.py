"""Leitura e validação de ``config/assistant.yaml``.

Este módulo implementa o contrato descrito na seção 4 da SPEC. Ele:

* lê o YAML (recusando chaves duplicadas);
* valida campos, tipos, limites, referências de logo e contraste das cores;
* acumula **todos** os problemas encontrados, em português, indicando o campo
  e como corrigir;
* devolve uma configuração imutável (``AssistantConfig``) já com os padrões
  aplicados.

Uso na linha de comando (também serve para a CI):

    python config_loader.py                      # valida config/assistant.yaml
    python config_loader.py outro/arquivo.yaml   # valida outro arquivo

O código de saída é 0 quando a configuração é válida e 1 quando não é.

Este módulo nunca lê chaves de API: elas vêm de variáveis de ambiente
(Secrets do Space) e não fazem parte do YAML.
"""

from __future__ import annotations

import difflib
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Optional

import yaml

# ---------------------------------------------------------------------------
# Constantes do contrato
# ---------------------------------------------------------------------------

RAIZ_PADRAO = Path(__file__).resolve().parent
CAMINHO_PADRAO = Path("config") / "assistant.yaml"

PASTA_LOGO = "assets"
EXTENSOES_LOGO = (".png", ".jpg", ".jpeg", ".webp")

PROVEDORES_VALIDOS = ("openrouter", "anthropic", "openai")

NOME_MAX = 60
DESCRICAO_MAX = 180
PERGUNTA_MAX = 120
PERGUNTAS_MAX = 6
PROVEDORES_MIN, PROVEDORES_MAX = 1, 3
ALTURA_LOGO_MIN, ALTURA_LOGO_MAX, ALTURA_LOGO_PADRAO = 24, 160, 64
TOKENS_MIN, TOKENS_MAX = 1, 1024

# Contraste (WCAG 2.x, nível AA para texto normal).
# A interface usa texto BRANCO sobre a cor primária (cabeçalho e botões) e
# texto ESCURO sobre a cor de fundo do chat. Ambos precisam de, no mínimo,
# a razão abaixo.
CONTRASTE_MINIMO = 4.5
COR_TEXTO_SOBRE_PRIMARIA = "#FFFFFF"
COR_TEXTO_SOBRE_FUNDO = "#111827"

_REGEX_COR = re.compile(r"^#[0-9A-Fa-f]{6}$")

_CAMPOS_RAIZ = ("assistant", "appearance", "providers", "generation")
_CAMPOS_ASSISTANT = (
    "name",
    "description",
    "logo",
    "logo_height_px",
    "instructions",
    "example_questions",
)
_CAMPOS_APPEARANCE = ("primary_color", "background_color")
_CAMPOS_PROVEDOR = ("name", "model")
_CAMPOS_GENERATION = ("max_output_tokens",)

_AUSENTE = object()


# ---------------------------------------------------------------------------
# Tipos públicos
# ---------------------------------------------------------------------------


class ConfigError(Exception):
    """Configuração inválida. ``errors`` traz uma mensagem por problema."""

    def __init__(self, errors: list[str]):
        self.errors = list(errors)
        super().__init__(self._formatar())

    def _formatar(self) -> str:
        n = len(self.errors)
        titulo = f"Configuração inválida ({n} problema{'s' if n != 1 else ''}):"
        return "\n".join([titulo] + [f"  - {e}" for e in self.errors])


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    model: str


@dataclass(frozen=True)
class AssistantConfig:
    name: str
    description: str
    instructions: str
    example_questions: tuple[str, ...]
    logo: Optional[str]  # caminho relativo à raiz do repositório, ou None
    logo_path: Optional[Path]  # caminho absoluto resolvido, ou None
    logo_height_px: int
    primary_color: str
    background_color: str
    providers: tuple[ProviderConfig, ...]
    max_output_tokens: int


# ---------------------------------------------------------------------------
# Leitura do YAML (com detecção de chave duplicada)
# ---------------------------------------------------------------------------


class _LeitorEstrito(yaml.SafeLoader):
    """SafeLoader que recusa chaves repetidas no mesmo bloco."""


def _construir_mapa(loader: _LeitorEstrito, node: yaml.MappingNode, deep: bool = False):
    vistas: set[Any] = set()
    for chave_node, _ in node.value:
        chave = loader.construct_object(chave_node, deep=deep)
        try:
            repetida = chave in vistas
        except TypeError:  # chave não hashable: o próprio PyYAML reclama depois
            continue
        if repetida:
            raise yaml.constructor.ConstructorError(
                None,
                None,
                f"a chave '{chave}' aparece mais de uma vez no mesmo bloco",
                chave_node.start_mark,
            )
        vistas.add(chave)
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


_LeitorEstrito.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construir_mapa
)


def _ler_yaml(caminho: Path) -> Any:
    try:
        texto = caminho.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError(
            [f"Arquivo de configuração não encontrado: {caminho}. "
             "Crie o arquivo ou informe o caminho correto."]
        ) from None
    except IsADirectoryError:
        raise ConfigError([f"{caminho} é uma pasta, não um arquivo YAML."]) from None
    except UnicodeDecodeError:
        raise ConfigError(
            [f"{caminho} não está em UTF-8. Salve o arquivo com codificação UTF-8."]
        ) from None
    except OSError as exc:
        raise ConfigError([f"Não foi possível ler {caminho}: {exc.strerror or exc}."]) from None

    try:
        return yaml.load(texto, Loader=_LeitorEstrito)  # noqa: S506 - loader seguro
    except yaml.YAMLError as exc:
        marca = getattr(exc, "problem_mark", None)
        onde = f" (linha {marca.line + 1}, coluna {marca.column + 1})" if marca else ""
        problema = getattr(exc, "problem", None) or str(exc)
        raise ConfigError(
            [f"YAML malformado{onde}: {problema}. Verifique indentação, dois-pontos e aspas."]
        ) from None


# ---------------------------------------------------------------------------
# Utilitários de validação
# ---------------------------------------------------------------------------


def _tipo(valor: Any) -> str:
    if valor is None:
        return "vazio"
    if isinstance(valor, bool):
        return "verdadeiro/falso"
    if isinstance(valor, int):
        return "número inteiro"
    if isinstance(valor, float):
        return "número decimal"
    if isinstance(valor, str):
        return "texto"
    if isinstance(valor, list):
        return "lista"
    if isinstance(valor, dict):
        return "bloco com subcampos"
    return type(valor).__name__


def _sugestao(chave: Any, validas: tuple[str, ...]) -> str:
    parecidas = difflib.get_close_matches(str(chave), validas, n=1)
    return f" Você quis dizer '{parecidas[0]}'?" if parecidas else ""


def _checar_desconhecidos(
    mapa: dict, validos: tuple[str, ...], prefixo: str, erros: list[str]
) -> None:
    for chave in mapa:
        if chave not in validos:
            caminho = f"{prefixo}.{chave}" if prefixo else str(chave)
            erros.append(
                f"{caminho}: campo desconhecido. Remova-o ou corrija o nome."
                f"{_sugestao(chave, validos)}"
            )


def _secao(dados: dict, nome: str, erros: list[str], obrigatoria: bool) -> Optional[dict]:
    valor = dados.get(nome, _AUSENTE)
    if valor is _AUSENTE or valor is None:
        if obrigatoria:
            erros.append(f"{nome}: seção obrigatória ausente. Adicione o bloco '{nome}:'.")
        return None
    if not isinstance(valor, dict):
        erros.append(
            f"{nome}: esperado um bloco com subcampos, encontrado {_tipo(valor)}."
        )
        return None
    return valor


def _texto(
    valor: Any,
    caminho: str,
    erros: list[str],
    *,
    max_len: Optional[int] = None,
    dica_vazio: str = "Informe um texto.",
) -> Optional[str]:
    """Valida um texto obrigatório. Devolve o texto sem espaços nas pontas."""
    if valor is _AUSENTE:
        erros.append(f"{caminho}: campo obrigatório ausente. {dica_vazio}")
        return None
    if valor is None:
        erros.append(f"{caminho}: campo obrigatório está vazio. {dica_vazio}")
        return None
    if not isinstance(valor, str):
        erros.append(
            f"{caminho}: esperado texto, encontrado {_tipo(valor)}. "
            "Coloque o valor entre aspas."
        )
        return None
    limpo = valor.strip()
    if not limpo:
        erros.append(f"{caminho}: o texto não pode ficar em branco. {dica_vazio}")
        return None
    if max_len is not None and len(limpo) > max_len:
        erros.append(
            f"{caminho}: texto com {len(limpo)} caracteres; o máximo é {max_len}. "
            "Encurte o texto."
        )
        return None
    return limpo


def _inteiro(
    valor: Any, caminho: str, erros: list[str], minimo: int, maximo: int
) -> Optional[int]:
    if isinstance(valor, bool) or not isinstance(valor, int):
        erros.append(
            f"{caminho}: esperado número inteiro entre {minimo} e {maximo}, "
            f"encontrado {_tipo(valor)}."
        )
        return None
    if not minimo <= valor <= maximo:
        erros.append(
            f"{caminho}: valor {valor} fora do limite. Use um inteiro entre "
            f"{minimo} e {maximo}."
        )
        return None
    return valor


# ---------------------------------------------------------------------------
# Cores e contraste
# ---------------------------------------------------------------------------


def _luminancia(cor: str) -> float:
    def canal(par: str) -> float:
        c = int(par, 16) / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = cor[1:3], cor[3:5], cor[5:7]
    return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b)


def razao_de_contraste(cor_a: str, cor_b: str) -> float:
    """Razão de contraste WCAG entre duas cores ``#RRGGBB`` (de 1 a 21)."""
    la, lb = _luminancia(cor_a), _luminancia(cor_b)
    claro, escuro = max(la, lb), min(la, lb)
    return (claro + 0.05) / (escuro + 0.05)


def _cor(valor: Any, caminho: str, erros: list[str]) -> Optional[str]:
    if valor is _AUSENTE:
        erros.append(
            f'{caminho}: campo obrigatório ausente. Informe uma cor no formato "#RRGGBB".'
        )
        return None
    if valor is None:
        erros.append(
            f"{caminho}: campo obrigatório está vazio. No YAML, o símbolo # sem aspas "
            f'inicia um comentário; escreva a cor entre aspas, como "#2563EB".'
        )
        return None
    if not isinstance(valor, str):
        erros.append(
            f'{caminho}: esperado texto no formato "#RRGGBB", encontrado {_tipo(valor)}.'
        )
        return None
    limpo = valor.strip()
    if not _REGEX_COR.match(limpo):
        erros.append(
            f"{caminho}: '{limpo}' não é uma cor válida. Use exatamente seis dígitos "
            'hexadecimais com #, como "#2563EB".'
        )
        return None
    return limpo.upper()


def _checar_contraste(
    primaria: Optional[str], fundo: Optional[str], erros: list[str]
) -> None:
    if primaria is not None:
        r = razao_de_contraste(primaria, COR_TEXTO_SOBRE_PRIMARIA)
        if r < CONTRASTE_MINIMO:
            erros.append(
                f"appearance.primary_color: contraste {r:.2f}:1 com o texto branco do "
                f"cabeçalho e dos botões; o mínimo é {CONTRASTE_MINIMO}:1. "
                "Escolha uma cor mais escura."
            )
    if fundo is not None:
        r = razao_de_contraste(fundo, COR_TEXTO_SOBRE_FUNDO)
        if r < CONTRASTE_MINIMO:
            erros.append(
                f"appearance.background_color: contraste {r:.2f}:1 com o texto escuro "
                f"({COR_TEXTO_SOBRE_FUNDO}) do chat; o mínimo é {CONTRASTE_MINIMO}:1. "
                "Escolha uma cor mais clara."
            )


# ---------------------------------------------------------------------------
# Logo
# ---------------------------------------------------------------------------


def _logo(valor: Any, raiz: Path, erros: list[str]) -> tuple[Optional[str], Optional[Path]]:
    caminho = "assistant.logo"
    if valor is _AUSENTE or valor is None:
        return None, None
    if not isinstance(valor, str):
        erros.append(
            f"{caminho}: esperado caminho em texto ou null, encontrado {_tipo(valor)}."
        )
        return None, None
    bruto = valor.strip()
    if not bruto:
        erros.append(
            f"{caminho}: caminho em branco. Use null para não mostrar logo ou informe "
            f"um arquivo dentro de {PASTA_LOGO}/."
        )
        return None, None

    normalizado = bruto.replace("\\", "/")
    relativo = PurePosixPath(normalizado)
    if relativo.is_absolute() or re.match(r"^[A-Za-z]:", normalizado):
        erros.append(
            f"{caminho}: '{bruto}' é um caminho absoluto. Use um caminho relativo à "
            f"raiz do repositório, como {PASTA_LOGO}/logo.png."
        )
        return None, None

    raiz = raiz.resolve()
    pasta_logos = (raiz / PASTA_LOGO).resolve()
    alvo = (raiz / relativo).resolve()
    try:
        alvo.relative_to(pasta_logos)
    except ValueError:
        erros.append(
            f"{caminho}: '{bruto}' está fora da pasta {PASTA_LOGO}/. Mova a imagem "
            f"para {PASTA_LOGO}/ e ajuste o caminho."
        )
        return None, None

    if alvo.suffix.lower() not in EXTENSOES_LOGO:
        aceitas = ", ".join(e.lstrip(".").upper() for e in EXTENSOES_LOGO)
        erros.append(
            f"{caminho}: extensão '{alvo.suffix or '(nenhuma)'}' não é aceita. "
            f"Use um arquivo {aceitas}."
        )
        return None, None

    if not alvo.is_file():
        erros.append(
            f"{caminho}: arquivo '{bruto}' não encontrado. Adicione a imagem ao "
            "repositório ou corrija o caminho."
        )
        return None, None

    return alvo.relative_to(raiz).as_posix(), alvo


# ---------------------------------------------------------------------------
# Seções
# ---------------------------------------------------------------------------


def _validar_assistant(secao: dict, raiz: Path, erros: list[str]) -> dict:
    _checar_desconhecidos(secao, _CAMPOS_ASSISTANT, "assistant", erros)

    nome = _texto(
        secao.get("name", _AUSENTE), "assistant.name", erros,
        max_len=NOME_MAX, dica_vazio=f"Informe um texto de até {NOME_MAX} caracteres.",
    )
    descricao = _texto(
        secao.get("description", _AUSENTE), "assistant.description", erros,
        max_len=DESCRICAO_MAX,
        dica_vazio=f"Informe um texto de até {DESCRICAO_MAX} caracteres.",
    )
    instrucoes = _texto(
        secao.get("instructions", _AUSENTE), "assistant.instructions", erros,
        dica_vazio="Descreva o papel, o público, o estilo e os limites do assistente.",
    )

    logo, logo_path = _logo(secao.get("logo", _AUSENTE), raiz, erros)

    altura_bruta = secao.get("logo_height_px", _AUSENTE)
    if altura_bruta is _AUSENTE or altura_bruta is None:
        altura = ALTURA_LOGO_PADRAO
    else:
        altura = _inteiro(
            altura_bruta, "assistant.logo_height_px", erros, ALTURA_LOGO_MIN, ALTURA_LOGO_MAX
        )

    perguntas = _validar_perguntas(secao.get("example_questions", _AUSENTE), erros)

    return {
        "name": nome,
        "description": descricao,
        "instructions": instrucoes,
        "logo": logo,
        "logo_path": logo_path,
        "logo_height_px": altura,
        "example_questions": perguntas,
    }


def _validar_perguntas(valor: Any, erros: list[str]) -> Optional[tuple[str, ...]]:
    caminho = "assistant.example_questions"
    if valor is _AUSENTE or valor is None:
        return ()
    if not isinstance(valor, list):
        erros.append(f"{caminho}: esperado uma lista de textos, encontrado {_tipo(valor)}.")
        return None
    if len(valor) > PERGUNTAS_MAX:
        erros.append(
            f"{caminho}: {len(valor)} perguntas; o máximo é {PERGUNTAS_MAX}. "
            "Remova as que sobrarem."
        )
    itens: list[str] = []
    for i, item in enumerate(valor):
        t = _texto(
            item, f"{caminho}[{i + 1}]", erros,
            max_len=PERGUNTA_MAX,
            dica_vazio="Escreva a pergunta ou remova a linha.",
        )
        if t is not None:
            itens.append(t)
    return tuple(itens)


def _validar_appearance(secao: dict, erros: list[str]) -> dict:
    _checar_desconhecidos(secao, _CAMPOS_APPEARANCE, "appearance", erros)
    primaria = _cor(secao.get("primary_color", _AUSENTE), "appearance.primary_color", erros)
    fundo = _cor(secao.get("background_color", _AUSENTE), "appearance.background_color", erros)
    _checar_contraste(primaria, fundo, erros)
    return {"primary_color": primaria, "background_color": fundo}


def _validar_providers(valor: Any, erros: list[str]) -> Optional[tuple[ProviderConfig, ...]]:
    if valor is _AUSENTE or valor is None:
        erros.append(
            "providers: lista obrigatória ausente. Informe de 1 a 3 provedores "
            f"({', '.join(PROVEDORES_VALIDOS)})."
        )
        return None
    if not isinstance(valor, list):
        erros.append(f"providers: esperado uma lista, encontrado {_tipo(valor)}.")
        return None
    if not PROVEDORES_MIN <= len(valor) <= PROVEDORES_MAX:
        erros.append(
            f"providers: {len(valor)} provedores; informe de {PROVEDORES_MIN} a "
            f"{PROVEDORES_MAX}."
        )

    vistos: dict[str, int] = {}
    itens: list[ProviderConfig] = []
    for i, item in enumerate(valor, start=1):
        caminho = f"providers[{i}]"
        if not isinstance(item, dict):
            erros.append(
                f"{caminho}: esperado um bloco com 'name' e 'model', encontrado {_tipo(item)}."
            )
            continue
        _checar_desconhecidos(item, _CAMPOS_PROVEDOR, caminho, erros)

        nome_bruto = item.get("name", _AUSENTE)
        nome: Optional[str] = None
        if nome_bruto is _AUSENTE or nome_bruto is None:
            erros.append(
                f"{caminho}.name: campo obrigatório "
                f"{'ausente' if nome_bruto is _AUSENTE else 'está vazio'}. "
                f"Use um de: {', '.join(PROVEDORES_VALIDOS)}."
            )
        elif not isinstance(nome_bruto, str):
            erros.append(
                f"{caminho}.name: esperado texto, encontrado {_tipo(nome_bruto)}. "
                f"Use um de: {', '.join(PROVEDORES_VALIDOS)}."
            )
        elif nome_bruto.strip() not in PROVEDORES_VALIDOS:
            erros.append(
                f"{caminho}.name: provedor '{nome_bruto.strip()}' não é suportado. "
                f"Use um de: {', '.join(PROVEDORES_VALIDOS)} (em minúsculas)."
                f"{_sugestao(nome_bruto.strip().lower(), PROVEDORES_VALIDOS)}"
            )
        else:
            nome = nome_bruto.strip()
            if nome in vistos:
                erros.append(
                    f"{caminho}.name: o provedor '{nome}' já aparece em "
                    f"providers[{vistos[nome]}]. Não repita provedores."
                )
                nome = None
            else:
                vistos[nome] = i

        modelo = _texto(
            item.get("model", _AUSENTE), f"{caminho}.model", erros,
            dica_vazio="Informe o identificador exato do modelo aceito pelo provedor.",
        )
        if nome is not None and modelo is not None:
            itens.append(ProviderConfig(name=nome, model=modelo))
    return tuple(itens)


def _validar_generation(secao: Optional[dict], erros: list[str]) -> Optional[int]:
    if secao is None:
        return TOKENS_MAX
    _checar_desconhecidos(secao, _CAMPOS_GENERATION, "generation", erros)
    bruto = secao.get("max_output_tokens", _AUSENTE)
    if bruto is _AUSENTE or bruto is None:
        return TOKENS_MAX
    return _inteiro(bruto, "generation.max_output_tokens", erros, TOKENS_MIN, TOKENS_MAX)


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def validate_config(dados: Any, raiz: Path | str = RAIZ_PADRAO) -> AssistantConfig:
    """Valida um dicionário já lido do YAML e devolve a configuração.

    Levanta ``ConfigError`` com todos os problemas encontrados.
    """
    raiz = Path(raiz)
    erros: list[str] = []

    if dados is None:
        raise ConfigError(
            ["O arquivo está vazio. Preencha as seções assistant, appearance e providers."]
        )
    if not isinstance(dados, dict):
        raise ConfigError(
            ["O arquivo deve conter blocos nomeados (assistant, appearance, providers, "
             f"generation), mas o conteúdo é do tipo {_tipo(dados)}."]
        )

    _checar_desconhecidos(dados, _CAMPOS_RAIZ, "", erros)

    sec_assistant = _secao(dados, "assistant", erros, obrigatoria=True)
    sec_appearance = _secao(dados, "appearance", erros, obrigatoria=True)
    sec_generation = _secao(dados, "generation", erros, obrigatoria=False)

    a = _validar_assistant(sec_assistant, raiz, erros) if sec_assistant is not None else None
    ap = _validar_appearance(sec_appearance, erros) if sec_appearance is not None else None
    provedores = _validar_providers(dados.get("providers", _AUSENTE), erros)
    tokens = _validar_generation(sec_generation, erros)

    if erros:
        raise ConfigError(erros)

    assert a is not None and ap is not None and provedores is not None and tokens is not None
    return AssistantConfig(
        name=a["name"],
        description=a["description"],
        instructions=a["instructions"],
        example_questions=a["example_questions"],
        logo=a["logo"],
        logo_path=a["logo_path"],
        logo_height_px=a["logo_height_px"],
        primary_color=ap["primary_color"],
        background_color=ap["background_color"],
        providers=provedores,
        max_output_tokens=tokens,
    )


def load_config(
    caminho: Path | str | None = None, raiz: Path | str | None = None
) -> AssistantConfig:
    """Lê e valida o YAML do assistente.

    ``raiz`` é a raiz do repositório (usada para resolver ``assistant.logo``).
    Sem argumentos, lê ``config/assistant.yaml`` ao lado deste módulo.
    """
    raiz_path = Path(raiz) if raiz is not None else RAIZ_PADRAO
    arquivo = Path(caminho) if caminho is not None else raiz_path / CAMINHO_PADRAO
    return validate_config(_ler_yaml(arquivo), raiz_path)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) > 1:
        print("Uso: python config_loader.py [caminho/do/assistant.yaml]", file=sys.stderr)
        return 2
    try:
        cfg = load_config(args[0] if args else None)
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 1
    ordem = " -> ".join(f"{p.name} ({p.model})" for p in cfg.providers)
    print(f"Configuração válida: '{cfg.name}'")
    print(f"  provedores (ordem de preferência): {ordem}")
    print(f"  limite de resposta: {cfg.max_output_tokens} tokens")
    print(f"  logo: {cfg.logo or 'nenhuma'}")
    print(f"  perguntas sugeridas: {len(cfg.example_questions)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
