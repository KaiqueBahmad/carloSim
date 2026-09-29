"""Exibicao dos resultados: KPIs, tabela mensal e graficos."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHeaderView,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..motor import Resultados
from .estilo import paleta
from .formato import mes_extenso, moeda, moeda_compacta, numero, percentual
from .graficos import PainelGraficos

COLUNAS = (
    ("Mês", "mes"),
    ("Data", "data"),
    ("Vend.", "vendedores"),
    ("Clínicas ativas", "clinicas_ativas"),
    ("Novas", "clinicas_novas"),
    ("Churn", "clinicas_churned"),
    ("Inadimplentes", "clinicas_inadimplentes"),
    ("Consultórios", "consultorios_ativos"),
    ("Ocupação", "ocupacao_media_percentual"),
    ("Atendimentos", "atendimentos_efetivos"),
    ("Volume", "volume_transacionado"),
    ("Rec. transacional", "receita_transacional"),
    ("Rec. mensalidade", "receita_mensalidade"),
    ("Receita total", "receita_total"),
    ("Inadimplência", "perda_inadimplencia"),
    ("Comissão vend.", "comissao_vendedor"),
    ("Por vendedor", "comissao_por_vendedor"),
    ("Custos", "custos_total"),
    ("Resultado", "resultado_liquido"),
    ("Acumulado", "resultado_acumulado"),
)

_MOEDA = {
    "volume_transacionado",
    "receita_transacional",
    "receita_mensalidade",
    "receita_total",
    "perda_inadimplencia",
    "comissao_vendedor",
    "comissao_por_vendedor",
    "custos_total",
    "resultado_liquido",
    "resultado_acumulado",
}


class Cartao(QFrame):
    def __init__(self, titulo: str):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setObjectName("cartaoKpi")
        self.rotulo_titulo = QLabel(titulo)
        self.rotulo_titulo.setObjectName("tituloKpi")
        self.rotulo_titulo.setWordWrap(True)
        self.rotulo_valor = QLabel("—")
        fonte = QFont()
        fonte.setPointSize(fonte.pointSize() + 5)
        fonte.setBold(True)
        self.rotulo_valor.setFont(fonte)
        self.rotulo_detalhe = QLabel("")
        self.rotulo_detalhe.setObjectName("detalheKpi")
        self.rotulo_detalhe.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)
        layout.addWidget(self.rotulo_titulo)
        layout.addWidget(self.rotulo_valor)
        layout.addWidget(self.rotulo_detalhe)

    def definir(self, valor: str, detalhe: str = "") -> None:
        self.rotulo_valor.setText(valor)
        self.rotulo_detalhe.setText(detalhe)


class PainelResultados(QTabWidget):
    def __init__(self, escuro: bool = False):
        super().__init__()
        self.cartoes: dict[str, Cartao] = {}
        self._cor_negativo = QColor(paleta(escuro)["negativo"])
        self.addTab(self._aba_resumo(), "Resumo")
        self.addTab(self._aba_tabela(), "Tabela mensal")
        self.graficos = PainelGraficos(escuro)
        rolagem = QScrollArea()
        rolagem.setWidget(self.graficos)
        rolagem.setWidgetResizable(True)
        self.addTab(rolagem, "Gráficos")

    def _aba_resumo(self) -> QWidget:
        titulos = [
            ("volume_transacionado_total", "Volume transacionado no período"),
            ("receita_total_periodo", "Receita total do período"),
            ("resultado_liquido_total", "Resultado líquido do período"),
            ("payback_meses", "Payback"),
            ("ticket_medio_realizado", "Ticket médio realizado"),
            ("clinicas_ativas_final", "Clínicas ativas no fim"),
            ("crescimento_medio_base_percentual", "Crescimento médio da base"),
            ("churn_acumulado_percentual", "Churn acumulado"),
            ("comissao_por_vendedor_total", "Ganho por vendedor"),
            ("ltv_medio", "LTV médio por clínica"),
            ("custos_total_periodo", "Custos do período"),
            ("perda_inadimplencia_total", "Perda por inadimplência"),
            ("comissao_vendedor_total", "Comissão dos vendedores"),
            ("atendimentos_efetivos_total", "Atendimentos efetivos"),
        ]
        conteudo = QWidget()
        coluna = QVBoxLayout(conteudo)
        coluna.setContentsMargins(12, 12, 12, 12)
        coluna.setSpacing(10)
        self.cabecalho = QLabel("—")
        self.cabecalho.setObjectName("cabecalhoResumo")
        self.cabecalho.setWordWrap(True)
        coluna.addWidget(self.cabecalho)
        grade = QGridLayout()
        grade.setSpacing(10)
        coluna.addLayout(grade)
        coluna.addStretch(1)
        for indice, (chave, titulo) in enumerate(titulos):
            cartao = Cartao(titulo)
            self.cartoes[chave] = cartao
            grade.addWidget(cartao, indice // 4, indice % 4)

        rolagem = QScrollArea()
        rolagem.setWidget(conteudo)
        rolagem.setWidgetResizable(True)
        return rolagem

    def _aba_tabela(self) -> QWidget:
        self.tabela = QTableWidget(0, len(COLUNAS))
        self.tabela.setHorizontalHeaderLabels([titulo for titulo, _ in COLUNAS])
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        return self.tabela

    # ------------------------------------------------------------------ render

    def definir_cabecalho(self, texto: str) -> None:
        self.cabecalho.setText(texto)

    def limpar(self) -> None:
        self.cabecalho.setText("—")
        self.tabela.setRowCount(0)
        for cartao in self.cartoes.values():
            cartao.definir("—")
        self.graficos.mostrar(None)

    def mostrar(self, resultados: Resultados) -> None:
        self._preencher_tabela(resultados)
        self._preencher_kpis(resultados)
        self.graficos.mostrar(resultados)

    def _preencher_tabela(self, resultados: Resultados) -> None:
        series = resultados.series_mensais
        self.tabela.setRowCount(len(series))
        for linha, mes in enumerate(series):
            for coluna, (_titulo, campo) in enumerate(COLUNAS):
                valor = getattr(mes, campo)
                if campo == "mes":
                    texto = str(valor)
                elif campo == "data":
                    texto = mes_extenso(valor)
                elif campo == "ocupacao_media_percentual":
                    texto = percentual(valor)
                elif campo in _MOEDA:
                    texto = moeda(valor, 0)
                else:
                    texto = numero(valor, 1)
                item = QTableWidgetItem(texto)
                item.setTextAlignment(
                    Qt.AlignVCenter | (Qt.AlignLeft if campo == "data" else Qt.AlignRight)
                )
                if campo in ("resultado_liquido", "resultado_acumulado") and valor < 0:
                    item.setForeground(self._cor_negativo)
                self.tabela.setItem(linha, coluna, item)

    def _preencher_kpis(self, resultados: Resultados) -> None:
        kpis = resultados.kpis_agregados
        total_meses = len(resultados.series_mensais)

        self.cartoes["volume_transacionado_total"].definir(
            moeda_compacta(kpis.volume_transacionado_total), f"em {total_meses} meses"
        )
        self.cartoes["receita_total_periodo"].definir(
            moeda_compacta(kpis.receita_total_periodo),
            f"transacional {moeda_compacta(kpis.receita_transacional_total)} · "
            f"mensalidade {moeda_compacta(kpis.receita_mensalidade_total)}",
        )
        self.cartoes["resultado_liquido_total"].definir(
            moeda_compacta(kpis.resultado_liquido_total), "receita − custos"
        )
        self.cartoes["payback_meses"].definir(
            f"mês {kpis.payback_meses}" if kpis.payback_meses else "não atingido",
            "1º mês com resultado acumulado positivo",
        )
        self.cartoes["ticket_medio_realizado"].definir(
            moeda(kpis.ticket_medio_realizado), "volume ÷ atendimentos efetivos"
        )
        self.cartoes["clinicas_ativas_final"].definir(
            numero(kpis.clinicas_ativas_final, 0),
            f"{numero(kpis.clinicas_adquiridas_total, 0)} adquiridas no período",
        )
        self.cartoes["crescimento_medio_base_percentual"].definir(
            percentual(kpis.crescimento_medio_base_percentual), "média mensal composta"
        )
        self.cartoes["churn_acumulado_percentual"].definir(
            percentual(kpis.churn_acumulado_percentual),
            f"{numero(kpis.clinicas_churned_total, 0)} clínicas perdidas",
        )
        self.cartoes["comissao_por_vendedor_total"].definir(
            moeda_compacta(kpis.comissao_por_vendedor_total),
            "quem ficou o período inteiro",
        )
        self.cartoes["ltv_medio"].definir(
            moeda_compacta(kpis.ltv_medio),
            "receita/clínica/mês × vida média (1 ÷ [churn + inadimplência])",
        )
        self.cartoes["custos_total_periodo"].definir(
            moeda_compacta(kpis.custos_total_periodo),
            "operacional + processamento + inadimplência + comissão",
        )
        self.cartoes["comissao_vendedor_total"].definir(
            moeda_compacta(kpis.comissao_vendedor_total),
            "sobre a receita recebida",
        )
        self.cartoes["perda_inadimplencia_total"].definir(
            moeda_compacta(kpis.perda_inadimplencia_total),
            f"{numero(kpis.clinicas_inadimplentes_total, 0)} clínicas perderam o acesso",
        )
        self.cartoes["atendimentos_efetivos_total"].definir(
            numero(kpis.atendimentos_efetivos_total, 0), "no período"
        )
