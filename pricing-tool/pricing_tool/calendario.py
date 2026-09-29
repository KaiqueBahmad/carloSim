"""Aritmetica de meses no formato ISO 8601 `YYYY-MM`."""

import re

_FORMATO = re.compile(r"^(\d{4})-(\d{2})$")


def valido(mes_iso: str) -> bool:
    encontrado = _FORMATO.match(str(mes_iso or ""))
    return bool(encontrado) and 1 <= int(encontrado.group(2)) <= 12


def partes(mes_iso: str) -> tuple[int, int]:
    encontrado = _FORMATO.match(mes_iso)
    if not encontrado or not 1 <= int(encontrado.group(2)) <= 12:
        raise ValueError(f"mes invalido: {mes_iso!r} (esperado YYYY-MM)")
    return int(encontrado.group(1)), int(encontrado.group(2))


def somar(mes_iso: str, meses: int) -> str:
    ano, mes = partes(mes_iso)
    total = (ano * 12 + (mes - 1)) + meses
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def indice_no_ano(mes_iso: str) -> int:
    """0 para janeiro, 11 para dezembro — indice na lista de sazonalidade."""
    return partes(mes_iso)[1] - 1


def sequencia(mes_inicio: str, quantidade: int) -> list[str]:
    return [somar(mes_inicio, i) for i in range(max(0, quantidade))]
