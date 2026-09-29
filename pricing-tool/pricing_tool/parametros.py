"""Parametros de entrada da simulacao e o preset padrao."""

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from . import calendario

TIPO_LISTA = "lista"
TIPO_EXPRESSAO = "expressao"

VARIAVEIS_COMERCIAIS = ("n",)
VARIAVEIS_AQUISICAO = ("n", "c")
VARIAVEIS_ESCOPO = ("t",)
VARIAVEIS_CUSTO = ("n", "a")

MESES_ABREVIADOS = (
    "jan", "fev", "mar", "abr", "mai", "jun",
    "jul", "ago", "set", "out", "nov", "dez",
)


def mes_atual() -> str:
    agora = datetime.now()  # noqa: DTZ005 — o mes inicial segue o relogio local
    return f"{agora.year:04d}-{agora.month:02d}"


def agora_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class PontoAquisicao:
    mes: str
    clientes_adquiridos: int = 0


@dataclass
class FuncaoAquisicao:
    """Clientes novos por mes, por lista explicita ou por expressao em `n` e `c`."""

    tipo: str = TIPO_EXPRESSAO
    expressao: str = "1 * c"
    valores: list[PontoAquisicao] = field(default_factory=list)


@dataclass
class PontoEscopo:
    mes_desde_ativacao: int
    escopo_percentual: float = 0.0


@dataclass
class CurvaEscopo:
    """Fracao do escopo pleno em execucao ao longo da vida do cliente, por lista ou expressao em `t`."""

    tipo: str = TIPO_EXPRESSAO
    expressao: str = "min(1, 0.5 + 0.1 * t)"
    valores: list[PontoEscopo] = field(default_factory=list)


@dataclass
class PontoComerciais:
    mes: str
    comerciais: int = 0


@dataclass
class FuncaoComerciais:
    """Comerciais ativos no mes, por lista explicita ou expressao em `n`."""

    tipo: str = TIPO_LISTA
    expressao: str = "2"
    valores: list[PontoComerciais] = field(default_factory=list)


@dataclass
class PontoCusto:
    mes: str
    custo: float = 0.0


@dataclass
class FuncaoCusto:
    """Custo de estrutura do mes, por lista explicita ou expressao em `n` e `a`."""

    tipo: str = TIPO_EXPRESSAO
    expressao: str = "9000 + 120 * a"
    valores: list[PontoCusto] = field(default_factory=list)


@dataclass
class Parametros:
    """Bloco `parametros` do JSON. Percentuais sao fracoes (0.02 = 2%)."""

    # Configuracao geral
    meses_simulados: int = 12

    # Aquisicao de clientes
    funcao_comerciais: FuncaoComerciais = field(default_factory=FuncaoComerciais)
    funcao_aquisicao: FuncaoAquisicao = field(default_factory=FuncaoAquisicao)
    taxa_churn_mensal: float = 0.04

    # Contrato: o que o cliente paga no escopo pleno
    retainer_mensal_pleno: float = 7500.0
    taxa_setup: float = 2500.0
    verba_midia_media: float = 15000.0
    fee_gestao_midia_percentual: float = 0.12

    # Escopo em execucao e sazonalidade da verba de midia
    curva_escopo: CurvaEscopo = field(default_factory=CurvaEscopo)
    sazonalidade_midia: list[float] = field(
        default_factory=lambda: [0.8, 0.85, 0.95, 0.95, 1.0, 0.95, 0.9, 0.95, 1.0, 1.1, 1.4, 1.2]
    )

    # Piloto: meses iniciais com desconto no retainer, seguidos de decisao de continuar
    meses_piloto: int = 1
    desconto_piloto_percentual: float = 0.5
    percentual_conversao_pos_piloto: float = 0.7

    # Capacidade: a equipe cresce em degraus conforme as horas demandadas
    horas_base_cliente_mes: float = 45.0
    horas_por_10mil_midia: float = 4.0
    horas_produtivas_profissional_mes: float = 140.0
    utilizacao_alvo_percentual: float = 0.75
    custo_mensal_profissional: float = 7000.0

    # Custos
    custo_terceiros_percentual: float = 0.10
    aliquota_impostos_percentual: float = 0.08
    taxa_inadimplencia: float = 0.03
    comissao_comercial_percentual: float = 0.08
    funcao_custo_estrutura: FuncaoCusto = field(default_factory=FuncaoCusto)


@dataclass
class Metadados:
    nome_cenario: str = "base"
    data_inicio: str = field(default_factory=mes_atual)
    criado_em: str = field(default_factory=agora_utc)


def lista_comerciais_padrao(mes_inicio: str, meses: int, comerciais: int = 2) -> list[PontoComerciais]:
    """Lista cobrindo todo o horizonte, em ordem crescente e sem lacunas."""
    return [PontoComerciais(mes=mes, comerciais=comerciais)
            for mes in calendario.sequencia(mes_inicio, meses)]


def preset_padrao() -> tuple[Metadados, Parametros]:
    """Cenario deliberadamente conservador, em 12 meses."""
    metadados = Metadados(nome_cenario="base")
    parametros = Parametros()
    # A tabela de comerciais e o unico bloco em modo lista por padrao, entao
    # precisa nascer cobrindo o horizonte inteiro para passar na validacao.
    parametros.funcao_comerciais.valores = lista_comerciais_padrao(
        metadados.data_inicio, parametros.meses_simulados
    )
    return metadados, parametros


def lista_aquisicao_padrao(mes_inicio: str, meses: int, clientes: int = 2) -> list[PontoAquisicao]:
    """Lista cobrindo todo o horizonte, em ordem crescente e sem lacunas."""
    return [PontoAquisicao(mes=mes, clientes_adquiridos=clientes)
            for mes in calendario.sequencia(mes_inicio, meses)]


def lista_escopo_padrao() -> list[PontoEscopo]:
    """Pontos 1..5; o ultimo vale como escopo de regime."""
    return [PontoEscopo(mes_desde_ativacao=t, escopo_percentual=escopo)
            for t, escopo in enumerate((0.6, 0.7, 0.8, 0.9, 1.0), start=1)]


def lista_custo_padrao(mes_inicio: str, meses: int, custo: float = 9000.0) -> list[PontoCusto]:
    """Lista cobrindo todo o horizonte, em ordem crescente e sem lacunas."""
    return [PontoCusto(mes=mes, custo=custo) for mes in calendario.sequencia(mes_inicio, meses)]


def alinhar_lista_aquisicao(funcao: FuncaoAquisicao, mes_inicio: str, meses: int) -> None:
    """Reaproveita valores ja preenchidos e cobre exatamente o horizonte atual."""
    existentes = {ponto.mes: ponto.clientes_adquiridos for ponto in funcao.valores}
    padrao = existentes.get(mes_inicio, 2 if not existentes else 0)
    funcao.valores = [
        PontoAquisicao(mes=mes, clientes_adquiridos=existentes.get(mes, padrao))
        for mes in calendario.sequencia(mes_inicio, meses)
    ]


def alinhar_lista_comerciais(funcao: FuncaoComerciais, mes_inicio: str, meses: int) -> None:
    """Reaproveita valores ja preenchidos e cobre exatamente o horizonte atual."""
    existentes = {ponto.mes: ponto.comerciais for ponto in funcao.valores}
    padrao = existentes.get(mes_inicio, 2 if not existentes else 0)
    funcao.valores = [
        PontoComerciais(mes=mes, comerciais=existentes.get(mes, padrao))
        for mes in calendario.sequencia(mes_inicio, meses)
    ]


def copiar(parametros: Parametros) -> Parametros:
    return replace(
        parametros,
        funcao_comerciais=replace(
            parametros.funcao_comerciais,
            valores=[replace(ponto) for ponto in parametros.funcao_comerciais.valores],
        ),
        funcao_aquisicao=replace(
            parametros.funcao_aquisicao,
            valores=[replace(ponto) for ponto in parametros.funcao_aquisicao.valores],
        ),
        curva_escopo=replace(
            parametros.curva_escopo,
            valores=[replace(ponto) for ponto in parametros.curva_escopo.valores],
        ),
        funcao_custo_estrutura=replace(
            parametros.funcao_custo_estrutura,
            valores=[replace(ponto) for ponto in parametros.funcao_custo_estrutura.valores],
        ),
        sazonalidade_midia=list(parametros.sazonalidade_midia),
    )
