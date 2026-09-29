"""Avaliacao de expressoes no padrao expr-eval."""

import math

from py_expression_eval import Parser

_parser = Parser()


class ErroExpressao(ValueError):
    """Sintaxe invalida ou variavel desconhecida em um campo `expressao`."""


class Expressao:
    """Expressao compilada, restrita as variaveis do seu dominio."""

    def __init__(self, texto: str, variaveis_permitidas: tuple[str, ...]):
        self.texto = texto
        self.variaveis_permitidas = variaveis_permitidas
        try:
            self._compilada = _parser.parse(texto)
        except Exception as erro:  # py-expression-eval lanca Exception nua
            raise ErroExpressao(str(erro)) from erro
        desconhecidas = sorted(set(self._compilada.variables()) - set(variaveis_permitidas))
        if desconhecidas:
            permitidas = ", ".join(variaveis_permitidas)
            raise ErroExpressao(
                f"variavel desconhecida: {', '.join(desconhecidas)} (disponivel: {permitidas})"
            )

    def avaliar(self, **variaveis: float) -> float:
        try:
            valor = self._compilada.evaluate(variaveis)
        except Exception as erro:
            raise ErroExpressao(str(erro)) from erro
        if not isinstance(valor, (int, float)) or isinstance(valor, bool):
            raise ErroExpressao("a expressao deve resultar em um numero")
        return float(valor)


def compilar(texto: str, variaveis_permitidas: tuple[str, ...]) -> Expressao:
    return Expressao(texto, variaveis_permitidas)


def validar(texto: str, variaveis_permitidas: tuple[str, ...]) -> str | None:
    """Retorna a mensagem de erro da expressao, ou None se ela for valida."""
    try:
        compilar(texto, variaveis_permitidas)
    except ErroExpressao as erro:
        return str(erro)
    return None


def normalizar_aquisicao(valor: float) -> int:
    """Dominio inteiro >= 0: negativo vira 0, fracionario arredonda."""
    if not math.isfinite(valor) or valor <= 0:
        return 0
    return math.floor(valor + 0.5)  # metade sempre para cima


def normalizar_custo(valor: float) -> float:
    """Dominio R$ >= 0, sem teto: negativo ou invalido vira 0."""
    if not math.isfinite(valor) or valor < 0.0:
        return 0.0
    return valor


def normalizar_escopo(valor: float) -> float:
    """Dominio 0.0 a 1.0, com clamp nas duas pontas."""
    if not math.isfinite(valor) or valor < 0.0:
        return 0.0
    return min(1.0, valor)
