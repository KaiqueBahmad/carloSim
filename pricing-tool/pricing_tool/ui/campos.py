"""Campos estruturados: fora dos campos `expressao`, nada e texto livre."""

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QDateEdit,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from .. import calendario, expressoes


class CampoMoeda(QDoubleSpinBox):
    def __init__(self, maximo: float = 1e9, passo: float = 10.0):
        super().__init__()
        self.setPrefix("R$ ")
        self.setDecimals(2)
        self.setRange(0.0, maximo)
        self.setSingleStep(passo)
        self.setGroupSeparatorShown(True)
        self.setAlignment(Qt.AlignRight)


class CampoDecimal(QDoubleSpinBox):
    def __init__(self, minimo=0.0, maximo=1e6, passo=0.5, casas=2, sufixo=""):
        super().__init__()
        self.setDecimals(casas)
        self.setRange(minimo, maximo)
        self.setSingleStep(passo)
        self.setAlignment(Qt.AlignRight)
        if sufixo:
            self.setSuffix(sufixo)


class CampoInteiro(QSpinBox):
    def __init__(self, minimo=0, maximo=1000, sufixo=""):
        super().__init__()
        self.setRange(minimo, maximo)
        self.setAlignment(Qt.AlignRight)
        if sufixo:
            self.setSuffix(sufixo)


class CampoPercentual(QDoubleSpinBox):
    """Exibe 0-100%, guarda a fracao 0.0-1.0 usada no JSON e no motor."""

    def __init__(self, casas: int = 2, passo: float = 0.5):
        super().__init__()
        self.setSuffix(" %")
        self.setDecimals(casas)
        self.setRange(0.0, 100.0)
        self.setSingleStep(passo)
        self.setAlignment(Qt.AlignRight)

    def fracao(self) -> float:
        return self.value() / 100.0

    def definir_fracao(self, fracao: float) -> None:
        self.setValue(max(0.0, min(1.0, float(fracao))) * 100.0)


class SeletorMes(QDateEdit):
    """Seletor de mes/ano; o dia e sempre 1 e nunca aparece."""

    def __init__(self):
        super().__init__()
        self.setDisplayFormat("MM/yyyy")
        self.setCalendarPopup(True)
        self.setDateRange(QDate(2000, 1, 1), QDate(2099, 12, 1))
        self.setAlignment(Qt.AlignRight)

    def mes_iso(self) -> str:
        data = self.date()
        return f"{data.year():04d}-{data.month():02d}"

    def definir_mes_iso(self, mes_iso: str) -> None:
        if calendario.valido(mes_iso):
            ano, mes = calendario.partes(mes_iso)
            self.setDate(QDate(ano, mes, 1))


class CampoExpressao(QWidget):
    """Unico campo de texto livre do app — com validacao expr-eval ao vivo."""

    alterado = Signal()

    def __init__(self, variaveis: tuple[str, ...], exemplo: str):
        super().__init__()
        self.variaveis = variaveis
        self.entrada = QLineEdit()
        self.entrada.setPlaceholderText(exemplo)
        self.entrada.setClearButtonEnabled(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.entrada, 1)

        self.entrada.textChanged.connect(self._revalidar)
        self.entrada.textChanged.connect(self.alterado)
        self._revalidar()

    def texto(self) -> str:
        return self.entrada.text().strip()

    def definir_texto(self, texto: str) -> None:
        self.entrada.setText(texto or "")

    def erro(self) -> str | None:
        return expressoes.validar(self.texto(), self.variaveis)

    def _revalidar(self) -> None:
        erro = self.erro()
        self.entrada.setProperty("invalido", bool(erro))
        self.entrada.setToolTip(erro or f"Variavel disponivel: {', '.join(self.variaveis)}")
        self.entrada.style().unpolish(self.entrada)
        self.entrada.style().polish(self.entrada)


class RotuloAjuda(QLabel):
    def __init__(self, texto: str):
        super().__init__(texto)
        self.setWordWrap(True)
        self.setObjectName("ajuda")
