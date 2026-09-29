"""Modo 'calcular sorte': roda a simulacao com dados N vezes e conta acertos."""

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QProgressDialog,
    QVBoxLayout,
)

from ..motor import Sorte, calcular_sorte
from .campos import CampoInteiro, CampoMoeda, RotuloAjuda
from .formato import moeda, moeda_compacta


class DialogoMeta(QDialog):
    """Pergunta as duas metas — acumulado e ultimo mes — e quantas rodadas simular."""

    def __init__(self, parent, deterministico: float, deterministico_resultado: float, meses: int):
        super().__init__(parent)
        self.setWindowTitle("Calcular sorte")
        self.setModal(True)

        self.meta = CampoMoeda(passo=1_000.0)
        self.meta.setValue(max(0.0, deterministico))
        self.meta_resultado = CampoMoeda(passo=1_000.0)
        self.meta_resultado.setValue(max(0.0, deterministico_resultado))
        self.rodadas = CampoInteiro(10, 1_000_000, " rodadas")
        self.rodadas.setValue(10_000)

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.button(QDialogButtonBox.Ok).setText("Simular")
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)

        form = QFormLayout()
        form.addRow("Resultado acumulado desejado", self.meta)
        form.addRow(f"Resultado do mês {meses} desejado", self.meta_resultado)
        form.addRow("Simulações", self.rodadas)

        coluna = QVBoxLayout(self)
        coluna.addWidget(
            RotuloAjuda(
                f"Os parâmetros ficam fixos. Cada rodada simula os {meses} meses de novo, "
                "sorteando cliente por cliente quem dá churn, quem converte no fim do piloto e "
                "quem fica inadimplente. A rodada só conta como acerto se bater as "
                "<b>duas</b> metas.<br>"
                f"O modo determinístico dá <b>{moeda(deterministico, 0)}</b> acumulado e "
                f"<b>{moeda(deterministico_resultado, 0)}</b> no último mês."
            )
        )
        coluna.addLayout(form)
        coluna.addWidget(botoes)


class _Trabalho(QThread):
    """Roda as simulacoes fora da thread da interface."""

    progresso = Signal(int, int)
    concluido = Signal(object)

    def __init__(self, parametros, metadados, meta: float, meta_resultado: float, rodadas: int):
        super().__init__()
        self._args = (parametros, metadados, meta, meta_resultado, rodadas)
        self._cancelar = False

    def cancelar(self) -> None:
        self._cancelar = True

    def run(self) -> None:
        parametros, metadados, meta, meta_resultado, rodadas = self._args
        resultado = calcular_sorte(
            parametros,
            metadados,
            meta,
            meta_resultado,
            rodadas,
            progresso=lambda feitas, total: self.progresso.emit(feitas, total),
            cancelado=lambda: self._cancelar,
        )
        self.concluido.emit(resultado)


class DialogoResultado(QDialog):
    def __init__(self, parent, sorte: Sorte):
        super().__init__(parent)
        self.setWindowTitle("Sorte necessária")
        self.setModal(True)

        titulo = QLabel(f"<h2>{sorte.proporcao:.1%}</h2>")
        titulo.setAlignment(Qt.AlignCenter)

        corpo = (
            f"<b>{sorte.atingiram:n}</b> de <b>{sorte.rodadas_feitas:n}</b> rodadas "
            f"fecharam com pelo menos <b>{moeda(sorte.meta, 0)}</b> acumulados "
            f"<i>e</i> <b>{moeda(sorte.meta_resultado, 0)}</b> no último mês."
            f"<br>Separadamente: <b>{sorte.atingiram_acumulado:n}</b> bateram o acumulado, "
            f"<b>{sorte.atingiram_resultado:n}</b> bateram o último mês."
        )
        if sorte.cancelado:
            corpo += (
                f"<br><br><i>Cancelado antes do fim — foram pedidas "
                f"{sorte.rodadas_pedidas:n} rodadas.</i>"
            )

        faixa_resultado = sorte.amostras_resultado
        detalhe = (
            f"<br><br>Determinístico: <b>{moeda(sorte.deterministico, 0)}</b> acumulado, "
            f"no percentil <b>{sorte.percentil_do_deterministico:.0%}</b> das rodadas."
            f"<br>Acumulado: p10 {moeda_compacta(sorte.percentil(0.10))} · "
            f"p50 {moeda_compacta(sorte.percentil(0.50))} · "
            f"p90 {moeda_compacta(sorte.percentil(0.90))}"
            f"<br>Último mês: p10 {moeda_compacta(sorte.percentil(0.10, faixa_resultado))} · "
            f"p50 {moeda_compacta(sorte.percentil(0.50, faixa_resultado))} · "
            f"p90 {moeda_compacta(sorte.percentil(0.90, faixa_resultado))}"
        )

        texto = QLabel(corpo + detalhe)
        texto.setWordWrap(True)
        texto.setTextFormat(Qt.RichText)

        botoes = QDialogButtonBox(QDialogButtonBox.Close)
        botoes.rejected.connect(self.reject)
        botoes.accepted.connect(self.accept)

        coluna = QVBoxLayout(self)
        coluna.setSpacing(10)
        coluna.addWidget(titulo)
        coluna.addWidget(texto)
        coluna.addWidget(botoes)
        self.setMinimumWidth(420)


def executar(
    parent, parametros, metadados, deterministico: float, deterministico_resultado: float
) -> None:
    """Pergunta as metas, roda em segundo plano com barra e cancelamento, mostra o resultado."""
    pergunta = DialogoMeta(
        parent, deterministico, deterministico_resultado, parametros.meses_simulados
    )
    if pergunta.exec() != QDialog.Accepted:
        return
    meta = pergunta.meta.value()
    meta_resultado = pergunta.meta_resultado.value()
    rodadas = pergunta.rodadas.value()

    barra = QProgressDialog("Simulando…", "Cancelar", 0, rodadas, parent)
    barra.setWindowTitle("Calcular sorte")
    barra.setWindowModality(Qt.WindowModal)
    barra.setMinimumDuration(0)
    barra.setAutoClose(False)
    barra.setAutoReset(False)
    barra.setValue(0)

    trabalho = _Trabalho(parametros, metadados, meta, meta_resultado, rodadas)
    trabalho.progresso.connect(
        lambda feitas, total: (
            barra.setValue(feitas),
            barra.setLabelText(f"Simulando… {feitas:n} de {total:n}"),
        )
    )
    barra.canceled.connect(trabalho.cancelar)

    concluido: list[Sorte] = []
    trabalho.concluido.connect(concluido.append)
    trabalho.concluido.connect(barra.close)
    trabalho.start()
    barra.exec()
    trabalho.wait()

    if concluido:
        DialogoResultado(parent, concluido[0]).exec()
