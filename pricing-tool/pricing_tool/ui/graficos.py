"""Graficos de evolucao: carteira, receita, equipe e resultado acumulado."""

from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ..motor import Resultados


class _Grafico(QChartView):
    """Os eixos sao criados uma unica vez: recria-los a cada desenho deixa rastros na cena."""

    def __init__(self, titulo: str, titulo_y: str, escuro: bool):
        self._chart = QChart()
        self._chart.setTitle(titulo)
        self._chart.setTheme(QChart.ChartThemeDark if escuro else QChart.ChartThemeLight)
        self._chart.setBackgroundVisible(False)
        self._chart.legend().setAlignment(Qt.AlignBottom)

        self._eixo_x = QValueAxis()
        self._eixo_x.setTitleText("Mês da simulação")
        self._eixo_x.setLabelFormat("%d")
        self._eixo_y = QValueAxis()
        self._eixo_y.setTitleText(titulo_y)
        self._eixo_y.setTickCount(6)
        self._chart.addAxis(self._eixo_x, Qt.AlignBottom)
        self._chart.addAxis(self._eixo_y, Qt.AlignLeft)

        super().__init__(self._chart)
        self.setRenderHint(QPainter.Antialiasing)
        self.setMinimumHeight(260)

    def desenhar(self, series: list[tuple[str, list[tuple[float, float]]]], meses: int) -> None:
        self._chart.removeAllSeries()
        if not meses:
            return

        self._eixo_x.setRange(1, max(1, meses))
        self._eixo_x.setTickCount(min(13, max(2, meses)))

        minimo = 0.0
        maximo = 0.0
        for _nome, pontos in series:
            for _x, y in pontos:
                minimo = min(minimo, y)
                maximo = max(maximo, y)
        if maximo == minimo:
            maximo = minimo + 1.0

        folga = (maximo - minimo) * 0.08
        self._eixo_y.setLabelFormat("%.0f" if maximo - minimo >= 20 else "%.1f")
        self._eixo_y.setRange(minimo if minimo >= 0 else minimo - folga, maximo + folga)
        self._eixo_y.applyNiceNumbers()

        for nome, pontos in series:
            serie = QLineSeries()
            serie.setName(nome)
            for x, y in pontos:
                serie.append(float(x), float(y))
            self._chart.addSeries(serie)
            serie.attachAxis(self._eixo_x)
            serie.attachAxis(self._eixo_y)


class PainelGraficos(QWidget):
    def __init__(self, escuro: bool = False):
        super().__init__()
        self.carteira = _Grafico("Carteira de clientes", "clientes", escuro)
        self.receita = _Grafico("Receita e custos", "R$ mil", escuro)
        self.equipe = _Grafico("Equipe (degraus de capacidade)", "profissionais", escuro)
        self.acumulado = _Grafico("Resultado acumulado", "R$ mil", escuro)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.carteira)
        layout.addWidget(self.receita)
        layout.addWidget(self.equipe)
        layout.addWidget(self.acumulado)

    def mostrar(self, resultados: Resultados | None) -> None:
        series = resultados.series_mensais if resultados else []
        meses = len(series)

        self.carteira.desenhar(
            [
                ("Ativos", [(mes.mes, mes.clientes_ativos) for mes in series]),
                ("Novos", [(mes.mes, mes.clientes_novos) for mes in series]),
                ("Churn", [(mes.mes, mes.clientes_churned) for mes in series]),
                ("Inadimplentes", [(mes.mes, mes.clientes_inadimplentes) for mes in series]),
            ],
            meses,
        )
        self.receita.desenhar(
            [
                ("Receita total", [(mes.mes, mes.receita_total / 1000) for mes in series]),
                ("Retainer", [(mes.mes, mes.receita_retainer / 1000) for mes in series]),
                ("Fee de mídia", [(mes.mes, mes.receita_midia / 1000) for mes in series]),
                ("Custos", [(mes.mes, mes.custos_total / 1000) for mes in series]),
                ("Equipe", [(mes.mes, mes.custo_equipe / 1000) for mes in series]),
            ],
            meses,
        )
        self.equipe.desenhar(
            [
                ("Equipe", [(mes.mes, mes.equipe) for mes in series]),
                ("Comerciais", [(mes.mes, mes.comerciais) for mes in series]),
            ],
            meses,
        )
        self.acumulado.desenhar(
            [
                ("Acumulado", [(mes.mes, mes.resultado_acumulado / 1000) for mes in series]),
                ("Zero", [(mes.mes, 0.0) for mes in series]),
            ],
            meses,
        )
