"""Janela principal: formulario, resultados e os dois modos de abertura do JSON."""

import json
import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .. import documento
from ..motor import Resultados, simular
from ..parametros import Metadados, agora_utc, preset_padrao
from . import sorte as ui_sorte
from .estilo import aplicar_tema, folha
from .formato import mes_extenso
from .formulario import Formulario
from .resultados import PainelResultados

PASTA_SIMULACOES = Path(__file__).resolve().parents[2] / "simulacoes"
# Padrao do usuario: sobrepoe o preset de fabrica quando existe.
ARQUIVO_PADRAO = Path(__file__).resolve().parents[2] / "padrao.json"

MODO_EDICAO = "edicao"
MODO_VISUALIZACAO = "visualizacao"


class Janela(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simulador de Retorno — Agência de Marketing")
        self.resize(1440, 900)

        escuro = aplicar_tema(QApplication.instance())
        self.formulario = Formulario()
        self.painel = PainelResultados(escuro)
        self.formulario.alterado.connect(self._parametros_alterados)

        self.modo = MODO_EDICAO
        self.resultados: Resultados | None = None
        self.atualizado = False
        self.arquivo_atual: Path | None = None

        self._montar_barra()
        self.setCentralWidget(self._montar_centro())
        self.statusBar().showMessage("Pronto.")
        self.setStyleSheet(folha(escuro))

        self.aplicar_preset_padrao()

    # ------------------------------------------------------------------ layout

    def _montar_barra(self) -> None:
        barra = self.addToolBar("Ações")
        barra.setMovable(False)

        self.acao_preset = QAction("Preset padrão", self)
        self.acao_preset.setShortcut(QKeySequence.New)
        self.acao_preset.setToolTip("Recarrega o cenário padrão e simula")
        self.acao_preset.triggered.connect(self.aplicar_preset_padrao)

        self.acao_definir_padrao = QAction("Definir como padrão", self)
        self.acao_definir_padrao.setToolTip(
            "Grava os parâmetros atuais como o padrão que abre com o app"
        )
        self.acao_definir_padrao.triggered.connect(self.definir_como_padrao)

        self.acao_importar = QAction("Importar JSON", self)
        self.acao_importar.setShortcut(QKeySequence.Open)
        self.acao_importar.triggered.connect(self.importar)

        self.acao_exportar = QAction("Exportar JSON", self)
        self.acao_exportar.setShortcut(QKeySequence.Save)
        self.acao_exportar.triggered.connect(self.exportar)

        self.acao_simular = QAction("Simular", self)
        self.acao_simular.setShortcut(QKeySequence("F5"))
        self.acao_simular.triggered.connect(self.simular)

        self.acao_sorte = QAction("Calcular sorte", self)
        self.acao_sorte.setShortcut(QKeySequence("F6"))
        self.acao_sorte.setToolTip(
            "Roda a simulação N vezes sorteando churn, conversão e inadimplência "
            "cliente por cliente, e diz quantas rodadas bateram a sua meta"
        )
        self.acao_sorte.triggered.connect(self.calcular_sorte)

        for acao in (
            self.acao_preset,
            self.acao_definir_padrao,
            self.acao_importar,
            self.acao_exportar,
        ):
            barra.addAction(acao)
        barra.addSeparator()
        barra.addAction(self.acao_simular)
        barra.addAction(self.acao_sorte)

    def _montar_centro(self) -> QWidget:
        self.faixa = QFrame()
        self.faixa.setObjectName("faixaVisualizacao")
        self.faixa_texto = QLabel()
        self.faixa_texto.setWordWrap(True)
        botao_editar = QPushButton("Editar e reprocessar")
        botao_editar.clicked.connect(self.entrar_em_edicao)
        linha = QHBoxLayout(self.faixa)
        linha.setContentsMargins(12, 8, 12, 8)
        linha.addWidget(self.faixa_texto, 1)
        linha.addWidget(botao_editar)
        self.faixa.setVisible(False)

        divisor = QSplitter(Qt.Horizontal)
        divisor.addWidget(self.formulario)
        divisor.addWidget(self.painel)
        divisor.setStretchFactor(0, 0)
        divisor.setStretchFactor(1, 1)
        divisor.setSizes([500, 940])

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.faixa)
        layout.addWidget(divisor, 1)
        return central

    # ------------------------------------------------------------------ acoes

    def aplicar_preset_padrao(self) -> None:
        metadados, parametros, origem = self._preset()
        self.arquivo_atual = None
        self.formulario.carregar(metadados, parametros)
        self._definir_modo(MODO_EDICAO)
        self.simular()
        self.statusBar().showMessage(f"Preset {origem} carregado e simulado.")

    def _preset(self):
        """Padrao do usuario, se houver; senao o de fabrica."""
        if not ARQUIVO_PADRAO.exists():
            metadados, parametros = preset_padrao()
            return metadados, parametros, "de fábrica"
        try:
            importado = documento.carregar(ARQUIVO_PADRAO)
        except (OSError, ValueError) as erro:
            QMessageBox.warning(
                self,
                "Padrão inválido",
                f"Não consegui ler {ARQUIVO_PADRAO.name}, então usei o preset de fábrica.\n\n{erro}",
            )
            metadados, parametros = preset_padrao()
            return metadados, parametros, "de fábrica"
        if importado.avisos:
            QMessageBox.information(
                self,
                "Avisos ao ler o padrão",
                "• " + "\n• ".join(importado.avisos),
            )
        return importado.metadados, importado.parametros, "salvo por você"

    def definir_como_padrao(self) -> None:
        metadados = self.formulario.metadados()
        parametros = self.formulario.parametros()
        erros = documento.validar(parametros, metadados)
        if erros:
            QMessageBox.warning(
                self,
                "Parâmetros inválidos",
                "Corrija antes de definir como padrão:\n\n• " + "\n• ".join(erros),
            )
            return

        caixa = QMessageBox(self)
        caixa.setIcon(QMessageBox.Question)
        caixa.setWindowTitle("Definir como padrão")
        existe = ARQUIVO_PADRAO.exists()
        caixa.setText(
            "Gravar os parâmetros atuais como padrão?"
            if not existe
            else "Já existe um padrão seu. Substituir pelos parâmetros atuais?"
        )
        caixa.setInformativeText(
            f"É o que abre com o app e o que o botão “Preset padrão” recarrega.\n"
            f"Fica em {ARQUIVO_PADRAO.name}, sem os resultados."
        )
        gravar = caixa.addButton("Gravar", QMessageBox.AcceptRole)
        restaurar = (
            caixa.addButton("Restaurar de fábrica", QMessageBox.DestructiveRole)
            if existe
            else None
        )
        caixa.addButton("Cancelar", QMessageBox.RejectRole)
        caixa.setDefaultButton(gravar)
        caixa.exec()

        if caixa.clickedButton() is gravar:
            try:
                documento.salvar(ARQUIVO_PADRAO, metadados, parametros, None)
            except OSError as erro:
                QMessageBox.critical(self, "Erro ao gravar", str(erro))
                return
            self.statusBar().showMessage(f"Padrão gravado em {ARQUIVO_PADRAO.name}.")
        elif restaurar is not None and caixa.clickedButton() is restaurar:
            try:
                ARQUIVO_PADRAO.unlink()
            except OSError as erro:
                QMessageBox.critical(self, "Erro ao remover", str(erro))
                return
            self.statusBar().showMessage("Padrão de fábrica restaurado.")

    def simular(self) -> None:
        if self.modo == MODO_VISUALIZACAO:
            self.entrar_em_edicao()
        metadados = self.formulario.metadados()
        parametros = self.formulario.parametros()
        erros = documento.validar(parametros, metadados)
        if erros:
            QMessageBox.warning(
                self,
                "Parâmetros inválidos",
                "Corrija antes de simular:\n\n• " + "\n• ".join(erros),
            )
            self.statusBar().showMessage("Simulação não rodou: há parâmetros inválidos.")
            return

        self.resultados = simular(parametros, metadados)
        self.painel.mostrar(self.resultados)
        self.painel.definir_cabecalho(_cabecalho(metadados, self.resultados))
        self.atualizado = True
        kpis = self.resultados.kpis_agregados
        payback = f"payback no mês {kpis.payback_meses}" if kpis.payback_meses else "sem payback no horizonte"
        self.statusBar().showMessage(
            f"Simulação de {parametros.meses_simulados} meses concluída — {payback}."
        )

    def calcular_sorte(self) -> None:
        if self.modo == MODO_VISUALIZACAO:
            self.entrar_em_edicao()
        metadados = self.formulario.metadados()
        parametros = self.formulario.parametros()
        erros = documento.validar(parametros, metadados)
        if erros:
            QMessageBox.warning(
                self,
                "Parâmetros inválidos",
                "Corrija antes de calcular a sorte:\n\n• " + "\n• ".join(erros),
            )
            return
        base = simular(parametros, metadados)
        deterministico = base.kpis_agregados.resultado_liquido_total
        ultimo_mes = base.series_mensais[-1].resultado_liquido if base.series_mensais else 0.0
        ui_sorte.executar(self, parametros, metadados, deterministico, ultimo_mes)

    def _parametros_alterados(self) -> None:
        if self.modo == MODO_EDICAO and self.atualizado:
            self.atualizado = False
            self.statusBar().showMessage("Parâmetros alterados — rode a simulação (F5).")

    def entrar_em_edicao(self) -> None:
        if self.modo != MODO_EDICAO:
            self._definir_modo(MODO_EDICAO)
            self.atualizado = False
            self.statusBar().showMessage(
                "Modo edição: ajuste os parâmetros e rode a simulação (F5)."
            )

    def _definir_modo(self, modo: str, origem: str = "") -> None:
        self.modo = modo
        visualizando = modo == MODO_VISUALIZACAO
        self.formulario.definir_somente_leitura(visualizando)
        self.faixa.setVisible(visualizando)
        if visualizando:
            self.faixa_texto.setText(
                f"<b>Visualizando resultados salvos</b> de {origem}. "
                "Os parâmetros estão travados; nada foi recalculado."
            )

    # ------------------------------------------------------------------ arquivos

    def importar(self) -> None:
        PASTA_SIMULACOES.mkdir(exist_ok=True)
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Importar simulação", str(PASTA_SIMULACOES), "Simulações (*.json)"
        )
        if not caminho:
            return
        try:
            importado = documento.carregar(caminho)
        except (OSError, json.JSONDecodeError, documento.DocumentoInvalido) as erro:
            QMessageBox.critical(self, "Falha ao importar", f"Não foi possível ler o arquivo:\n{erro}")
            return

        self.arquivo_atual = Path(caminho)
        self.formulario.carregar(importado.metadados, importado.parametros)
        if importado.avisos:
            QMessageBox.information(
                self,
                "Importado com ajustes",
                "O arquivo foi lido, mas alguns pontos precisaram de ajuste:\n\n• "
                + "\n• ".join(importado.avisos),
            )

        if importado.resultados is None:
            self._definir_modo(MODO_EDICAO)
            self.resultados = None
            self.painel.limpar()
            self.atualizado = False
            QMessageBox.information(
                self,
                "Sem resultados salvos",
                "O arquivo não traz o bloco `resultados`. Abrindo em modo de re-simulação.",
            )
            self.simular()
            return

        self._perguntar_modo(importado)

    def _perguntar_modo(self, importado: documento.DocumentoImportado) -> None:
        caixa = QMessageBox(self)
        caixa.setWindowTitle("Como abrir esta simulação?")
        caixa.setIcon(QMessageBox.Question)
        caixa.setText(f"<b>{importado.metadados.nome_cenario}</b> — o arquivo já traz resultados salvos.")
        caixa.setInformativeText("Escolha como abrir:")
        ver = caixa.addButton("Ver resultados salvos", QMessageBox.AcceptRole)
        reprocessar = caixa.addButton("Editar e reprocessar", QMessageBox.ActionRole)
        caixa.setDefaultButton(ver)
        caixa.exec()

        if caixa.clickedButton() is reprocessar:
            self._definir_modo(MODO_EDICAO)
            self.simular()
            self.statusBar().showMessage(
                f"{self.arquivo_atual.name} reprocessado a partir dos parâmetros salvos."
            )
            return

        self.resultados = importado.resultados
        self.painel.mostrar(importado.resultados)
        self.painel.definir_cabecalho(
            _cabecalho(importado.metadados, importado.resultados)
            + " · <i>resultados salvos, não recalculados</i>"
        )
        self.atualizado = True
        self._definir_modo(MODO_VISUALIZACAO, origem=self.arquivo_atual.name)
        self.statusBar().showMessage(f"Exibindo os resultados salvos em {self.arquivo_atual.name}.")

    def exportar(self) -> None:
        if self.modo == MODO_EDICAO and not self.atualizado:
            self.simular()
        if self.resultados is None:
            QMessageBox.warning(self, "Nada para exportar", "Rode a simulação antes de exportar.")
            return

        metadados = self.formulario.metadados()
        parametros = self.formulario.parametros()
        if self.modo == MODO_EDICAO:
            metadados.criado_em = agora_utc()

        PASTA_SIMULACOES.mkdir(exist_ok=True)
        sugestao = PASTA_SIMULACOES / f"{_apelido(metadados)}.json"
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Exportar simulação", str(sugestao), "Simulações (*.json)"
        )
        if not caminho:
            return
        if not caminho.lower().endswith(".json"):
            caminho += ".json"
        try:
            documento.salvar(caminho, metadados, parametros, self.resultados)
        except OSError as erro:
            QMessageBox.critical(self, "Falha ao exportar", f"Não foi possível gravar:\n{erro}")
            return
        self.arquivo_atual = Path(caminho)
        self.statusBar().showMessage(f"Exportado para {caminho}")


def _cabecalho(metadados: Metadados, resultados: Resultados) -> str:
    series = resultados.series_mensais
    if not series:
        return metadados.nome_cenario
    return (
        f"<b>{metadados.nome_cenario}</b> · {mes_extenso(series[0].data)} → "
        f"{mes_extenso(series[-1].data)} · {len(series)} meses"
    )


def _apelido(metadados: Metadados) -> str:
    nome = re.sub(r"[^a-z0-9]+", "-", metadados.nome_cenario.lower()).strip("-")
    return f"{nome or 'simulacao'}-{metadados.data_inicio}"


def executar() -> int:
    aplicacao = QApplication.instance() or QApplication([])
    aplicacao.setApplicationName("Simulador de Retorno")
    janela = Janela()
    janela.show()
    return aplicacao.exec()
