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
    CurvaEscopo,
    FuncaoAquisicao,
    FuncaoComerciais,
    FuncaoCusto,
    Metadados,
    Parametros,
    agora_utc,
    lista_aquisicao_padrao,
    lista_comerciais_padrao,
    lista_custo_padrao,
    lista_escopo_padrao,
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
    TabelaComerciais,
    TabelaCusto,
    TabelaEscopo,
)


class Sazonalidade(QWidget):
    """Multiplicador da verba de midia por mes do ano (jan-dez)."""

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
        layout.addWidget(self._grupo_comerciais())
        layout.addWidget(self._grupo_aquisicao())
        layout.addWidget(self._grupo_contrato())
        layout.addWidget(self._grupo_escopo())
        layout.addWidget(self._grupo_piloto())
        layout.addWidget(self._grupo_capacidade())
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

    def _grupo_comerciais(self) -> QGroupBox:
        self.tabela_comerciais = TabelaComerciais()
        self.tabela_comerciais.alterado.connect(self._mudou)
        self.expressao_comerciais = CampoExpressao(("n",), "ex.: 2 + n / 6")
        self.expressao_comerciais.alterado.connect(self._mudou)

        pagina_expressao = QWidget()
        coluna = QVBoxLayout(pagina_expressao)
        coluna.setContentsMargins(0, 0, 0, 0)
        coluna.setSpacing(4)
        coluna.addWidget(self.expressao_comerciais)
        coluna.addWidget(
            RotuloAjuda(
                "Padrão expr-eval. Variável: <b>n</b> (mês da simulação). "
                "O resultado é arredondado e nunca fica negativo."
            )
        )

        self.tipo_comerciais = SeletorTipo(
            "Lista por mês", "Expressão", self.tabela_comerciais, pagina_expressao
        )
        self.tipo_comerciais.alterado.connect(self._mudou)

        grupo = QGroupBox("2. Comerciais")
        layout = QVBoxLayout(grupo)
        layout.addWidget(self.tipo_comerciais)
        layout.addWidget(
            RotuloAjuda(
                "Disponível como <b>c</b> na expressão de aquisição — é assim que o time "
                "comercial vira alavanca: <code>1 * c</code> é um contrato fechado por "
                "comercial por mês."
            )
        )
        return grupo

    def _grupo_aquisicao(self) -> QGroupBox:
        self.tabela_aquisicao = TabelaAquisicao()
        self.tabela_aquisicao.alterado.connect(self._mudou)
        self.expressao_aquisicao = CampoExpressao(("n", "c"), "ex.: 1 * c")
        self.expressao_aquisicao.alterado.connect(self._mudou)

        pagina_expressao = QWidget()
        coluna = QVBoxLayout(pagina_expressao)
        coluna.setContentsMargins(0, 0, 0, 0)
        coluna.setSpacing(4)
        coluna.addWidget(self.expressao_aquisicao)
        coluna.addWidget(
            RotuloAjuda(
                "Padrão expr-eval, avaliada a cada mês. Variáveis: <b>n</b> (mês da simulação) "
                "e <b>c</b> (comerciais ativos no mês). O resultado é arredondado e nunca "
                "fica negativo."
            )
        )

        self.tipo_aquisicao = SeletorTipo(
            "Lista por mês", "Expressão", self.tabela_aquisicao, pagina_expressao
        )
        self.tipo_aquisicao.alterado.connect(self._mudou)

        self.taxa_churn_mensal = CampoPercentual(passo=0.25)
        self.taxa_churn_mensal.valueChanged.connect(self._mudou)

        grupo = QGroupBox("3. Aquisição de clientes")
        layout = QVBoxLayout(grupo)
        layout.addWidget(self.tipo_aquisicao)
        form = QFormLayout()
        form.addRow("Churn mensal", self.taxa_churn_mensal)
        layout.addLayout(form)
        return grupo

    def _grupo_contrato(self) -> QGroupBox:
        self.retainer_mensal_pleno = CampoMoeda(passo=250.0)
        self.retainer_mensal_pleno.valueChanged.connect(self._mudou)
        self.taxa_setup = CampoMoeda(passo=100.0)
        self.taxa_setup.valueChanged.connect(self._mudou)
        self.verba_midia_media = CampoMoeda(passo=500.0)
        self.verba_midia_media.valueChanged.connect(self._mudou)
        self.fee_gestao_midia_percentual = CampoPercentual(passo=0.5)
        self.fee_gestao_midia_percentual.valueChanged.connect(self._mudou)

        grupo = QGroupBox("4. Contrato (escopo pleno)")
        form = QFormLayout(grupo)
        form.addRow("Retainer mensal", self.retainer_mensal_pleno)
        form.addRow("Taxa de setup (única)", self.taxa_setup)
        form.addRow("Verba de mídia gerenciada", self.verba_midia_media)
        form.addRow("Fee sobre a verba", self.fee_gestao_midia_percentual)
        form.addRow(
            "",
            RotuloAjuda(
                "A verba é do cliente e não vira receita — a agência fica só com o "
                "<b>fee</b> sobre ela. Mas cada real de verba também gera horas de otimização."
            ),
        )
        return grupo

    def _grupo_escopo(self) -> QGroupBox:
        self.tabela_escopo = TabelaEscopo()
        self.tabela_escopo.alterado.connect(self._mudou)
        self.expressao_escopo = CampoExpressao(("t",), "ex.: min(1, 0.5 + 0.1 * t)")
        self.expressao_escopo.alterado.connect(self._mudou)

        pagina_expressao = QWidget()
        coluna = QVBoxLayout(pagina_expressao)
        coluna.setContentsMargins(0, 0, 0, 0)
        coluna.setSpacing(4)
        coluna.addWidget(self.expressao_escopo)
        coluna.addWidget(
            RotuloAjuda(
                "Padrão expr-eval, avaliada por mês de vida do cliente. Variável: <b>t</b> "
                "(mês desde a ativação, a partir de 1). O resultado é limitado entre 0% e 100%."
            )
        )

        self.tipo_escopo = SeletorTipo(
            "Lista de pontos", "Expressão", self.tabela_escopo, pagina_expressao
        )
        self.tipo_escopo.alterado.connect(self._mudou)

        self.sazonalidade = Sazonalidade()
        self.sazonalidade.alterado.connect(self._mudou)

        grupo = QGroupBox("5. Escopo e sazonalidade")
        layout = QVBoxLayout(grupo)
        layout.addWidget(QLabel("<b>Rampa de escopo</b> (fração do escopo pleno em execução)"))
        layout.addWidget(self.tipo_escopo)
        layout.addWidget(
            RotuloAjuda(
                "O escopo escala retainer, verba de mídia e horas ao mesmo tempo: o cliente "
                "novo começa pequeno e o time só cresce junto com ele."
            )
        )
        layout.addWidget(QLabel("<b>Sazonalidade da verba</b> (multiplicador por mês do ano)"))
        layout.addWidget(self.sazonalidade)
        layout.addWidget(
            RotuloAjuda(
                "Datas como Black Friday e Natal inflam a verba — e com ela o fee e as horas, "
                "o que pode forçar contratação no pico."
            )
        )
        return grupo

    def _grupo_piloto(self) -> QGroupBox:
        self.meses_piloto = CampoInteiro(0, 24, " meses")
        self.meses_piloto.valueChanged.connect(self._mudou)
        self.desconto_piloto_percentual = CampoPercentual(passo=5.0)
        self.desconto_piloto_percentual.valueChanged.connect(self._mudou)
        self.percentual_conversao_pos_piloto = CampoPercentual(passo=1.0)
        self.percentual_conversao_pos_piloto.valueChanged.connect(self._mudou)

        grupo = QGroupBox("6. Piloto")
        form = QFormLayout(grupo)
        form.addRow("Duração do piloto", self.meses_piloto)
        form.addRow("Desconto no retainer", self.desconto_piloto_percentual)
        form.addRow("Conversão ao fim do piloto", self.percentual_conversao_pos_piloto)
        form.addRow(
            "",
            RotuloAjuda(
                "Durante o piloto o retainer sai com desconto, mas a entrega é a mesma. "
                "Quem não converte encerra o contrato e sai da carteira; 100% de "
                "conversão faz do piloto só um desconto de entrada."
            ),
        )
        return grupo

    def _grupo_capacidade(self) -> QGroupBox:
        self.horas_base_cliente_mes = CampoDecimal(0.0, 2000.0, 5.0, 1, " h")
        self.horas_base_cliente_mes.valueChanged.connect(self._mudou)
        self.horas_por_10mil_midia = CampoDecimal(0.0, 500.0, 0.5, 1, " h")
        self.horas_por_10mil_midia.valueChanged.connect(self._mudou)
        self.horas_produtivas_profissional_mes = CampoDecimal(1.0, 300.0, 5.0, 1, " h")
        self.horas_produtivas_profissional_mes.valueChanged.connect(self._mudou)
        self.utilizacao_alvo_percentual = CampoPercentual(passo=1.0)
        self.utilizacao_alvo_percentual.valueChanged.connect(self._mudou)
        self.custo_mensal_profissional = CampoMoeda(passo=250.0)
        self.custo_mensal_profissional.valueChanged.connect(self._mudou)

        grupo = QGroupBox("7. Capacidade e equipe")
        form = QFormLayout(grupo)
        form.addRow("Horas por cliente/mês (escopo pleno)", self.horas_base_cliente_mes)
        form.addRow("Horas por R$ 10 mil de verba", self.horas_por_10mil_midia)
        form.addRow("Horas produtivas por profissional/mês", self.horas_produtivas_profissional_mes)
        form.addRow("Utilização alvo", self.utilizacao_alvo_percentual)
        form.addRow("Custo mensal por profissional", self.custo_mensal_profissional)
        form.addRow(
            "",
            RotuloAjuda(
                "As horas demandadas dividem-se pela capacidade útil "
                "(horas produtivas × utilização alvo) e o resultado sobe ao próximo "
                "profissional inteiro — por isso o custo de equipe cresce em degraus."
            ),
        )
        return grupo

    def _grupo_custos(self) -> QGroupBox:
        self.custo_terceiros_percentual = CampoPercentual(passo=0.5)
        self.custo_terceiros_percentual.valueChanged.connect(self._mudou)
        self.aliquota_impostos_percentual = CampoPercentual(passo=0.5)
        self.aliquota_impostos_percentual.valueChanged.connect(self._mudou)
        self.taxa_inadimplencia = CampoPercentual(passo=0.1)
        self.taxa_inadimplencia.valueChanged.connect(self._mudou)
        self.comissao_comercial_percentual = CampoPercentual(passo=1.0)
        self.comissao_comercial_percentual.valueChanged.connect(self._mudou)

        self.tabela_custo = TabelaCusto()
        self.tabela_custo.alterado.connect(self._mudou)
        self.expressao_custo = CampoExpressao(("n", "a"), "ex.: 9000 + 120 * a")
        self.expressao_custo.alterado.connect(self._mudou)

        pagina_expressao = QWidget()
        coluna = QVBoxLayout(pagina_expressao)
        coluna.setContentsMargins(0, 0, 0, 0)
        coluna.setSpacing(4)
        coluna.addWidget(self.expressao_custo)
        coluna.addWidget(
            RotuloAjuda(
                "Padrão expr-eval, avaliada a cada mês. Variáveis: <b>n</b> (mês da simulação) "
                "e <b>a</b> (clientes ativos no mês). Nunca fica negativa.<br>"
                "Aluguel, ferramentas e marketing próprio entram aqui. Degrau por tamanho "
                "da carteira: <code>9000 + 2500 * ceil(a / 15)</code>."
            )
        )

        self.tipo_custo = SeletorTipo(
            "Lista por mês", "Expressão", self.tabela_custo, pagina_expressao
        )
        self.tipo_custo.alterado.connect(self._mudou)

        grupo = QGroupBox("8. Custos")
        layout = QVBoxLayout(grupo)
        form = QFormLayout()
        form.addRow("Terceiros (sobre o retainer)", self.custo_terceiros_percentual)
        form.addRow(
            "",
            RotuloAjuda(
                "Freelancers, produção de vídeo e gráfica repassados como custo — "
                "proporcional ao retainer faturado."
            ),
        )
        form.addRow("Impostos (sobre a receita)", self.aliquota_impostos_percentual)
        form.addRow("Inadimplência (sobre a fatura)", self.taxa_inadimplencia)
        form.addRow(
            "",
            RotuloAjuda(
                "O cliente consumiu o mês de entrega, foi faturado e não pagou: a receita do "
                "mês vira perda <b>e</b> o contrato é encerrado, saindo da carteira no mês seguinte."
            ),
        )
        form.addRow("Comissão comercial", self.comissao_comercial_percentual)
        form.addRow(
            "",
            RotuloAjuda(
                "Sobre a receita <b>recebida</b> do cliente — o que não foi pago não comissiona. "
                "Vale enquanto aquele cliente continuar na carteira."
            ),
        )
        layout.addLayout(form)
        layout.addWidget(QLabel("<b>Custo de estrutura do mês</b>"))
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
        self.tabela_comerciais.sincronizar(mes_inicio, meses)
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
            funcao_comerciais=FuncaoComerciais(
                tipo=self.tipo_comerciais.tipo(),
                expressao=self.expressao_comerciais.texto(),
                valores=self.tabela_comerciais.valores(),
            ),
            funcao_aquisicao=FuncaoAquisicao(
                tipo=self.tipo_aquisicao.tipo(),
                expressao=self.expressao_aquisicao.texto(),
                valores=self.tabela_aquisicao.valores(),
            ),
            taxa_churn_mensal=self.taxa_churn_mensal.fracao(),
            retainer_mensal_pleno=self.retainer_mensal_pleno.value(),
            taxa_setup=self.taxa_setup.value(),
            verba_midia_media=self.verba_midia_media.value(),
            fee_gestao_midia_percentual=self.fee_gestao_midia_percentual.fracao(),
            curva_escopo=CurvaEscopo(
                tipo=self.tipo_escopo.tipo(),
                expressao=self.expressao_escopo.texto(),
                valores=self.tabela_escopo.valores(),
            ),
            sazonalidade_midia=self.sazonalidade.valores(),
            meses_piloto=self.meses_piloto.value(),
            desconto_piloto_percentual=self.desconto_piloto_percentual.fracao(),
            percentual_conversao_pos_piloto=self.percentual_conversao_pos_piloto.fracao(),
            horas_base_cliente_mes=self.horas_base_cliente_mes.value(),
            horas_por_10mil_midia=self.horas_por_10mil_midia.value(),
            horas_produtivas_profissional_mes=self.horas_produtivas_profissional_mes.value(),
            utilizacao_alvo_percentual=self.utilizacao_alvo_percentual.fracao(),
            custo_mensal_profissional=self.custo_mensal_profissional.value(),
            custo_terceiros_percentual=self.custo_terceiros_percentual.fracao(),
            aliquota_impostos_percentual=self.aliquota_impostos_percentual.fracao(),
            taxa_inadimplencia=self.taxa_inadimplencia.fracao(),
            comissao_comercial_percentual=self.comissao_comercial_percentual.fracao(),
            funcao_custo_estrutura=FuncaoCusto(
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

        comerciais = parametros.funcao_comerciais
        self.expressao_comerciais.definir_texto(comerciais.expressao)
        self.tabela_comerciais.definir(
            comerciais.valores
            or lista_comerciais_padrao(metadados.data_inicio, parametros.meses_simulados),
            metadados.data_inicio,
            parametros.meses_simulados,
        )
        self.tipo_comerciais.definir_tipo(comerciais.tipo)

        aquisicao = parametros.funcao_aquisicao
        self.expressao_aquisicao.definir_texto(aquisicao.expressao)
        valores = aquisicao.valores or lista_aquisicao_padrao(
            metadados.data_inicio, parametros.meses_simulados
        )
        self.tabela_aquisicao.definir(valores, metadados.data_inicio, parametros.meses_simulados)
        self.tipo_aquisicao.definir_tipo(aquisicao.tipo)

        self.taxa_churn_mensal.definir_fracao(parametros.taxa_churn_mensal)
        self.retainer_mensal_pleno.setValue(parametros.retainer_mensal_pleno)
        self.taxa_setup.setValue(parametros.taxa_setup)
        self.verba_midia_media.setValue(parametros.verba_midia_media)
        self.fee_gestao_midia_percentual.definir_fracao(parametros.fee_gestao_midia_percentual)

        curva = parametros.curva_escopo
        self.expressao_escopo.definir_texto(curva.expressao)
        self.tabela_escopo.definir(curva.valores or lista_escopo_padrao())
        self.tipo_escopo.definir_tipo(curva.tipo)
        self.sazonalidade.definir(parametros.sazonalidade_midia)

        self.meses_piloto.setValue(parametros.meses_piloto)
        self.desconto_piloto_percentual.definir_fracao(parametros.desconto_piloto_percentual)
        self.percentual_conversao_pos_piloto.definir_fracao(
            parametros.percentual_conversao_pos_piloto
        )

        self.horas_base_cliente_mes.setValue(parametros.horas_base_cliente_mes)
        self.horas_por_10mil_midia.setValue(parametros.horas_por_10mil_midia)
        self.horas_produtivas_profissional_mes.setValue(
            parametros.horas_produtivas_profissional_mes
        )
        self.utilizacao_alvo_percentual.definir_fracao(parametros.utilizacao_alvo_percentual)
        self.custo_mensal_profissional.setValue(parametros.custo_mensal_profissional)

        self.custo_terceiros_percentual.definir_fracao(parametros.custo_terceiros_percentual)
        self.aliquota_impostos_percentual.definir_fracao(parametros.aliquota_impostos_percentual)
        self.taxa_inadimplencia.definir_fracao(parametros.taxa_inadimplencia)
        self.comissao_comercial_percentual.definir_fracao(parametros.comissao_comercial_percentual)

        custo = parametros.funcao_custo_estrutura
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
