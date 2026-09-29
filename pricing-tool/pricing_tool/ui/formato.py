"""Formatacao pt-BR para exibicao (a persistencia usa sempre numeros crus)."""

from ..parametros import MESES_ABREVIADOS


def _br(texto: str) -> str:
    return texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def numero(valor: float, casas: int = 1) -> str:
    return _br(f"{valor:,.{casas}f}")


def moeda(valor: float, casas: int = 2) -> str:
    sinal = "-" if valor < 0 else ""
    return f"{sinal}R$ {_br(f'{abs(valor):,.{casas}f}')}"


def moeda_compacta(valor: float) -> str:
    absoluto = abs(valor)
    for limite, sufixo in ((1e9, " bi"), (1e6, " mi"), (1e3, " mil")):
        if absoluto >= limite:
            return f"{'-' if valor < 0 else ''}R$ {_br(f'{absoluto / limite:,.1f}')}{sufixo}"
    return moeda(valor, 0)


def percentual(fracao: float, casas: int = 1) -> str:
    return _br(f"{fracao * 100:,.{casas}f}") + "%"


def mes_extenso(mes_iso: str) -> str:
    """`2026-09` vira `set/2026`."""
    try:
        ano, mes = mes_iso.split("-")
        return f"{MESES_ABREVIADOS[int(mes) - 1]}/{ano}"
    except (ValueError, IndexError):
        return mes_iso
