"""Tema da janela: correcao da paleta do Qt e folha de estilo por tema.

Alguns temas GTK escuros chegam ao Qt com `Window`, `Base`, `Mid` e `Dark`
praticamente na mesma cor (no Flat-Remix-Darkest, tudo entre #070707 e #090909).
O Fusion desenha bordas e campos com esses papeis, entao o formulario inteiro
some. Quando a paleta chega degenerada assim, trocamos por uma paleta escura
consistente antes de montar a janela.
"""

from string import Template

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette

PALETA_CLARA = {
    "texto_secundario": "#586471",
    "borda": "#c8d0d8",
    "cartao": "#ffffff",
    "faixa_fundo": "#fff4d6",
    "faixa_borda": "#e0be5e",
    "faixa_texto": "#5c4300",
    "erro_borda": "#c0392b",
    "erro_fundo": "#fdecea",
    "erro_texto": "#8a1f16",
    "negativo": "#c0392b",
    "realce": "#2f6fb0",
    "campo": "#ffffff",
}

PALETA_ESCURA = {
    "texto_secundario": "#aab5c1",
    "borda": "#454d57",
    "cartao": "#2f343b",
    "faixa_fundo": "#3b3320",
    "faixa_borda": "#8a7330",
    "faixa_texto": "#f2dc9b",
    "erro_borda": "#e06c5f",
    "erro_fundo": "#4a2925",
    "erro_texto": "#ffb9ae",
    "negativo": "#ff8577",
    "realce": "#6ea8dc",
    "campo": "#14171c",
}

_CORES_QT_ESCURAS = {
    QPalette.Window: "#282c32",
    QPalette.WindowText: "#e8ecf0",
    QPalette.Base: "#14171c",
    QPalette.AlternateBase: "#1b1f25",
    QPalette.Text: "#e8ecf0",
    QPalette.Button: "#31363d",
    QPalette.ButtonText: "#e8ecf0",
    QPalette.ToolTipBase: "#31363d",
    QPalette.ToolTipText: "#e8ecf0",
    QPalette.BrightText: "#ff8577",
    QPalette.Light: "#5e6773",
    QPalette.Midlight: "#48505b",
    QPalette.Mid: "#525b67",
    QPalette.Dark: "#171b20",
    QPalette.Shadow: "#101317",
    QPalette.Highlight: "#3d7cc0",
    QPalette.HighlightedText: "#ffffff",
    QPalette.PlaceholderText: "#8b96a2",
}

_MODELO = Template("""
QGroupBox {
    font-weight: 600;
    border: 1px solid $borda;
    border-radius: 6px;
    margin-top: 14px;
    padding: 12px 10px 10px 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}
QLabel#ajuda, QLabel#detalheKpi {
    color: $texto_secundario;
    font-size: 11px;
}
QLabel#cabecalhoResumo {
    font-size: 15px;
    padding: 2px 2px 6px 2px;
}
QLabel#tituloKpi {
    color: $texto_secundario;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.4px;
}
QFrame#cartaoKpi {
    border: 1px solid $borda;
    border-radius: 8px;
    background: $cartao;
}
QFrame#faixaVisualizacao {
    background: $faixa_fundo;
    border-bottom: 1px solid $faixa_borda;
}
QFrame#faixaVisualizacao QLabel {
    color: $faixa_texto;
}
QLineEdit[invalido="true"] {
    border: 1px solid $erro_borda;
    background: $erro_fundo;
    color: $erro_texto;
}
QRadioButton::indicator {
    width: 14px;
    height: 14px;
    border-radius: 7px;
    border: 1px solid $borda;
    background: $campo;
}
QRadioButton::indicator:checked {
    border: 1px solid $realce;
    background: $realce;
}
QToolBar {
    padding: 6px;
    spacing: 6px;
    border-bottom: 1px solid $borda;
}
QHeaderView::section {
    padding: 4px 8px;
    border: none;
    border-bottom: 1px solid $borda;
    border-right: 1px solid $borda;
}
""")


def paleta(escuro: bool) -> dict[str, str]:
    return PALETA_ESCURA if escuro else PALETA_CLARA


def folha(escuro: bool) -> str:
    return _MODELO.substitute(paleta(escuro))


def _degenerada(palette: QPalette) -> bool:
    """Paleta em que fundo, campo e bordas sao a mesma cor — nada fica visivel."""
    janela = palette.color(QPalette.Window).lightness()
    base = palette.color(QPalette.Base).lightness()
    mid = palette.color(QPalette.Mid).lightness()
    return abs(janela - base) < 12 and abs(janela - mid) < 12


def _paleta_escura() -> QPalette:
    palette = QPalette()
    for papel, cor in _CORES_QT_ESCURAS.items():
        palette.setColor(papel, QColor(cor))
    for papel in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, papel, QColor("#79828d"))
    palette.setColor(QPalette.Disabled, QPalette.Base, QColor("#232830"))
    return palette


def aplicar_tema(aplicacao) -> bool:
    """Devolve se o tema e escuro, corrigindo a paleta quando ela vem degenerada."""
    escuro = (
        QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
        or aplicacao.palette().color(QPalette.Window).lightness() < 128
    )
    if escuro and _degenerada(aplicacao.palette()):
        aplicacao.setPalette(_paleta_escura())
    return escuro
