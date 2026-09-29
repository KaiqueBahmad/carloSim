"""Motor de calculo mes a mes e agregacao de KPIs de uma agencia de marketing.

O mesmo laco mensal roda em dois modos, que diferem so em como a carteira perde
clientes: `Continua` tira a fracao exata (deterministico) e `Sorteio` tira um
binomial por cohort (agente que lanca dados).

A interacao central do modelo e a capacidade: o escopo de cada cliente e a verba
de midia sob gestao geram horas de trabalho, e as horas dimensionam a equipe em
degraus de profissionais inteiros. Receita cresce de forma suave; custo de equipe
sobe em saltos — e e a margem entre os dois que decide o resultado.
"""

import math
import random
from dataclasses import dataclass, field

from . import calendario, expressoes
from .parametros import TIPO_EXPRESSAO, Metadados, Parametros


@dataclass
class MesResultado:
    mes: int
    data: str
    comerciais: int
    clientes_ativos: float
    clientes_novos: int
    clientes_churned: float
    clientes_inadimplentes: float
    verba_midia_gerenciada: float
    horas_demandadas: float
    equipe: int
    utilizacao_equipe_percentual: float
    receita_retainer: float
    receita_midia: float
    receita_setup: float
    receita_total: float
    custo_equipe: float
    custo_estrutura: float
    custo_terceiros: float
    impostos: float
    perda_inadimplencia: float
    comissao_comercial: float
    comissao_por_comercial: float
    custos_total: float
    resultado_liquido: float
    resultado_acumulado: float


@dataclass
class KpisAgregados:
    verba_midia_total: float = 0.0
    receita_total_periodo: float = 0.0
    receita_retainer_total: float = 0.0
    receita_midia_total: float = 0.0
    receita_setup_total: float = 0.0
    custo_equipe_total: float = 0.0
    perda_inadimplencia_total: float = 0.0
    comissao_comercial_total: float = 0.0
    comissao_por_comercial_total: float = 0.0
    custos_total_periodo: float = 0.0
    resultado_liquido_total: float = 0.0
    margem_liquida_percentual: float = 0.0
    receita_media_por_cliente_mes: float = 0.0
    utilizacao_media_percentual: float = 0.0
    equipe_final: float = 0.0
    clientes_adquiridos_total: float = 0.0
    clientes_churned_total: float = 0.0
    clientes_inadimplentes_total: float = 0.0
    clientes_ativos_final: float = 0.0
    ltv_medio: float = 0.0
    payback_meses: int | None = None
    crescimento_medio_base_percentual: float = 0.0
    churn_acumulado_percentual: float = 0.0


@dataclass
class Resultados:
    series_mensais: list[MesResultado] = field(default_factory=list)
    kpis_agregados: KpisAgregados = field(default_factory=KpisAgregados)


class Continua:
    """Saida deterministica: a fracao exata da carteira deixa o cohort."""

    def saem(self, ativos: float, taxa: float) -> float:
        return ativos * taxa


class Sorteio:
    """Saida por dado: cada cliente do cohort e um ensaio de Bernoulli."""

    def __init__(self, rng: random.Random):
        self._rng = rng

    def saem(self, ativos: float, taxa: float) -> float:
        clientes = int(round(ativos))
        if clientes <= 0 or taxa <= 0.0:
            return 0.0
        return float(self._rng.binomialvariate(clientes, min(1.0, taxa)))


@dataclass
class _Cohort:
    mes_ativacao: int
    ativos: float


def _fonte_comerciais(parametros: Parametros):
    """Retorna f(mes_simulacao, mes_calendario) -> comerciais ativos no mes."""
    funcao = parametros.funcao_comerciais
    if funcao.tipo == TIPO_EXPRESSAO:
        expressao = expressoes.compilar(funcao.expressao, ("n",))
        return lambda n, _data: expressoes.normalizar_aquisicao(expressao.avaliar(n=n))
    por_mes = {ponto.mes: ponto.comerciais for ponto in funcao.valores}
    return lambda _n, data: expressoes.normalizar_aquisicao(float(por_mes.get(data, 0)))


def _fonte_aquisicao(parametros: Parametros):
    """Retorna f(mes_simulacao, mes_calendario, comerciais) -> clientes novos."""
    funcao = parametros.funcao_aquisicao
    if funcao.tipo == TIPO_EXPRESSAO:
        expressao = expressoes.compilar(funcao.expressao, ("n", "c"))
        return lambda n, _data, c: expressoes.normalizar_aquisicao(expressao.avaliar(n=n, c=c))
    por_mes = {ponto.mes: ponto.clientes_adquiridos for ponto in funcao.valores}
    return lambda _n, data, _c: expressoes.normalizar_aquisicao(float(por_mes.get(data, 0)))


def _fonte_escopo(parametros: Parametros):
    """Retorna f(mes_desde_ativacao) -> fracao do escopo pleno entre 0 e 1."""
    curva = parametros.curva_escopo
    if curva.tipo == TIPO_EXPRESSAO:
        expressao = expressoes.compilar(curva.expressao, ("t",))
        return lambda t: expressoes.normalizar_escopo(expressao.avaliar(t=t))
    pontos = sorted(curva.valores, key=lambda ponto: ponto.mes_desde_ativacao)
    if not pontos:
        return lambda _t: 0.0
    por_t = {ponto.mes_desde_ativacao: ponto.escopo_percentual for ponto in pontos}
    ultimo = pontos[-1]

    def escopo(t: int) -> float:
        # Alem do ultimo ponto vale o escopo de regime.
        bruto = por_t.get(t, ultimo.escopo_percentual if t > ultimo.mes_desde_ativacao else 0.0)
        return expressoes.normalizar_escopo(float(bruto))

    return escopo


def _fonte_custo(parametros: Parametros):
    """Retorna f(mes, mes_calendario, clientes_ativos) -> custo de estrutura do mes."""
    funcao = parametros.funcao_custo_estrutura
    if funcao.tipo == TIPO_EXPRESSAO:
        expressao = expressoes.compilar(funcao.expressao, ("n", "a"))
        return lambda n, _data, a: expressoes.normalizar_custo(expressao.avaliar(n=n, a=a))
    por_mes = {ponto.mes: ponto.custo for ponto in funcao.valores}
    return lambda _n, data, _a: expressoes.normalizar_custo(float(por_mes.get(data, 0.0)))


def _sazonalidade(parametros: Parametros, data: str) -> float:
    fatores = parametros.sazonalidade_midia
    indice = calendario.indice_no_ano(data)
    if len(fatores) != 12:
        return 1.0
    return max(0.0, float(fatores[indice]))


def _dimensionar_equipe(parametros: Parametros, horas: float) -> int:
    """Profissionais inteiros para absorver as horas dentro da utilizacao alvo."""
    capacidade = (
        parametros.horas_produtivas_profissional_mes * parametros.utilizacao_alvo_percentual
    )
    if horas <= 1e-9 or capacidade <= 0.0:
        return 0
    return math.ceil(horas / capacidade - 1e-9)


def simular(parametros: Parametros, metadados: Metadados, politica=None) -> Resultados:
    """Roda a simulacao mes a mes. Lanca ErroExpressao se uma formula for invalida.

    `politica` decide como a carteira encolhe; o padrao e deterministico.
    """
    politica = politica or Continua()
    comerciais_ativos = _fonte_comerciais(parametros)
    aquisicao = _fonte_aquisicao(parametros)
    escopo_em = _fonte_escopo(parametros)
    custo_estrutura_em = _fonte_custo(parametros)

    cohorts: list[_Cohort] = []
    series: list[MesResultado] = []
    acumulado = 0.0

    for mes in range(1, max(0, parametros.meses_simulados) + 1):
        data = calendario.somar(metadados.data_inicio, mes - 1)

        # 1. Aquisicao / 2. Churn sobre a carteira do mes anterior / 3. Carteira ativa
        comerciais = comerciais_ativos(mes, data)
        novos = aquisicao(mes, data, comerciais)
        churned = 0.0
        for cohort in cohorts:
            perdidos = politica.saem(cohort.ativos, parametros.taxa_churn_mensal)
            cohort.ativos -= perdidos
            churned += perdidos
        if novos > 0:
            cohorts.append(_Cohort(mes_ativacao=mes, ativos=float(novos)))

        # Fim do piloto: quem nao decide continuar encerra o contrato e sai da carteira.
        for cohort in cohorts:
            if mes - cohort.mes_ativacao + 1 == parametros.meses_piloto + 1:
                nao_converteram = politica.saem(
                    cohort.ativos, 1.0 - parametros.percentual_conversao_pos_piloto
                )
                cohort.ativos -= nao_converteram
                churned += nao_converteram
        cohorts = [cohort for cohort in cohorts if cohort.ativos > 1e-9]

        clientes_ativos = sum(cohort.ativos for cohort in cohorts)
        fator_sazonal = _sazonalidade(parametros, data)

        # 4-8. Por cohort: escopo em execucao define retainer, verba de midia e horas.
        # A receita e apurada por cohort porque a inadimplencia cobra do cohort que
        # deixou de pagar, e nao a media da carteira: cliente novo, em escopo reduzido
        # e piloto com desconto, fatura muito menos que cliente maduro.
        verba_total = 0.0
        horas_total = 0.0
        receita_retainer = 0.0
        receita_midia = 0.0
        receita_setup = 0.0
        receita_por_cohort: list[float] = []
        for cohort in cohorts:
            t = mes - cohort.mes_ativacao + 1
            escopo = escopo_em(t)
            em_piloto = t <= parametros.meses_piloto
            fator_piloto = 1.0 - parametros.desconto_piloto_percentual if em_piloto else 1.0

            verba = cohort.ativos * parametros.verba_midia_media * escopo * fator_sazonal
            horas = (
                cohort.ativos * parametros.horas_base_cliente_mes * escopo
                + verba / 10_000.0 * parametros.horas_por_10mil_midia
            )
            retainer = (
                cohort.ativos * parametros.retainer_mensal_pleno * escopo * fator_piloto
            )
            midia = verba * parametros.fee_gestao_midia_percentual
            setup = cohort.ativos * parametros.taxa_setup if t == 1 else 0.0

            verba_total += verba
            horas_total += horas
            receita_retainer += retainer
            receita_midia += midia
            receita_setup += setup
            receita_por_cohort.append(retainer + midia + setup)

        receita_total = receita_retainer + receita_midia + receita_setup

        # 9. Capacidade: horas viram profissionais inteiros, e ai o custo salta em degraus.
        equipe = _dimensionar_equipe(parametros, horas_total)
        horas_disponiveis = equipe * parametros.horas_produtivas_profissional_mes
        utilizacao = horas_total / horas_disponiveis if horas_disponiveis else 0.0
        custo_equipe = equipe * parametros.custo_mensal_profissional

        # 10. Inadimplencia: a fatura do mes nao e paga e o contrato e encerrado.
        # O cliente consumiu o mes inteiro de entrega, entao a receita faturada vira
        # perda e a saida so vale para o mes seguinte.
        inadimplentes = 0.0
        perda_inadimplencia = 0.0
        if parametros.taxa_inadimplencia > 0:
            for cohort, receita in zip(cohorts, receita_por_cohort):
                perdidos = politica.saem(cohort.ativos, parametros.taxa_inadimplencia)
                if cohort.ativos > 0:
                    perda_inadimplencia += receita * (perdidos / cohort.ativos)
                cohort.ativos -= perdidos
                inadimplentes += perdidos
            cohorts = [cohort for cohort in cohorts if cohort.ativos > 1e-9]

        # 11. Comissao comercial sobre o que entrou de fato: se o cliente nao pagou,
        # ninguem comissiona em cima da fatura furada.
        receita_recebida = receita_total - perda_inadimplencia
        comissao_comercial = receita_recebida * parametros.comissao_comercial_percentual
        comissao_por_comercial = comissao_comercial / comerciais if comerciais else 0.0

        # 12-13. Custos e resultado
        custo_estrutura = custo_estrutura_em(mes, data, clientes_ativos)
        custo_terceiros = receita_retainer * parametros.custo_terceiros_percentual
        impostos = receita_total * parametros.aliquota_impostos_percentual
        custos_total = (
            custo_equipe
            + custo_estrutura
            + custo_terceiros
            + impostos
            + perda_inadimplencia
            + comissao_comercial
        )
        resultado_liquido = receita_total - custos_total
        acumulado += resultado_liquido

        series.append(
            MesResultado(
                mes=mes,
                data=data,
                comerciais=comerciais,
                clientes_ativos=clientes_ativos,
                clientes_novos=novos,
                clientes_churned=churned,
                clientes_inadimplentes=inadimplentes,
                verba_midia_gerenciada=verba_total,
                horas_demandadas=horas_total,
                equipe=equipe,
                utilizacao_equipe_percentual=utilizacao,
                receita_retainer=receita_retainer,
                receita_midia=receita_midia,
                receita_setup=receita_setup,
                receita_total=receita_total,
                custo_equipe=custo_equipe,
                custo_estrutura=custo_estrutura,
                custo_terceiros=custo_terceiros,
                impostos=impostos,
                perda_inadimplencia=perda_inadimplencia,
                comissao_comercial=comissao_comercial,
                comissao_por_comercial=comissao_por_comercial,
                custos_total=custos_total,
                resultado_liquido=resultado_liquido,
                resultado_acumulado=acumulado,
            )
        )

    return Resultados(series_mensais=series, kpis_agregados=_agregar(parametros, series))


def _agregar(parametros: Parametros, series: list[MesResultado]) -> KpisAgregados:
    kpis = KpisAgregados()
    if not series:
        return kpis

    kpis.verba_midia_total = sum(mes.verba_midia_gerenciada for mes in series)
    kpis.receita_retainer_total = sum(mes.receita_retainer for mes in series)
    kpis.receita_midia_total = sum(mes.receita_midia for mes in series)
    kpis.receita_setup_total = sum(mes.receita_setup for mes in series)
    kpis.receita_total_periodo = (
        kpis.receita_retainer_total + kpis.receita_midia_total + kpis.receita_setup_total
    )
    kpis.custo_equipe_total = sum(mes.custo_equipe for mes in series)
    kpis.perda_inadimplencia_total = sum(mes.perda_inadimplencia for mes in series)
    kpis.comissao_comercial_total = sum(mes.comissao_comercial for mes in series)
    # O que um comercial presente o periodo inteiro teria levado.
    kpis.comissao_por_comercial_total = sum(mes.comissao_por_comercial for mes in series)
    kpis.custos_total_periodo = sum(mes.custos_total for mes in series)
    kpis.resultado_liquido_total = kpis.receita_total_periodo - kpis.custos_total_periodo
    kpis.margem_liquida_percentual = (
        kpis.resultado_liquido_total / kpis.receita_total_periodo
        if kpis.receita_total_periodo
        else 0.0
    )

    kpis.clientes_adquiridos_total = sum(mes.clientes_novos for mes in series)
    kpis.clientes_churned_total = sum(mes.clientes_churned for mes in series)
    kpis.clientes_inadimplentes_total = sum(mes.clientes_inadimplentes for mes in series)
    kpis.clientes_ativos_final = series[-1].clientes_ativos
    kpis.equipe_final = series[-1].equipe
    kpis.churn_acumulado_percentual = (
        kpis.clientes_churned_total / kpis.clientes_adquiridos_total
        if kpis.clientes_adquiridos_total
        else 0.0
    )

    meses_com_equipe = [mes for mes in series if mes.equipe]
    if meses_com_equipe:
        kpis.utilizacao_media_percentual = sum(
            mes.utilizacao_equipe_percentual for mes in meses_com_equipe
        ) / len(meses_com_equipe)

    # LTV = receita media por cliente ativo/mes x vida media (1 / saida mensal).
    # O cliente sai por churn ou por inadimplencia, entao as duas taxas contam.
    clientes_mes = sum(mes.clientes_ativos for mes in series)
    kpis.receita_media_por_cliente_mes = (
        kpis.receita_total_periodo / clientes_mes if clientes_mes else 0.0
    )
    saida_mensal = parametros.taxa_churn_mensal + parametros.taxa_inadimplencia
    vida_media = 1.0 / saida_mensal if saida_mensal > 0 else float(len(series))
    kpis.ltv_medio = kpis.receita_media_por_cliente_mes * vida_media

    for mes in series:
        if mes.resultado_acumulado >= 0:
            kpis.payback_meses = mes.mes
            break

    crescimentos = [
        series[i].clientes_ativos / series[i - 1].clientes_ativos
        for i in range(1, len(series))
        if series[i - 1].clientes_ativos > 0
    ]
    if crescimentos:
        produto = 1.0
        for fator in crescimentos:
            produto *= fator
        kpis.crescimento_medio_base_percentual = produto ** (1.0 / len(crescimentos)) - 1.0

    return kpis


# --------------------------------------------------------------------------- sorte


@dataclass
class Sorte:
    """Quantas rodadas com dados bateram as duas metas: acumulado e ultimo mes."""

    meta: float = 0.0
    meta_resultado: float = 0.0
    rodadas_pedidas: int = 0
    rodadas_feitas: int = 0
    atingiram: int = 0
    atingiram_acumulado: int = 0
    atingiram_resultado: int = 0
    cancelado: bool = False
    deterministico: float = 0.0
    deterministico_resultado: float = 0.0
    percentil_do_deterministico: float = 0.0
    amostras: list[float] = field(default_factory=list)
    amostras_resultado: list[float] = field(default_factory=list)

    @property
    def proporcao(self) -> float:
        return self.atingiram / self.rodadas_feitas if self.rodadas_feitas else 0.0

    def percentil(self, fracao: float, amostras: list[float] | None = None) -> float:
        valores = self.amostras if amostras is None else amostras
        if not valores:
            return 0.0
        ordenadas = sorted(valores)
        indice = min(len(ordenadas) - 1, int(len(ordenadas) * fracao))
        return ordenadas[indice]


def calcular_sorte(
    parametros: Parametros,
    metadados: Metadados,
    meta: float,
    meta_resultado: float,
    rodadas: int,
    semente: int | None = None,
    progresso=None,
    cancelado=None,
) -> Sorte:
    """Roda a simulacao `rodadas` vezes com dados e conta quantas bateram as metas.

    A rodada so conta como acerto se o resultado acumulado do periodo alcancar
    `meta` **e** o resultado liquido do ultimo mes alcancar `meta_resultado` —
    terminar no azul acumulado nao garante que o ultimo mes tenha fechado bem.

    `progresso(feitas, total)` e chamado ao longo do caminho e `cancelado()` corta
    a execucao entre rodadas — a Sorte devolvida traz o que deu tempo de apurar.
    """
    rng = random.Random(semente)
    base = simular(parametros, metadados)
    resultado = Sorte(
        meta=meta,
        meta_resultado=meta_resultado,
        rodadas_pedidas=max(0, rodadas),
        deterministico=base.kpis_agregados.resultado_liquido_total,
        deterministico_resultado=(
            base.series_mensais[-1].resultado_liquido if base.series_mensais else 0.0
        ),
    )
    for feitas in range(1, resultado.rodadas_pedidas + 1):
        if cancelado is not None and cancelado():
            resultado.cancelado = True
            break
        series = simular(parametros, metadados, Sorteio(rng)).series_mensais
        acumulado = series[-1].resultado_acumulado if series else 0.0
        resultado_final = series[-1].resultado_liquido if series else 0.0
        resultado.amostras.append(acumulado)
        resultado.amostras_resultado.append(resultado_final)
        bateu_acumulado = acumulado >= meta
        bateu_resultado = resultado_final >= meta_resultado
        resultado.atingiram_acumulado += bateu_acumulado
        resultado.atingiram_resultado += bateu_resultado
        if bateu_acumulado and bateu_resultado:
            resultado.atingiram += 1
        resultado.rodadas_feitas = feitas
        if progresso is not None and (feitas % 100 == 0 or feitas == resultado.rodadas_pedidas):
            progresso(feitas, resultado.rodadas_pedidas)
    if resultado.amostras:
        abaixo = sum(1 for a in resultado.amostras if a < resultado.deterministico)
        resultado.percentil_do_deterministico = abaixo / len(resultado.amostras)
    return resultado
