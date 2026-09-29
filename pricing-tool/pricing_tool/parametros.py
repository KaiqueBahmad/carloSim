"""Parametros de entrada da simulacao e o preset padrao."""

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from . import calendario

TIPO_LISTA = "lista"
TIPO_EXPRESSAO = "expressao"

VARIAVEIS_AQUISICAO = ("n",)
VARIAVEIS_MATURACAO = ("t",)
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
    clinicas_adquiridas: int = 0


@dataclass
class FuncaoAquisicao:
    """Aquisicao mensal por lista explicita ou por expressao em `n`."""

    tipo: str = TIPO_EXPRESSAO
    expressao: str = "2 * v"
    valores: list[PontoAquisicao] = field(default_factory=list)


@dataclass
class PontoMaturacao:
    mes_desde_ativacao: int
    ocupacao_percentual: float = 0.0


@dataclass
class CurvaMaturacao:
    """Ocupacao ao longo da vida da clinica, por lista ou expressao em `t`."""

    tipo: str = TIPO_EXPRESSAO
    expressao: str = "min(0.3, 0.05 * t)"
    valores: list[PontoMaturacao] = field(default_factory=list)


@dataclass
class PontoVendedores:
    mes: str
    vendedores: int = 0


@dataclass
class FuncaoVendedores:
    """Vendedores ativos no mes, por lista explicita ou expressao em `n`."""

    tipo: str = TIPO_LISTA
    expressao: str = "2"
    valores: list[PontoVendedores] = field(default_factory=list)


@dataclass
class PontoCusto:
    mes: str
    custo: float = 0.0


@dataclass
class FuncaoCusto:
    """Custo operacional do mes, por lista explicita ou expressao em `n` e `a`."""

    tipo: str = TIPO_EXPRESSAO
    expressao: str = "4500"
    valores: list[PontoCusto] = field(default_factory=list)


@dataclass
class Parametros:
    """Bloco `parametros` do JSON. Percentuais sao fracoes (0.02 = 2%)."""

    # 3.1 Configuracao geral
    meses_simulados: int = 12

    # 3.2 Aquisicao de clinicas
    funcao_vendedores: FuncaoVendedores = field(default_factory=FuncaoVendedores)
    funcao_aquisicao: FuncaoAquisicao = field(default_factory=FuncaoAquisicao)
    taxa_churn_mensal: float = 0.03

    # 3.3 Estrutura de cada clinica
    consultorios_por_clinica_media: float = 4.0

    # 3.4 Utilizacao / ocupacao
    vagas_disponiveis_dia: float = 16.0
    dias_operacao_mes: float = 26.0
    curva_maturacao: CurvaMaturacao = field(default_factory=CurvaMaturacao)
    sazonalidade_mensal: list[float] = field(
        default_factory=lambda: [0.9, 0.9, 1.0, 1.0, 1.05, 1.05, 1.0, 1.0, 1.05, 1.05, 1.1, 1.1]
    )
    valor_medio_atendimento: float = 180.0

    # 3.5 Receita transacional
    taxa_fixa_por_atendimento: float = 1.5
    taxa_percentual_por_atendimento: float = 0.02

    # 3.6 Receita recorrente
    valor_mensalidade: float = 149.0
    meses_trial_gratis: int = 1
    percentual_conversao_pos_trial: float = 0.6

    # 3.7 Custos
    custo_processamento_percentual: float = 0.0
    taxa_inadimplencia: float = 0.04
    comissao_vendedor_percentual: float = 0.2
    funcao_custo_operacional: FuncaoCusto = field(default_factory=FuncaoCusto)


@dataclass
class Metadados:
    nome_cenario: str = "base"
    data_inicio: str = field(default_factory=mes_atual)
    criado_em: str = field(default_factory=agora_utc)


def lista_vendedores_padrao(mes_inicio: str, meses: int, vendedores: int = 2) -> list[PontoVendedores]:
    """Lista cobrindo todo o horizonte, em ordem crescente e sem lacunas."""
    return [PontoVendedores(mes=mes, vendedores=vendedores)
            for mes in calendario.sequencia(mes_inicio, meses)]


def preset_padrao() -> tuple[Metadados, Parametros]:
    """Cenario deliberadamente conservador, em 12 meses."""
    metadados = Metadados(nome_cenario="base")
    parametros = Parametros()
    # A tabela de vendedores e o unico bloco em modo lista por padrao, entao
    # precisa nascer cobrindo o horizonte inteiro para passar na validacao.
    parametros.funcao_vendedores.valores = lista_vendedores_padrao(
        metadados.data_inicio, parametros.meses_simulados
    )
    return metadados, parametros


def lista_aquisicao_padrao(mes_inicio: str, meses: int, clinicas: int = 2) -> list[PontoAquisicao]:
    """Lista cobrindo todo o horizonte, em ordem crescente e sem lacunas."""
    return [PontoAquisicao(mes=mes, clinicas_adquiridas=clinicas)
            for mes in calendario.sequencia(mes_inicio, meses)]


def lista_maturacao_padrao() -> list[PontoMaturacao]:
    """Pontos 1..6; o ultimo vale como ocupacao de regime."""
    return [PontoMaturacao(mes_desde_ativacao=t, ocupacao_percentual=ocupacao)
            for t, ocupacao in enumerate((0.05, 0.10, 0.15, 0.20, 0.25, 0.30), start=1)]


def lista_custo_padrao(mes_inicio: str, meses: int, custo: float = 4500.0) -> list[PontoCusto]:
    """Lista cobrindo todo o horizonte, em ordem crescente e sem lacunas."""
    return [PontoCusto(mes=mes, custo=custo) for mes in calendario.sequencia(mes_inicio, meses)]


def alinhar_lista_aquisicao(funcao: FuncaoAquisicao, mes_inicio: str, meses: int) -> None:
    """Reaproveita valores ja preenchidos e cobre exatamente o horizonte atual."""
    existentes = {ponto.mes: ponto.clinicas_adquiridas for ponto in funcao.valores}
    padrao = existentes.get(mes_inicio, 2 if not existentes else 0)
    funcao.valores = [
        PontoAquisicao(mes=mes, clinicas_adquiridas=existentes.get(mes, padrao))
        for mes in calendario.sequencia(mes_inicio, meses)
    ]


def alinhar_lista_vendedores(funcao: FuncaoVendedores, mes_inicio: str, meses: int) -> None:
    """Reaproveita valores ja preenchidos e cobre exatamente o horizonte atual."""
    existentes = {ponto.mes: ponto.vendedores for ponto in funcao.valores}
    padrao = existentes.get(mes_inicio, 2 if not existentes else 0)
    funcao.valores = [
        PontoVendedores(mes=mes, vendedores=existentes.get(mes, padrao))
        for mes in calendario.sequencia(mes_inicio, meses)
    ]


def copiar(parametros: Parametros) -> Parametros:
    return replace(
        parametros,
        funcao_vendedores=replace(
            parametros.funcao_vendedores,
            valores=[replace(ponto) for ponto in parametros.funcao_vendedores.valores],
        ),
        funcao_aquisicao=replace(
            parametros.funcao_aquisicao,
            valores=[replace(ponto) for ponto in parametros.funcao_aquisicao.valores],
        ),
        curva_maturacao=replace(
            parametros.curva_maturacao,
            valores=[replace(ponto) for ponto in parametros.curva_maturacao.valores],
        ),
        funcao_custo_operacional=replace(
            parametros.funcao_custo_operacional,
            valores=[replace(ponto) for ponto in parametros.funcao_custo_operacional.valores],
        ),
        sazonalidade_mensal=list(parametros.sazonalidade_mensal),
    )
