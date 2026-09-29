"""Tabelas de entrada das listas de aquisicao, comerciais, custo e escopo."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import calendario
from ..parametros import PontoAquisicao, PontoComerciais, PontoCusto, PontoEscopo
from .campos import CampoInteiro, CampoMoeda, CampoPercentual, RotuloAjuda
from .formato import mes_extenso


def _tabela(colunas: list[str]) -> QTableWidget:
    tabela = QTableWidget(0, len(colunas))
    tabela.setHorizontalHeaderLabels(colunas)
    tabela.verticalHeader().setVisible(False)
    tabela.setEditTriggers(QAbstractItemView.NoEditTriggers)
    tabela.setSelectionMode(QAbstractItemView.NoSelection)
    tabela.setAlternatingRowColors(True)
    cabecalho = tabela.horizontalHeader()
    cabecalho.setSectionResizeMode(0, QHeaderView.Stretch)
    cabecalho.setSectionResizeMode(1, QHeaderView.ResizeToContents)
    return tabela


def _rotulo(texto: str) -> QTableWidgetItem:
    item = QTableWidgetItem(texto)
    item.setFlags(Qt.ItemIsEnabled)
    return item


class TabelaPorMes(QWidget):
    """Uma linha por mes calendario do horizonte — sem lacunas, por construcao."""

    alterado = Signal()

    def __init__(self, titulo_valor: str, rotulo_replicar: str):
        super().__init__()
        self._silencioso = False
        self.tabela = _tabela(["Mês", titulo_valor])
        self.tabela.setMinimumHeight(180)

        self.replicar = self._criar_campo()
        botao = QPushButton("Aplicar a todos")
        botao.clicked.connect(self._aplicar_a_todos)

        rodape = QHBoxLayout()
        rodape.setContentsMargins(0, 0, 0, 0)
        rodape.addWidget(QLabel(rotulo_replicar))
        rodape.addWidget(self.replicar)
        rodape.addWidget(botao)
        rodape.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.tabela)
        layout.addLayout(rodape)

    # ------------------------------------------------------------ subclasses
    def _criar_campo(self):
        raise NotImplementedError

    def _ponto(self, mes: str, valor):
        raise NotImplementedError

    def _valor(self, ponto):
        raise NotImplementedError

    # ------------------------------------------------------------ comum
    def sincronizar(self, mes_inicio: str, meses: int) -> None:
        """Refaz as linhas para o horizonte atual, preservando o que ja foi digitado."""
        atuais = {ponto.mes: self._valor(ponto) for ponto in self.valores()}
        padrao = atuais.get(mes_inicio, self.replicar.value() if not atuais else 0)
        self._silencioso = True
        self.tabela.setRowCount(0)
        for mes in calendario.sequencia(mes_inicio, meses):
            self._inserir(mes, atuais.get(mes, padrao))
        self._silencioso = False

    def _inserir(self, mes: str, valor) -> None:
        linha = self.tabela.rowCount()
        self.tabela.insertRow(linha)
        item = _rotulo(mes_extenso(mes))
        item.setData(Qt.UserRole, mes)
        self.tabela.setItem(linha, 0, item)
        campo = self._criar_campo()
        campo.setValue(valor)
        campo.valueChanged.connect(self._emitir)
        self.tabela.setCellWidget(linha, 1, campo)

    def _emitir(self) -> None:
        if not self._silencioso:
            self.alterado.emit()

    def _aplicar_a_todos(self) -> None:
        self._silencioso = True
        for linha in range(self.tabela.rowCount()):
            self.tabela.cellWidget(linha, 1).setValue(self.replicar.value())
        self._silencioso = False
        self.alterado.emit()

    def valores(self) -> list:
        pontos = []
        for linha in range(self.tabela.rowCount()):
            item = self.tabela.item(linha, 0)
            campo = self.tabela.cellWidget(linha, 1)
            if item and campo:
                pontos.append(self._ponto(item.data(Qt.UserRole), campo.value()))
        return pontos

    def definir(self, valores: list, mes_inicio: str, meses: int) -> None:
        self._silencioso = True
        self.tabela.setRowCount(0)
        importados = {ponto.mes: self._valor(ponto) for ponto in valores}
        for mes in calendario.sequencia(mes_inicio, meses):
            self._inserir(mes, importados.get(mes, 0))
        self._silencioso = False


class TabelaAquisicao(TabelaPorMes):
    def __init__(self):
        super().__init__("Clientes adquiridos", "Preencher todos os meses com")
        self.replicar.setValue(2)

    def _criar_campo(self):
        return CampoInteiro(0, 10_000)

    def _ponto(self, mes: str, valor):
        return PontoAquisicao(mes=mes, clientes_adquiridos=int(valor))

    def _valor(self, ponto):
        return ponto.clientes_adquiridos


class TabelaComerciais(TabelaPorMes):
    def __init__(self):
        super().__init__("Comerciais ativos", "Preencher todos os meses com")
        self.replicar.setValue(2)

    def _criar_campo(self):
        return CampoInteiro(0, 1_000)

    def _ponto(self, mes: str, valor):
        return PontoComerciais(mes=mes, comerciais=int(valor))

    def _valor(self, ponto):
        return ponto.comerciais


class TabelaCusto(TabelaPorMes):
    def __init__(self):
        super().__init__("Custo de estrutura", "Preencher todos os meses com")
        self.replicar.setValue(4_500.0)

    def _criar_campo(self):
        return CampoMoeda(passo=500.0)

    def _ponto(self, mes: str, valor):
        return PontoCusto(mes=mes, custo=float(valor))

    def _valor(self, ponto):
        return ponto.custo


class TabelaEscopo(QWidget):
    """Pontos 1..k sem lacunas; o ultimo vale como escopo de regime."""

    alterado = Signal()

    def __init__(self):
        super().__init__()
        self._silencioso = False
        self.tabela = _tabela(["Mês desde a ativação", "Escopo"])
        self.tabela.setMinimumHeight(180)

        adicionar = QPushButton("+ ponto")
        adicionar.clicked.connect(self._adicionar)
        remover = QPushButton("− ponto")
        remover.clicked.connect(self._remover)

        rodape = QHBoxLayout()
        rodape.setContentsMargins(0, 0, 0, 0)
        rodape.addWidget(adicionar)
        rodape.addWidget(remover)
        rodape.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.tabela)
        layout.addLayout(rodape)
        layout.addWidget(RotuloAjuda("O último ponto vale como escopo de regime, mantido nos meses seguintes."))

    def _inserir(self, escopo: float) -> None:
        linha = self.tabela.rowCount()
        self.tabela.insertRow(linha)
        self.tabela.setItem(linha, 0, _rotulo(f"Mês {linha + 1}"))
        campo = CampoPercentual(casas=1, passo=1.0)
        campo.definir_fracao(escopo)
        campo.valueChanged.connect(self._emitir)
        self.tabela.setCellWidget(linha, 1, campo)

    def _emitir(self) -> None:
        if not self._silencioso:
            self.alterado.emit()

    def _adicionar(self) -> None:
        ultimo = self.valores()[-1].escopo_percentual if self.tabela.rowCount() else 0.05
        self._inserir(ultimo)
        self.alterado.emit()

    def _remover(self) -> None:
        if self.tabela.rowCount() > 1:
            self.tabela.removeRow(self.tabela.rowCount() - 1)
            self.alterado.emit()

    def valores(self) -> list[PontoEscopo]:
        pontos = []
        for linha in range(self.tabela.rowCount()):
            campo = self.tabela.cellWidget(linha, 1)
            if campo:
                pontos.append(
                    PontoEscopo(mes_desde_ativacao=linha + 1, escopo_percentual=campo.fracao())
                )
        return pontos

    def definir(self, valores: list[PontoEscopo]) -> None:
        self._silencioso = True
        self.tabela.setRowCount(0)
        for ponto in valores:
            self._inserir(ponto.escopo_percentual)
        if not self.tabela.rowCount():
            self._inserir(0.05)
        self._silencioso = False
