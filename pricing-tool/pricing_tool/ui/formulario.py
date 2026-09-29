"""Formulario de parametros, com todos os campos de entrada."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..parametros import (
    MESES_ABREVIADOS,
    TIPO_EXPRESSAO,
    TIPO_LISTA,
    CurvaMaturacao,
    FuncaoAquisicao,
    FuncaoCusto,
    FuncaoVendedores,
    Metadados,
    Parametros,
    agora_utc,
    lista_aquisicao_padrao,
    lista_custo_padrao,
    lista_vendedores_padrao,
    lista_maturacao_padrao,
)
from .campos import (
    CampoDecimal,
    CampoExpressao,
    CampoInteiro,
    CampoMoeda,
    CampoPercentual,
    RotuloAjuda,
    SeletorMes,
)
from .tabelas_entrada import (
    TabelaAquisicao,
    TabelaCusto,
    TabelaMaturacao,
    TabelaVendedores,
)


class Sazonalidade(QWidget):
    """Multiplicador de ocupacao por mes do ano (jan-dez)."""

    alterado = Signal()

    def __init__(self):
        super().__init__()
        self.campos = []
        grade = QGridLayout()
        grade.setContentsMargins(0, 0, 0, 0)
        grade.setHorizontalSpacing(10)
        grade.setVerticalSpacing(4)
        for indice, nome in enumerate(MESES_ABREVIADOS):
            campo = CampoDecimal(minimo=0.0, maximo=3.0, passo=0.05, casas=2)
            campo.valueChanged.connect(self.alterado)
            self.campos.append(campo)
            coluna, linha = divmod(indice, 6)
            rotulo = QLabel(nome)
            rotulo.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grade.addWidget(rotulo, linha, coluna * 2)
            grade.addWidget(campo, linha, coluna * 2 + 1)

        neutralizar = QPushButton("Neutralizar (1,00)")
        neutralizar.clicked.connect(lambda: self.definir([1.0] * 12))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(grade)
        rodape = QHBoxLayout()
        rodape.setContentsMargins(0, 0, 0, 0)
        rodape.addWidget(neutralizar)
        rodape.addStretch(1)
        layout.addLayout(rodape)

    def valores(self) -> list[float]:
        return [campo.value() for campo in self.campos]

    def definir(self, valores: list[float]) -> None:
        for campo, valor in zip(self.campos, list(valores) + [1.0] * 12):
            campo.setValue(float(valor))


class SeletorTipo(QWidget):
    """Par de radios `lista` / `expressao` que mostra uma pagina de cada vez.

    Usa visibilidade em vez de QStackedWidget porque o stack sempre reserva a
    altura da maior pagina — no caso, a tabela.
    """

    alterado = Signal()

    def __init__(self, rotulo_lista: str, rotulo_expressao: str, pagina_lista, pagina_expressao):
        super().__init__()
        self.radio_lista = QRadioButton(rotulo_lista)
        self.radio_expressao = QRadioButton(rotulo_expressao)
        self.grupo = QButtonGroup(self)
        self.grupo.addButton(self.radio_lista, 0)
        self.grupo.addButton(self.radio_expressao, 1)
        self.paginas = (pagina_lista, pagina_expressao)

        linha = QHBoxLayout()
        linha.setContentsMargins(0, 0, 0, 0)
        linha.addWidget(self.radio_lista)
        linha.addWidget(self.radio_expressao)
        linha.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addLayout(linha)
        for pagina in self.paginas:
            layout.addWidget(pagina)

        self.grupo.idToggled.connect(self._trocar)
        self.definir_tipo(TIPO_EXPRESSAO)

    def _trocar(self, indice: int, marcado: bool) -> None:
        if not marcado:
            return
        self._mostrar_pagina(indice)
        self.alterado.emit()

    def _mostrar_pagina(self, indice: int) -> None:
        for posicao, pagina in enumerate(self.paginas):
            pagina.setVisible(posicao == indice)

    def tipo(self) -> str:
        return TIPO_EXPRESSAO if self.radio_expressao.isChecked() else TIPO_LISTA

    def definir_tipo(self, tipo: str) -> None:
        indice = 1 if tipo == TIPO_EXPRESSAO else 0
        (self.radio_expressao if indice else self.radio_lista).setChecked(True)
        self._mostrar_pagina(indice)


class Formulario(QScrollArea):
    """Le e escreve `Metadados` + `Parametros` a partir de campos restritos ao dominio."""

    alterado = Signal()

    def __init__(self):
        super().__init__()
        self._carregando = False
        self._criado_em = agora_utc()

        conteudo = QWidget()
        layout = QVBoxLayout(conteudo)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        layout.addWidget(self._grupo_cenario())
        layout.addWidget(self._grupo_vendedores())
        layout.addWidget(self._grupo_aquisicao())
        layout.addWidget(self._grupo_estrutura())
        layout.addWidget(self._grupo_utilizacao())
        layout.addWidget(self._grupo_transacional())
        layout.addWidget(self._grupo_recorrente())
        layout.addWidget(self._grupo_custos())
        layout.addStretch(1)

        self.setWidget(conteudo)
        self.setWidgetResizable(True)
        self.setMinimumWidth(478)

        self.meses_simulados.valueChanged.connect(self._sincronizar_horizonte)
        self.data_inicio.dateChanged.connect(self._sincronizar_horizonte)

    # ------------------------------------------------------------------ grupos

    def _grupo_cenario(self) -> QGroupBox:
        self.nome_cenario = QLineEdit()
        self.nome_cenario.setPlaceholderText("base, otimista, conservador...")
        self.nome_cenario.textChanged.connect(self._mudou)
        self.data_inicio = SeletorMes()
        self.data_inicio.dateChanged.connect(self._mudou)
        self.meses_simulados = CampoInteiro(1, 600, " meses")
        self.meses_simulados.valueChanged.connect(self._mudou)

        grupo = QGroupBox("1. Cenário")
        form = QFormLayout(grupo)
        form.addRow("Nome do cenário", self.nome_cenario)
        form.addRow("Mês inicial", self.data_inicio)
        form.addRow("Horizonte", self.meses_simulados)
        return grupo

    def _grupo_vendedores(self) -> QGroupBox:
        self.tabela_vendedores = TabelaVendedores()
        self.tabela_vendedores.alterado.connect(self._mudou)
        self.expressao_vendedores = CampoExpressao(("n",), "ex.: 3 + n / 6")
        self.expressao_vendedores.alterado.connect(self._mudou)

        pagina_expressao = QWidget()
        coluna = QVBoxLayout(pagina_expressao)
        coluna.setContentsMargins(0, 0, 0, 0)
        coluna.setSpacing(4)
        coluna.addWidget(self.expressao_vendedores)
        coluna.addWidget(
            RotuloAjuda(
                "Padrão expr-eval. Variável: <b>n</b> (mês da simulação). "
                "O resultado é arredondado e nunca fica negativo."
            )
        )

        self.tipo_vendedores = SeletorTipo(
            "Lista por mês", "Expressão", self.tabela_vendedores, pagina_expressao
        )
        self.tipo_vendedores.alterado.connect(self._mudou)

        grupo = QGroupBox("2. Vendedores")
        layout = QVBoxLayout(grupo)
        layout.addWidget(self.tipo_vendedores)
        layout.addWidget(
            RotuloAjuda(
                "Disponível como <b>v</b> na expressão de aquisição — é assim que o time "
                "vira alavanca: <code>2 * v</code> são duas clínicas por vendedor por mês."
            )
        )
        return grupo

    def _grupo_aquisicao(self) -> QGroupBox:
        self.tabela_aquisicao = TabelaAquisicao()
        self.tabela_aquisicao.alterado.connect(self._mudou)
        self.expressao_aquisicao = CampoExpressao(("n", "v"), "ex.: 2 * v")
        self.expressao_aquisicao.alterado.connect(self._mudou)

        pagina_expressao = QWidget()
        coluna = QVBoxLayout(pagina_expressao)
        coluna.setContentsMargins(0, 0, 0, 0)
        coluna.setSpacing(4)
        coluna.addWidget(self.expressao_aquisicao)
        coluna.addWidget(
            RotuloAjuda(
                "Padrão expr-eval, avaliada a cada mês. Variáveis: <b>n</b> (mês da simulação) "
                "e <b>v</b> (vendedores ativos no mês). O resultado é arredondado e nunca "
                "fica negativo."
            )
        )

        self.tipo_aquisicao = SeletorTipo(
            "Lista por mês", "Expressão", self.tabela_aquisicao, pagina_expressao
        )
        self.tipo_aquisicao.alterado.connect(self._mudou)

        self.taxa_churn_mensal = CampoPercentual(passo=0.25)
        self.taxa_churn_mensal.valueChanged.connect(self._mudou)

        grupo = QGroupBox("3. Aquisição de clínicas")
        layout = QVBoxLayout(grupo)
        layout.addWidget(self.tipo_aquisicao)
        form = QFormLayout()
        form.addRow("Churn mensal", self.taxa_churn_mensal)
        layout.addLayout(form)
        return grupo

    def _grupo_estrutura(self) -> QGroupBox:
        self.consultorios_por_clinica_media = CampoDecimal(0.0, 200.0, 0.5, 2)
        self.consultorios_por_clinica_media.valueChanged.connect(self._mudou)

        grupo = QGroupBox("4. Estrutura da clínica")
        form = QFormLayout(grupo)
        form.addRow("Consultórios por clínica (média)", self.consultorios_por_clinica_media)
        return grupo

    def _grupo_utilizacao(self) -> QGroupBox:
        self.vagas_disponiveis_dia = CampoDecimal(0.0, 24.0, 1.0, 1)
        self.vagas_disponiveis_dia.valueChanged.connect(self._mudou)
        self.dias_operacao_mes = CampoDecimal(0.0, 31.0, 1.0, 1)
        self.dias_operacao_mes.valueChanged.connect(self._mudou)
        self.valor_medio_atendimento = CampoMoeda(passo=5.0)
        self.valor_medio_atendimento.valueChanged.connect(self._mudou)

        self.tabela_maturacao = TabelaMaturacao()
        self.tabela_maturacao.alterado.connect(self._mudou)
        self.expressao_maturacao = CampoExpressao(("t",), "ex.: min(0.3, 0.06 * t)")
        self.expressao_maturacao.alterado.connect(self._mudou)

        pagina_expressao = QWidget()
        coluna = QVBoxLayout(pagina_expressao)
        coluna.setContentsMargins(0, 0, 0, 0)
        coluna.setSpacing(4)
        coluna.addWidget(self.expressao_maturacao)
        coluna.addWidget(
            RotuloAjuda(
                "Padrão expr-eval, avaliada por mês de vida da clínica. Variável: <b>t</b> "
                "(mês desde a ativação, a partir de 1). O resultado é limitado entre 0% e 100%."
            )
        )

        self.tipo_maturacao = SeletorTipo(
            "Lista de pontos", "Expressão", self.tabela_maturacao, pagina_expressao
        )
        self.tipo_maturacao.alterado.connect(self._mudou)

        self.sazonalidade = Sazonalidade()
        self.sazonalidade.alterado.connect(self._mudou)

        grupo = QGroupBox("5. Utilização e ocupação")
        layout = QVBoxLayout(grupo)
        form = QFormLayout()
        form.addRow("Vagas por consultório/dia", self.vagas_disponiveis_dia)
        form.addRow("Dias de operação/mês", self.dias_operacao_mes)
        form.addRow("Valor médio por atendimento", self.valor_medio_atendimento)
        layout.addLayout(form)
        layout.addWidget(QLabel("<b>Curva de maturação</b>"))
        layout.addWidget(self.tipo_maturacao)
        layout.addWidget(QLabel("<b>Sazonalidade</b> (multiplicador por mês do ano)"))
        layout.addWidget(self.sazonalidade)
        return grupo

    def _grupo_transacional(self) -> QGroupBox:
        self.taxa_fixa_por_atendimento = CampoMoeda(passo=0.5)
        self.taxa_fixa_por_atendimento.valueChanged.connect(self._mudou)
        self.taxa_percentual_por_atendimento = CampoPercentual(passo=0.5)
        self.taxa_percentual_por_atendimento.valueChanged.connect(self._mudou)

        grupo = QGroupBox("6. Receita transacional")
        form = QFormLayout(grupo)
        form.addRow("Taxa fixa por atendimento", self.taxa_fixa_por_atendimento)
        form.addRow("Taxa % por atendimento", self.taxa_percentual_por_atendimento)
        return grupo

    def _grupo_recorrente(self) -> QGroupBox:
        self.valor_mensalidade = CampoMoeda(passo=10.0)
        self.valor_mensalidade.valueChanged.connect(self._mudou)
        self.meses_trial_gratis = CampoInteiro(0, 60, " meses")
        self.meses_trial_gratis.valueChanged.connect(self._mudou)
        self.percentual_conversao_pos_trial = CampoPercentual(passo=1.0)
        self.percentual_conversao_pos_trial.valueChanged.connect(self._mudou)

        grupo = QGroupBox("7. Receita recorrente")
        form = QFormLayout(grupo)
        form.addRow("Mensalidade por clínica", self.valor_mensalidade)
        form.addRow("Trial grátis", self.meses_trial_gratis)
        form.addRow("Conversão ao fim do trial", self.percentual_conversao_pos_trial)
        form.addRow("", RotuloAjuda("As clínicas que não convertem saem da base — sem assinatura não há agenda online."))
        return grupo

    def _grupo_custos(self) -> QGroupBox:
        self.custo_processamento_percentual = CampoPercentual(passo=0.1)
        self.custo_processamento_percentual.valueChanged.connect(self._mudou)
        self.taxa_inadimplencia = CampoPercentual(passo=0.1)
        self.taxa_inadimplencia.valueChanged.connect(self._mudou)
        self.comissao_vendedor_percentual = CampoPercentual(passo=1.0)
        self.comissao_vendedor_percentual.valueChanged.connect(self._mudou)

        self.tabela_custo = TabelaCusto()
        self.tabela_custo.alterado.connect(self._mudou)
        self.expressao_custo = CampoExpressao(("n", "a"), "ex.: 4500 + 20 * a")
        self.expressao_custo.alterado.connect(self._mudou)

        pagina_expressao = QWidget()
        coluna = QVBoxLayout(pagina_expressao)
        coluna.setContentsMargins(0, 0, 0, 0)
        coluna.setSpacing(4)
        coluna.addWidget(self.expressao_custo)
        coluna.addWidget(
            RotuloAjuda(
                "Padrão expr-eval, avaliada a cada mês. Variáveis: <b>n</b> (mês da simulação) "
                "e <b>a</b> (clínicas ativas no mês). Nunca fica negativa.<br>"
                "Degrau por tamanho da base: <code>8000 + 2500 * ceil(a / 50)</code>."
            )
        )

        self.tipo_custo = SeletorTipo(
            "Lista por mês", "Expressão", self.tabela_custo, pagina_expressao
        )
        self.tipo_custo.alterado.connect(self._mudou)

        grupo = QGroupBox("8. Custos")
        layout = QVBoxLayout(grupo)
        form = QFormLayout()
        form.addRow("Processamento (sobre o volume transacionado)", self.custo_processamento_percentual)
        form.addRow(
            "",
            RotuloAjuda(
                "Zero enquanto o pagamento cai direto na conta da clínica — nesse desenho "
                "a taxa da operadora de pagamento é dela, não sua."
            ),
        )
        form.addRow("Inadimplência (sobre a fatura)", self.taxa_inadimplencia)
        form.addRow(
            "",
            RotuloAjuda(
                "A clínica operou o mês, foi faturada e não pagou: a receita do mês vira perda "
                "<b>e</b> ela perde o acesso à agenda online, saindo da base no mês seguinte."
            ),
        )
        form.addRow("Comissão do vendedor", self.comissao_vendedor_percentual)
        form.addRow(
            "",
            RotuloAjuda(
                "Sobre a receita <b>recebida</b> da clínica — o que não foi pago não comissiona. "
                "Vale enquanto aquela clínica continuar na carteira dele."
            ),
        )
        layout.addLayout(form)
        layout.addWidget(QLabel("<b>Custo operacional do mês</b>"))
        layout.addWidget(self.tipo_custo)
        return grupo

    # ------------------------------------------------------------------ estado

    def _mudou(self, *_args) -> None:
        if not self._carregando:
            self.alterado.emit()

    def _sincronizar_horizonte(self, *_args) -> None:
        if self._carregando:
            return
        mes_inicio, meses = self.data_inicio.mes_iso(), self.meses_simulados.value()
        self.tabela_vendedores.sincronizar(mes_inicio, meses)
        self.tabela_aquisicao.sincronizar(mes_inicio, meses)
        self.tabela_custo.sincronizar(mes_inicio, meses)

    def metadados(self) -> Metadados:
        return Metadados(
            nome_cenario=self.nome_cenario.text().strip() or "sem nome",
            data_inicio=self.data_inicio.mes_iso(),
            criado_em=self._criado_em,
        )

    def parametros(self) -> Parametros:
        return Parametros(
            meses_simulados=self.meses_simulados.value(),
            funcao_vendedores=FuncaoVendedores(
                tipo=self.tipo_vendedores.tipo(),
                expressao=self.expressao_vendedores.texto(),
                valores=self.tabela_vendedores.valores(),
            ),
            funcao_aquisicao=FuncaoAquisicao(
                tipo=self.tipo_aquisicao.tipo(),
                expressao=self.expressao_aquisicao.texto(),
                valores=self.tabela_aquisicao.valores(),
            ),
            taxa_churn_mensal=self.taxa_churn_mensal.fracao(),
            consultorios_por_clinica_media=self.consultorios_por_clinica_media.value(),
            vagas_disponiveis_dia=self.vagas_disponiveis_dia.value(),
            dias_operacao_mes=self.dias_operacao_mes.value(),
            curva_maturacao=CurvaMaturacao(
                tipo=self.tipo_maturacao.tipo(),
                expressao=self.expressao_maturacao.texto(),
                valores=self.tabela_maturacao.valores(),
            ),
            sazonalidade_mensal=self.sazonalidade.valores(),
            valor_medio_atendimento=self.valor_medio_atendimento.value(),
            taxa_fixa_por_atendimento=self.taxa_fixa_por_atendimento.value(),
            taxa_percentual_por_atendimento=self.taxa_percentual_por_atendimento.fracao(),
            valor_mensalidade=self.valor_mensalidade.value(),
            meses_trial_gratis=self.meses_trial_gratis.value(),
            percentual_conversao_pos_trial=self.percentual_conversao_pos_trial.fracao(),
            custo_processamento_percentual=self.custo_processamento_percentual.fracao(),
            taxa_inadimplencia=self.taxa_inadimplencia.fracao(),
            comissao_vendedor_percentual=self.comissao_vendedor_percentual.fracao(),
            funcao_custo_operacional=FuncaoCusto(
                tipo=self.tipo_custo.tipo(),
                expressao=self.expressao_custo.texto(),
                valores=self.tabela_custo.valores(),
            ),
        )

    def carregar(self, metadados: Metadados, parametros: Parametros) -> None:
        self._carregando = True
        self._criado_em = metadados.criado_em or agora_utc()
        self.nome_cenario.setText(metadados.nome_cenario)
        self.data_inicio.definir_mes_iso(metadados.data_inicio)
        self.meses_simulados.setValue(parametros.meses_simulados)

        vendedores = parametros.funcao_vendedores
        self.expressao_vendedores.definir_texto(vendedores.expressao)
        self.tabela_vendedores.definir(
            vendedores.valores
            or lista_vendedores_padrao(metadados.data_inicio, parametros.meses_simulados),
            metadados.data_inicio,
            parametros.meses_simulados,
        )
        self.tipo_vendedores.definir_tipo(vendedores.tipo)

        aquisicao = parametros.funcao_aquisicao
        self.expressao_aquisicao.definir_texto(aquisicao.expressao)
        valores = aquisicao.valores or lista_aquisicao_padrao(
            metadados.data_inicio, parametros.meses_simulados
        )
        self.tabela_aquisicao.definir(valores, metadados.data_inicio, parametros.meses_simulados)
        self.tipo_aquisicao.definir_tipo(aquisicao.tipo)

        self.taxa_churn_mensal.definir_fracao(parametros.taxa_churn_mensal)
        self.consultorios_por_clinica_media.setValue(parametros.consultorios_por_clinica_media)
        self.vagas_disponiveis_dia.setValue(parametros.vagas_disponiveis_dia)
        self.dias_operacao_mes.setValue(parametros.dias_operacao_mes)

        curva = parametros.curva_maturacao
        self.expressao_maturacao.definir_texto(curva.expressao)
        self.tabela_maturacao.definir(curva.valores or lista_maturacao_padrao())
        self.tipo_maturacao.definir_tipo(curva.tipo)

        self.sazonalidade.definir(parametros.sazonalidade_mensal)
        self.valor_medio_atendimento.setValue(parametros.valor_medio_atendimento)
        self.taxa_fixa_por_atendimento.setValue(parametros.taxa_fixa_por_atendimento)
        self.taxa_percentual_por_atendimento.definir_fracao(parametros.taxa_percentual_por_atendimento)
        self.valor_mensalidade.setValue(parametros.valor_mensalidade)
        self.meses_trial_gratis.setValue(parametros.meses_trial_gratis)
        self.percentual_conversao_pos_trial.definir_fracao(parametros.percentual_conversao_pos_trial)
        self.custo_processamento_percentual.definir_fracao(parametros.custo_processamento_percentual)
        self.taxa_inadimplencia.definir_fracao(parametros.taxa_inadimplencia)
        self.comissao_vendedor_percentual.definir_fracao(parametros.comissao_vendedor_percentual)

        custo = parametros.funcao_custo_operacional
        self.expressao_custo.definir_texto(custo.expressao)
        self.tabela_custo.definir(
            custo.valores or lista_custo_padrao(metadados.data_inicio, parametros.meses_simulados),
            metadados.data_inicio,
            parametros.meses_simulados,
        )
        self.tipo_custo.definir_tipo(custo.tipo)
        self._carregando = False

    def definir_somente_leitura(self, somente_leitura: bool) -> None:
        self.widget().setEnabled(not somente_leitura)
