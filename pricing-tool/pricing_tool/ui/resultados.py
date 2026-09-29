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
    ("Comerc.", "comerciais"),
    ("Clientes ativos", "clientes_ativos"),
    ("Novos", "clientes_novos"),
    ("Churn", "clientes_churned"),
    ("Inadimplentes", "clientes_inadimplentes"),
    ("Verba gerenciada", "verba_midia_gerenciada"),
    ("Horas", "horas_demandadas"),
    ("Equipe", "equipe"),
    ("Utilização", "utilizacao_equipe_percentual"),
    ("Rec. retainer", "receita_retainer"),
    ("Rec. mídia", "receita_midia"),
    ("Rec. setup", "receita_setup"),
    ("Receita total", "receita_total"),
    ("Custo equipe", "custo_equipe"),
    ("Estrutura", "custo_estrutura"),
    ("Terceiros", "custo_terceiros"),
    ("Impostos", "impostos"),
    ("Inadimplência", "perda_inadimplencia"),
    ("Comissão", "comissao_comercial"),
    ("Por comercial", "comissao_por_comercial"),
    ("Custos", "custos_total"),
    ("Resultado", "resultado_liquido"),
    ("Acumulado", "resultado_acumulado"),
)

_MOEDA = {
    "verba_midia_gerenciada",
    "receita_retainer",
    "receita_midia",
    "receita_setup",
    "receita_total",
    "custo_equipe",
    "custo_estrutura",
    "custo_terceiros",
    "impostos",
    "perda_inadimplencia",
    "comissao_comercial",
    "comissao_por_comercial",
    "custos_total",
    "resultado_liquido",
    "resultado_acumulado",
}

_INTEIRO = {"mes", "comerciais", "clientes_novos", "equipe"}


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
            ("verba_midia_total", "Verba de mídia gerenciada"),
            ("receita_total_periodo", "Receita total do período"),
            ("resultado_liquido_total", "Resultado líquido do período"),
            ("margem_liquida_percentual", "Margem líquida"),
            ("payback_meses", "Payback"),
            ("receita_media_por_cliente_mes", "Receita média por cliente/mês"),
            ("clientes_ativos_final", "Clientes ativos no fim"),
            ("equipe_final", "Equipe no fim"),
            ("utilizacao_media_percentual", "Utilização média da equipe"),
            ("crescimento_medio_base_percentual", "Crescimento médio da carteira"),
            ("churn_acumulado_percentual", "Churn acumulado"),
            ("ltv_medio", "LTV médio por cliente"),
            ("custo_equipe_total", "Custo da equipe"),
            ("custos_total_periodo", "Custos do período"),
            ("perda_inadimplencia_total", "Perda por inadimplência"),
            ("comissao_comercial_total", "Comissão comercial"),
            ("comissao_por_comercial_total", "Ganho por comercial"),
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
                if campo == "data":
                    texto = mes_extenso(valor)
                elif campo in _INTEIRO:
                    texto = str(int(valor))
                elif campo == "utilizacao_equipe_percentual":
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

        self.cartoes["verba_midia_total"].definir(
            moeda_compacta(kpis.verba_midia_total), f"em {total_meses} meses · não é receita"
        )
        self.cartoes["receita_total_periodo"].definir(
            moeda_compacta(kpis.receita_total_periodo),
            f"retainer {moeda_compacta(kpis.receita_retainer_total)} · "
            f"mídia {moeda_compacta(kpis.receita_midia_total)} · "
            f"setup {moeda_compacta(kpis.receita_setup_total)}",
        )
        self.cartoes["resultado_liquido_total"].definir(
            moeda_compacta(kpis.resultado_liquido_total), "receita − custos"
        )
        self.cartoes["margem_liquida_percentual"].definir(
            percentual(kpis.margem_liquida_percentual), "resultado ÷ receita"
        )
        self.cartoes["payback_meses"].definir(
            f"mês {kpis.payback_meses}" if kpis.payback_meses else "não atingido",
            "1º mês com resultado acumulado positivo",
        )
        self.cartoes["receita_media_por_cliente_mes"].definir(
            moeda(kpis.receita_media_por_cliente_mes, 0), "receita ÷ clientes ativos/mês"
        )
        self.cartoes["clientes_ativos_final"].definir(
            numero(kpis.clientes_ativos_final, 0),
            f"{numero(kpis.clientes_adquiridos_total, 0)} conquistados no período",
        )
        self.cartoes["equipe_final"].definir(
            numero(kpis.equipe_final, 0), "profissionais no último mês"
        )
        self.cartoes["utilizacao_media_percentual"].definir(
            percentual(kpis.utilizacao_media_percentual), "horas demandadas ÷ horas produtivas"
        )
        self.cartoes["crescimento_medio_base_percentual"].definir(
            percentual(kpis.crescimento_medio_base_percentual), "média mensal composta"
        )
        self.cartoes["churn_acumulado_percentual"].definir(
            percentual(kpis.churn_acumulado_percentual),
            f"{numero(kpis.clientes_churned_total, 0)} clientes perdidos",
        )
        self.cartoes["ltv_medio"].definir(
            moeda_compacta(kpis.ltv_medio),
            "receita/cliente/mês × vida média (1 ÷ [churn + inadimplência])",
        )
        self.cartoes["custo_equipe_total"].definir(
            moeda_compacta(kpis.custo_equipe_total), "maior custo da agência"
        )
        self.cartoes["custos_total_periodo"].definir(
            moeda_compacta(kpis.custos_total_periodo),
            "equipe + estrutura + terceiros + impostos + inadimplência + comissão",
        )
        self.cartoes["perda_inadimplencia_total"].definir(
            moeda_compacta(kpis.perda_inadimplencia_total),
            f"{numero(kpis.clientes_inadimplentes_total, 0)} contratos encerrados",
        )
        self.cartoes["comissao_comercial_total"].definir(
            moeda_compacta(kpis.comissao_comercial_total),
            "sobre a receita recebida",
        )
        self.cartoes["comissao_por_comercial_total"].definir(
            moeda_compacta(kpis.comissao_por_comercial_total),
            "quem ficou o período inteiro",
        )
