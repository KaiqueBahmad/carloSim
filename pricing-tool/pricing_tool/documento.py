"""Contrato de import/export do JSON com defaults e validacao."""

import json
from dataclasses import asdict, fields
from typing import Any

from . import calendario, expressoes
from .motor import KpisAgregados, MesResultado, Resultados
from .parametros import (
    TIPO_EXPRESSAO,
    TIPO_LISTA,
    CurvaMaturacao,
    FuncaoAquisicao,
    FuncaoCusto,
    FuncaoVendedores,
    Metadados,
    Parametros,
    PontoAquisicao,
    PontoCusto,
    PontoMaturacao,
    PontoVendedores,
    agora_utc,
    mes_atual,
)

VERSAO_SCHEMA = "1.0"

PERCENTUAIS = (
    "taxa_churn_mensal",
    "taxa_percentual_por_atendimento",
    "percentual_conversao_pos_trial",
    "custo_processamento_percentual",
    "taxa_inadimplencia",
    "comissao_vendedor_percentual",
)


class DocumentoInvalido(ValueError):
    """O arquivo nao tem a estrutura minima de um documento de simulacao."""


class DocumentoImportado:
    def __init__(self, metadados, parametros, resultados, avisos):
        self.metadados: Metadados = metadados
        self.parametros: Parametros = parametros
        self.resultados: Resultados | None = resultados
        self.avisos: list[str] = avisos


# --------------------------------------------------------------------------- export


def montar(metadados: Metadados, parametros: Parametros, resultados: Resultados | None) -> dict:
    documento: dict[str, Any] = {
        "versao_schema": VERSAO_SCHEMA,
        "metadados": {
            "nome_cenario": metadados.nome_cenario,
            "criado_em": metadados.criado_em or agora_utc(),
            "data_inicio": metadados.data_inicio,
        },
        "parametros": asdict(parametros),
    }
    documento["resultados"] = _resultados_para_dict(resultados) if resultados else None
    return documento


def _resultados_para_dict(resultados: Resultados) -> dict:
    return {
        "series_mensais": [asdict(mes) for mes in resultados.series_mensais],
        "kpis_agregados": asdict(resultados.kpis_agregados),
    }


def serializar(documento: dict) -> str:
    """JSON indentado e com acentos preservados, para leitura/edicao manual."""
    return json.dumps(documento, indent=2, ensure_ascii=False) + "\n"


def salvar(caminho, metadados, parametros, resultados) -> dict:
    documento = montar(metadados, parametros, resultados)
    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write(serializar(documento))
    return documento


# --------------------------------------------------------------------------- import


def carregar(caminho) -> DocumentoImportado:
    with open(caminho, encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    return ler(dados)


def ler(dados: Any) -> DocumentoImportado:
    if not isinstance(dados, dict):
        raise DocumentoInvalido("o arquivo nao contem um objeto JSON")

    avisos: list[str] = []
    versao = str(dados.get("versao_schema") or "")
    if not versao:
        avisos.append(f"arquivo sem `versao_schema`; assumindo {VERSAO_SCHEMA}.")
    elif versao != VERSAO_SCHEMA:
        avisos.append(
            f"o arquivo usa o schema {versao} e este app usa o {VERSAO_SCHEMA}; "
            "campos desconhecidos foram ignorados e ausentes assumiram o default."
        )

    metadados = _ler_metadados(dados.get("metadados"), avisos)
    parametros = _ler_parametros(dados.get("parametros"), avisos)
    resultados = _ler_resultados(dados.get("resultados"), avisos)
    return DocumentoImportado(metadados, parametros, resultados, avisos)


def _ler_metadados(bruto: Any, avisos: list[str]) -> Metadados:
    bruto = bruto if isinstance(bruto, dict) else {}
    metadados = Metadados()
    metadados.nome_cenario = str(bruto.get("nome_cenario") or "importado")
    metadados.criado_em = str(bruto.get("criado_em") or agora_utc())
    data_inicio = str(bruto.get("data_inicio") or "")
    if calendario.valido(data_inicio):
        metadados.data_inicio = data_inicio
    else:
        metadados.data_inicio = mes_atual()
        if data_inicio:
            avisos.append(f"`data_inicio` invalida ({data_inicio!r}); usando {metadados.data_inicio}.")
    return metadados


def _ler_parametros(bruto: Any, avisos: list[str]) -> Parametros:
    bruto = bruto if isinstance(bruto, dict) else {}
    if not bruto:
        avisos.append("bloco `parametros` ausente; todos os valores assumiram o default.")
    parametros = Parametros()

    for campo in fields(Parametros):
        if campo.name in (
            "funcao_vendedores",
            "funcao_aquisicao",
            "curva_maturacao",
            "funcao_custo_operacional",
            "sazonalidade_mensal",
        ):
            continue
        if campo.name not in bruto:
            continue
        valor_bruto = bruto[campo.name]
        atual = getattr(parametros, campo.name)
        if campo.name in PERCENTUAIS:
            valor = _percentual(valor_bruto, atual, campo.name, avisos)
        elif isinstance(atual, int):
            valor = _inteiro(valor_bruto, atual, campo.name, avisos)
        else:
            valor = _numero(valor_bruto, atual, campo.name, avisos)
        setattr(parametros, campo.name, valor)

    parametros.meses_simulados = max(1, min(600, parametros.meses_simulados))
    parametros.funcao_vendedores = _ler_funcao_vendedores(
        bruto.get("funcao_vendedores"), parametros.funcao_vendedores, avisos
    )
    parametros.funcao_aquisicao = _ler_funcao_aquisicao(bruto.get("funcao_aquisicao"), avisos)
    parametros.curva_maturacao = _ler_curva_maturacao(bruto.get("curva_maturacao"), avisos)
    parametros.funcao_custo_operacional = _ler_funcao_custo(
        bruto.get("funcao_custo_operacional"), parametros.funcao_custo_operacional, avisos
    )
    parametros.sazonalidade_mensal = _ler_sazonalidade(bruto.get("sazonalidade_mensal"), avisos)
    return parametros


def _ler_funcao_custo(bruto: Any, padrao: FuncaoCusto, avisos: list[str]) -> FuncaoCusto:
    if bruto is None:
        return padrao
    bruto = bruto if isinstance(bruto, dict) else {}
    funcao = FuncaoCusto()
    funcao.tipo = _tipo(bruto.get("tipo"), funcao.tipo, "funcao_custo_operacional.tipo", avisos)
    if isinstance(bruto.get("expressao"), str) and bruto["expressao"].strip():
        funcao.expressao = bruto["expressao"].strip()
    funcao.valores = []
    for item in bruto.get("valores") or []:
        if not isinstance(item, dict):
            continue
        mes = str(item.get("mes") or "")
        if not calendario.valido(mes):
            avisos.append(f"ponto de custo com mes invalido ({mes!r}) foi descartado.")
            continue
        funcao.valores.append(
            PontoCusto(mes=mes, custo=_numero(item.get("custo"), 0.0, "custo", avisos))
        )
    funcao.valores.sort(key=lambda ponto: ponto.mes)
    return funcao


def _ler_funcao_vendedores(bruto, padrao: FuncaoVendedores, avisos: list[str]) -> FuncaoVendedores:
    if bruto is None:
        return padrao
    bruto = bruto if isinstance(bruto, dict) else {}
    funcao = FuncaoVendedores()
    funcao.tipo = _tipo(bruto.get("tipo"), funcao.tipo, "funcao_vendedores.tipo", avisos)
    if isinstance(bruto.get("expressao"), str) and bruto["expressao"].strip():
        funcao.expressao = bruto["expressao"].strip()
    funcao.valores = []
    for item in bruto.get("valores") or []:
        if not isinstance(item, dict):
            continue
        mes = str(item.get("mes") or "")
        if not calendario.valido(mes):
            avisos.append(f"ponto de vendedores com mes invalido ({mes!r}) foi descartado.")
            continue
        quantidade = _inteiro(item.get("vendedores"), 0, "vendedores", avisos)
        funcao.valores.append(PontoVendedores(mes=mes, vendedores=max(0, quantidade)))
    funcao.valores.sort(key=lambda ponto: ponto.mes)
    return funcao


def _ler_funcao_aquisicao(bruto: Any, avisos: list[str]) -> FuncaoAquisicao:
    bruto = bruto if isinstance(bruto, dict) else {}
    funcao = FuncaoAquisicao()
    funcao.tipo = _tipo(bruto.get("tipo"), funcao.tipo, "funcao_aquisicao.tipo", avisos)
    if isinstance(bruto.get("expressao"), str) and bruto["expressao"].strip():
        funcao.expressao = bruto["expressao"].strip()
    funcao.valores = []
    for item in bruto.get("valores") or []:
        if not isinstance(item, dict):
            continue
        mes = str(item.get("mes") or "")
        if not calendario.valido(mes):
            avisos.append(f"ponto de aquisicao com mes invalido ({mes!r}) foi descartado.")
            continue
        quantidade = _inteiro(item.get("clinicas_adquiridas"), 0, "clinicas_adquiridas", avisos)
        funcao.valores.append(PontoAquisicao(mes=mes, clinicas_adquiridas=max(0, quantidade)))
    funcao.valores.sort(key=lambda ponto: ponto.mes)
    return funcao


def _ler_curva_maturacao(bruto: Any, avisos: list[str]) -> CurvaMaturacao:
    bruto = bruto if isinstance(bruto, dict) else {}
    curva = CurvaMaturacao()
    curva.tipo = _tipo(bruto.get("tipo"), curva.tipo, "curva_maturacao.tipo", avisos)
    if isinstance(bruto.get("expressao"), str) and bruto["expressao"].strip():
        curva.expressao = bruto["expressao"].strip()
    curva.valores = []
    for item in bruto.get("valores") or []:
        if not isinstance(item, dict):
            continue
        t = _inteiro(item.get("mes_desde_ativacao"), 0, "mes_desde_ativacao", avisos)
        if t < 1:
            avisos.append("ponto de maturacao com `mes_desde_ativacao` < 1 foi descartado.")
            continue
        ocupacao = _percentual(
            item.get("ocupacao_percentual"), 0.0, "ocupacao_percentual", avisos
        )
        curva.valores.append(PontoMaturacao(mes_desde_ativacao=t, ocupacao_percentual=ocupacao))
    curva.valores.sort(key=lambda ponto: ponto.mes_desde_ativacao)
    return curva


def _ler_sazonalidade(bruto: Any, avisos: list[str]) -> list[float]:
    padrao = Parametros().sazonalidade_mensal
    if bruto is None:
        return padrao
    if not isinstance(bruto, list) or len(bruto) != 12:
        avisos.append("`sazonalidade_mensal` precisa ter 12 valores; usando o default.")
        return padrao
    return [
        max(0.0, _numero(valor, 1.0, "sazonalidade_mensal", avisos)) for valor in bruto
    ]


def _ler_resultados(bruto: Any, avisos: list[str]) -> Resultados | None:
    if bruto is None:
        return None
    if not isinstance(bruto, dict):
        avisos.append("bloco `resultados` ilegivel; o app abriu em modo de re-simulacao.")
        return None
    series_brutas = bruto.get("series_mensais")
    if not isinstance(series_brutas, list) or not series_brutas:
        avisos.append("bloco `resultados` sem `series_mensais`; o app abriu em modo de re-simulacao.")
        return None

    series = [_preencher(MesResultado, item) for item in series_brutas if isinstance(item, dict)]
    if not series:
        return None
    kpis_brutos = bruto.get("kpis_agregados")
    kpis = _preencher(KpisAgregados, kpis_brutos if isinstance(kpis_brutos, dict) else {})
    return Resultados(series_mensais=series, kpis_agregados=kpis)


def _preencher(classe, bruto: dict):
    valores = {}
    for campo in fields(classe):
        valor = bruto.get(campo.name)
        if campo.name == "data":
            valores[campo.name] = str(valor or "")
        elif campo.name == "payback_meses":
            valores[campo.name] = int(valor) if isinstance(valor, (int, float)) else None
        elif isinstance(valor, bool) or not isinstance(valor, (int, float)):
            valores[campo.name] = 0 if campo.name in ("mes", "clinicas_novas") else 0.0
        else:
            valores[campo.name] = valor
    return classe(**valores)


# --------------------------------------------------------------------------- coercao


def _numero(valor: Any, padrao: float, campo: str, avisos: list[str]) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        avisos.append(f"`{campo}` nao e um numero; usando {padrao}.")
        return padrao
    if valor < 0:
        avisos.append(f"`{campo}` negativo ({valor}); ajustado para 0.")
        return 0.0
    return float(valor)


def _inteiro(valor: Any, padrao: int, campo: str, avisos: list[str]) -> int:
    numero = _numero(valor, float(padrao), campo, avisos)
    return round(numero)


def _percentual(valor: Any, padrao: float, campo: str, avisos: list[str]) -> float:
    numero = _numero(valor, padrao, campo, avisos)
    if numero > 1.0:
        avisos.append(f"`{campo}` acima de 100% ({numero}); ajustado para 1.0.")
        return 1.0
    return numero


def _tipo(valor: Any, padrao: str, campo: str, avisos: list[str]) -> str:
    if valor in (TIPO_LISTA, TIPO_EXPRESSAO):
        return valor
    if valor is not None:
        avisos.append(f"`{campo}` invalido ({valor!r}); usando {padrao!r}.")
    return padrao


# --------------------------------------------------------------------------- validacao


def validar(parametros: Parametros, metadados: Metadados) -> list[str]:
    """Erros que impedem a simulacao de rodar."""
    erros: list[str] = []
    if parametros.meses_simulados < 1:
        erros.append("`meses_simulados` precisa ser maior que zero.")
    if not calendario.valido(metadados.data_inicio):
        erros.append("`data_inicio` precisa estar no formato YYYY-MM.")

    vendedores = parametros.funcao_vendedores
    if vendedores.tipo == TIPO_EXPRESSAO:
        erro = expressoes.validar(vendedores.expressao, ("n",))
        if erro:
            erros.append(f"Expressao de vendedores: {erro}")
    elif calendario.valido(metadados.data_inicio):
        esperados = calendario.sequencia(metadados.data_inicio, parametros.meses_simulados)
        faltando = [mes for mes in esperados if mes not in {p.mes for p in vendedores.valores}]
        if faltando:
            erros.append(
                f"A lista de vendedores nao cobre {len(faltando)} mes(es) do horizonte "
                f"(a partir de {faltando[0]})."
            )

    funcao = parametros.funcao_aquisicao
    if funcao.tipo == TIPO_EXPRESSAO:
        erro = expressoes.validar(funcao.expressao, ("n", "v"))
        if erro:
            erros.append(f"Expressao de aquisicao: {erro}")
    elif calendario.valido(metadados.data_inicio):
        esperados = calendario.sequencia(metadados.data_inicio, parametros.meses_simulados)
        faltando = [mes for mes in esperados if mes not in {p.mes for p in funcao.valores}]
        if faltando:
            erros.append(
                f"A lista de aquisicao nao cobre {len(faltando)} mes(es) do horizonte "
                f"(a partir de {faltando[0]})."
            )

    custo = parametros.funcao_custo_operacional
    if custo.tipo == TIPO_EXPRESSAO:
        erro = expressoes.validar(custo.expressao, ("n", "a"))
        if erro:
            erros.append(f"Expressao de custo operacional: {erro}")
    elif calendario.valido(metadados.data_inicio):
        esperados = calendario.sequencia(metadados.data_inicio, parametros.meses_simulados)
        faltando = [mes for mes in esperados if mes not in {p.mes for p in custo.valores}]
        if faltando:
            erros.append(
                f"A lista de custo operacional nao cobre {len(faltando)} mes(es) do horizonte "
                f"(a partir de {faltando[0]})."
            )

    curva = parametros.curva_maturacao
    if curva.tipo == TIPO_EXPRESSAO:
        erro = expressoes.validar(curva.expressao, ("t",))
        if erro:
            erros.append(f"Expressao de maturacao: {erro}")
    else:
        if not curva.valores:
            erros.append("A curva de maturacao em lista precisa de ao menos um ponto.")
        else:
            esperados = list(range(1, len(curva.valores) + 1))
            if [ponto.mes_desde_ativacao for ponto in curva.valores] != esperados:
                erros.append(
                    "A curva de maturacao precisa comecar em 1 e seguir sem lacunas (1, 2, 3...)."
                )
    return erros
