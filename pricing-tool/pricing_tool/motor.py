"""Motor de calculo mes a mes e agregacao de KPIs.

O mesmo laco mensal roda em dois modos, que diferem so em como a base perde
clinicas: `Continua` tira a fracao exata (deterministico) e `Sorteio` tira um
binomial por cohort (agente que lanca dados). Ver `POLITICAS`.
"""

import random
from dataclasses import dataclass, field

from . import calendario, expressoes
from .parametros import TIPO_EXPRESSAO, Metadados, Parametros


@dataclass
class MesResultado:
    mes: int
    data: str
    vendedores: int
    clinicas_ativas: float
    clinicas_novas: int
    clinicas_churned: float
    clinicas_inadimplentes: float
    consultorios_ativos: float
    ocupacao_media_percentual: float
    atendimentos_efetivos: float
    volume_transacionado: float
    receita_transacional: float
    receita_mensalidade: float
    receita_total: float
    perda_inadimplencia: float
    comissao_vendedor: float
    comissao_por_vendedor: float
    custos_total: float
    resultado_liquido: float
    resultado_acumulado: float


@dataclass
class KpisAgregados:
    volume_transacionado_total: float = 0.0
    receita_total_periodo: float = 0.0
    receita_transacional_total: float = 0.0
    receita_mensalidade_total: float = 0.0
    perda_inadimplencia_total: float = 0.0
    comissao_vendedor_total: float = 0.0
    comissao_por_vendedor_total: float = 0.0
    custos_total_periodo: float = 0.0
    resultado_liquido_total: float = 0.0
    atendimentos_efetivos_total: float = 0.0
    ticket_medio_realizado: float = 0.0
    clinicas_adquiridas_total: float = 0.0
    clinicas_churned_total: float = 0.0
    clinicas_inadimplentes_total: float = 0.0
    clinicas_ativas_final: float = 0.0
    ltv_medio: float = 0.0
    payback_meses: int | None = None
    crescimento_medio_base_percentual: float = 0.0
    churn_acumulado_percentual: float = 0.0


@dataclass
class Resultados:
    series_mensais: list[MesResultado] = field(default_factory=list)
    kpis_agregados: KpisAgregados = field(default_factory=KpisAgregados)


class Continua:
    """Saida deterministica: a fracao exata da base deixa o cohort."""

    def saem(self, ativas: float, taxa: float) -> float:
        return ativas * taxa


class Sorteio:
    """Saida por dado: cada clinica do cohort e um ensaio de Bernoulli."""

    def __init__(self, rng: random.Random):
        self._rng = rng

    def saem(self, ativas: float, taxa: float) -> float:
        clinicas = int(round(ativas))
        if clinicas <= 0 or taxa <= 0.0:
            return 0.0
        return float(self._rng.binomialvariate(clinicas, min(1.0, taxa)))


@dataclass
class _Cohort:
    mes_ativacao: int
    ativas: float


def _fonte_vendedores(parametros: Parametros):
    """Retorna f(mes_simulacao, mes_calendario) -> vendedores ativos no mes."""
    funcao = parametros.funcao_vendedores
    if funcao.tipo == TIPO_EXPRESSAO:
        expressao = expressoes.compilar(funcao.expressao, ("n",))
        return lambda n, _data: expressoes.normalizar_aquisicao(expressao.avaliar(n=n))
    por_mes = {ponto.mes: ponto.vendedores for ponto in funcao.valores}
    return lambda _n, data: expressoes.normalizar_aquisicao(float(por_mes.get(data, 0)))


def _fonte_aquisicao(parametros: Parametros):
    """Retorna f(mes_simulacao, mes_calendario, vendedores) -> clinicas novas."""
    funcao = parametros.funcao_aquisicao
    if funcao.tipo == TIPO_EXPRESSAO:
        expressao = expressoes.compilar(funcao.expressao, ("n", "v"))
        return lambda n, _data, v: expressoes.normalizar_aquisicao(expressao.avaliar(n=n, v=v))
    por_mes = {ponto.mes: ponto.clinicas_adquiridas for ponto in funcao.valores}
    return lambda _n, data, _v: expressoes.normalizar_aquisicao(float(por_mes.get(data, 0)))


def _fonte_maturacao(parametros: Parametros):
    """Retorna f(mes_desde_ativacao) -> ocupacao entre 0 e 1."""
    curva = parametros.curva_maturacao
    if curva.tipo == TIPO_EXPRESSAO:
        expressao = expressoes.compilar(curva.expressao, ("t",))
        return lambda t: expressoes.normalizar_ocupacao(expressao.avaliar(t=t))
    pontos = sorted(curva.valores, key=lambda ponto: ponto.mes_desde_ativacao)
    if not pontos:
        return lambda _t: 0.0
    por_t = {ponto.mes_desde_ativacao: ponto.ocupacao_percentual for ponto in pontos}
    ultimo = pontos[-1]

    def maturacao(t: int) -> float:
        # Alem do ultimo ponto vale a ocupacao de regime.
        bruto = por_t.get(t, ultimo.ocupacao_percentual if t > ultimo.mes_desde_ativacao else 0.0)
        return expressoes.normalizar_ocupacao(float(bruto))

    return maturacao


def _fonte_custo(parametros: Parametros):
    """Retorna f(mes, mes_calendario, clinicas_ativas) -> custo operacional do mes."""
    funcao = parametros.funcao_custo_operacional
    if funcao.tipo == TIPO_EXPRESSAO:
        expressao = expressoes.compilar(funcao.expressao, ("n", "a"))
        return lambda n, _data, a: expressoes.normalizar_custo(expressao.avaliar(n=n, a=a))
    por_mes = {ponto.mes: ponto.custo for ponto in funcao.valores}
    return lambda _n, data, _a: expressoes.normalizar_custo(float(por_mes.get(data, 0.0)))


def _sazonalidade(parametros: Parametros, data: str) -> float:
    fatores = parametros.sazonalidade_mensal
    indice = calendario.indice_no_ano(data)
    if len(fatores) != 12:
        return 1.0
    return max(0.0, float(fatores[indice]))


def simular(parametros: Parametros, metadados: Metadados, politica=None) -> Resultados:
    """Roda a simulacao mes a mes. Lanca ErroExpressao se uma formula for invalida.

    `politica` decide como a base encolhe; o padrao e deterministico.
    """
    politica = politica or Continua()
    vendedores_ativos = _fonte_vendedores(parametros)
    aquisicao = _fonte_aquisicao(parametros)
    maturacao = _fonte_maturacao(parametros)
    custo_operacional = _fonte_custo(parametros)

    cohorts: list[_Cohort] = []
    series: list[MesResultado] = []
    acumulado = 0.0

    vagas_por_clinica_mes = (
        parametros.consultorios_por_clinica_media
        * parametros.vagas_disponiveis_dia
        * parametros.dias_operacao_mes
    )

    for mes in range(1, max(0, parametros.meses_simulados) + 1):
        data = calendario.somar(metadados.data_inicio, mes - 1)

        # 1. Aquisicao / 2. Churn sobre a base do mes anterior / 3. Base ativa
        vendedores = vendedores_ativos(mes, data)
        novas = aquisicao(mes, data, vendedores)
        churned = 0.0
        for cohort in cohorts:
            perdidas = politica.saem(cohort.ativas, parametros.taxa_churn_mensal)
            cohort.ativas -= perdidas
            churned += perdidas
        if novas > 0:
            cohorts.append(_Cohort(mes_ativacao=mes, ativas=float(novas)))

        # Fim do trial: quem nao assina deixa de ter agenda online, entao sai da base.
        for cohort in cohorts:
            if mes - cohort.mes_ativacao + 1 == parametros.meses_trial_gratis + 1:
                nao_converteram = politica.saem(
                    cohort.ativas, 1.0 - parametros.percentual_conversao_pos_trial
                )
                cohort.ativas -= nao_converteram
                churned += nao_converteram
        cohorts = [cohort for cohort in cohorts if cohort.ativas > 1e-9]

        clinicas_ativas = sum(cohort.ativas for cohort in cohorts)
        fator_sazonal = _sazonalidade(parametros, data)

        # 4-8. Maturacao por cohort, sazonalidade e atendimentos efetivos.
        # A receita e apurada por cohort porque a inadimplencia cobra do cohort
        # que deixou de pagar, e nao a media da base: clinica nova fatura muito
        # menos que clinica madura.
        atendimentos_efetivos = 0.0
        clinicas_pagantes = 0.0
        receita_por_cohort: list[float] = []
        for cohort in cohorts:
            t = mes - cohort.mes_ativacao + 1
            ocupacao = expressoes.normalizar_ocupacao(maturacao(t) * fator_sazonal)
            atendimentos = cohort.ativas * vagas_por_clinica_mes * ocupacao
            atendimentos_efetivos += atendimentos
            receita = atendimentos * (
                parametros.taxa_fixa_por_atendimento
                + parametros.valor_medio_atendimento * parametros.taxa_percentual_por_atendimento
            )
            if t > parametros.meses_trial_gratis:
                clinicas_pagantes += cohort.ativas
                receita += cohort.ativas * parametros.valor_mensalidade
            receita_por_cohort.append(receita)

        consultorios_ativos = clinicas_ativas * parametros.consultorios_por_clinica_media
        atendimentos_possiveis = (
            consultorios_ativos * parametros.vagas_disponiveis_dia * parametros.dias_operacao_mes
        )
        ocupacao_media = atendimentos_efetivos / atendimentos_possiveis if atendimentos_possiveis else 0.0

        # 9-12. Receita
        volume_transacionado = atendimentos_efetivos * parametros.valor_medio_atendimento
        receita_transacional = (
            atendimentos_efetivos * parametros.taxa_fixa_por_atendimento
            + volume_transacionado * parametros.taxa_percentual_por_atendimento
        )
        receita_mensalidade = clinicas_pagantes * parametros.valor_mensalidade
        receita_total = receita_transacional + receita_mensalidade

        # 13. Inadimplencia: a fatura do mes nao e paga e a clinica perde o acesso.
        # Ela operou o mes inteiro, entao a receita faturada vira perda e a saida
        # so vale para o mes seguinte.
        inadimplentes = 0.0
        perda_inadimplencia = 0.0
        if parametros.taxa_inadimplencia > 0:
            for cohort, receita in zip(cohorts, receita_por_cohort):
                perdidas = politica.saem(cohort.ativas, parametros.taxa_inadimplencia)
                if cohort.ativas > 0:
                    perda_inadimplencia += receita * (perdidas / cohort.ativas)
                cohort.ativas -= perdidas
                inadimplentes += perdidas
            cohorts = [cohort for cohort in cohorts if cohort.ativas > 1e-9]

        # 14. Comissao do vendedor sobre o que entrou de fato: se a clinica nao
        # pagou, ninguem comissiona em cima da fatura furada.
        receita_recebida = receita_total - perda_inadimplencia
        comissao_vendedor = receita_recebida * parametros.comissao_vendedor_percentual
        comissao_por_vendedor = comissao_vendedor / vendedores if vendedores else 0.0

        # 15-16. Custos e resultado
        custos_total = (
            custo_operacional(mes, data, clinicas_ativas)
            + volume_transacionado * parametros.custo_processamento_percentual
            + perda_inadimplencia
            + comissao_vendedor
        )
        resultado_liquido = receita_total - custos_total
        acumulado += resultado_liquido

        series.append(
            MesResultado(
                mes=mes,
                data=data,
                vendedores=vendedores,
                clinicas_ativas=clinicas_ativas,
                clinicas_novas=novas,
                clinicas_churned=churned,
                clinicas_inadimplentes=inadimplentes,
                consultorios_ativos=consultorios_ativos,
                ocupacao_media_percentual=ocupacao_media,
                atendimentos_efetivos=atendimentos_efetivos,
                volume_transacionado=volume_transacionado,
                receita_transacional=receita_transacional,
                receita_mensalidade=receita_mensalidade,
                receita_total=receita_total,
                perda_inadimplencia=perda_inadimplencia,
                comissao_vendedor=comissao_vendedor,
                comissao_por_vendedor=comissao_por_vendedor,
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

    kpis.volume_transacionado_total = sum(mes.volume_transacionado for mes in series)
    kpis.receita_transacional_total = sum(mes.receita_transacional for mes in series)
    kpis.receita_mensalidade_total = sum(mes.receita_mensalidade for mes in series)
    kpis.receita_total_periodo = kpis.receita_transacional_total + kpis.receita_mensalidade_total
    kpis.perda_inadimplencia_total = sum(mes.perda_inadimplencia for mes in series)
    kpis.comissao_vendedor_total = sum(mes.comissao_vendedor for mes in series)
    # O que um vendedor presente o periodo inteiro teria levado.
    kpis.comissao_por_vendedor_total = sum(mes.comissao_por_vendedor for mes in series)
    kpis.custos_total_periodo = sum(mes.custos_total for mes in series)
    kpis.resultado_liquido_total = kpis.receita_total_periodo - kpis.custos_total_periodo
    kpis.atendimentos_efetivos_total = sum(mes.atendimentos_efetivos for mes in series)
    kpis.ticket_medio_realizado = (
        kpis.volume_transacionado_total / kpis.atendimentos_efetivos_total if kpis.atendimentos_efetivos_total else 0.0
    )

    kpis.clinicas_adquiridas_total = sum(mes.clinicas_novas for mes in series)
    kpis.clinicas_churned_total = sum(mes.clinicas_churned for mes in series)
    kpis.clinicas_inadimplentes_total = sum(mes.clinicas_inadimplentes for mes in series)
    kpis.clinicas_ativas_final = series[-1].clinicas_ativas
    kpis.churn_acumulado_percentual = (
        kpis.clinicas_churned_total / kpis.clinicas_adquiridas_total
        if kpis.clinicas_adquiridas_total
        else 0.0
    )

    # LTV = receita media por clinica ativa/mes x vida media (1 / saida mensal).
    # A clinica sai por churn ou por inadimplencia, entao as duas taxas contam.
    clinicas_mes = sum(mes.clinicas_ativas for mes in series)
    receita_por_clinica_mes = kpis.receita_total_periodo / clinicas_mes if clinicas_mes else 0.0
    saida_mensal = parametros.taxa_churn_mensal + parametros.taxa_inadimplencia
    vida_media = 1.0 / saida_mensal if saida_mensal > 0 else float(len(series))
    kpis.ltv_medio = receita_por_clinica_mes * vida_media

    for mes in series:
        if mes.resultado_acumulado >= 0:
            kpis.payback_meses = mes.mes
            break

    crescimentos = [
        series[i].clinicas_ativas / series[i - 1].clinicas_ativas
        for i in range(1, len(series))
        if series[i - 1].clinicas_ativas > 0
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
