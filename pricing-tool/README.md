# Simulador de Retorno — Agendamento para Clínicas Veterinárias

App desktop (PySide6) que projeta, mês a mês, a evolução de uma plataforma de agendamento
para clínicas veterinárias, uma empresa **fictícia** usada como cenário de exemplo. A receita
é híbrida: **transacional** (taxa fixa + % por atendimento agendado) e **recorrente**
(mensalidade por clínica). Tudo roda local: sem backend, sem rede, com o JSON exportado
como único artefato de persistência.

## Rodar

```bash
./run.sh          # ou: uv run main.py
```

No Windows, use `run.bat` — um duplo clique basta. Ele instala o `uv` se não houver,
e o `uv` baixa o Python 3.12 e as dependências na primeira execução. Só a primeira
vez precisa de internet.

## Como usar

O app abre já com o **preset padrão** carregado e simulado. A partir daí:

| Ação | Atalho | O que faz |
|---|---|---|
| Preset padrão | `Ctrl+N` | Recarrega o cenário padrão e simula |
| Definir como padrão | — | Grava os parâmetros atuais como o padrão que abre com o app |
| Importar JSON | `Ctrl+O` | Abre uma simulação salva (ver os dois modos abaixo) |
| Exportar JSON | `Ctrl+S` | Grava `parametros` + `resultados` em `simulacoes/` |
| Simular | `F5` | Roda o motor com os parâmetros atuais |
| Calcular sorte | `F6` | Roda N simulações com dados e diz quantas bateram as suas metas |

Ao importar um arquivo que já tem `resultados`, o app pergunta como abrir:

- **Ver resultados salvos** — mostra o que está no arquivo, sem recalcular nada. O
  formulário fica travado e uma faixa amarela indica o modo.
- **Editar e reprocessar** — carrega os `parametros` no formulário, roda o motor e
  gera um bloco `resultados` novo.

Se `resultados` estiver ausente ou nulo, o modo de re-simulação é forçado.

## Preset padrão

**Definir como padrão** grava os parâmetros da tela em `padrao.json`, na raiz da ferramenta —
só os `parametros` e `metadados`, sem `resultados`. A partir daí é ele que abre com o app e
que o `Ctrl+N` recarrega. O mesmo botão oferece **restaurar de fábrica**, que apaga o arquivo
e devolve o preset abaixo. O arquivo é local e está no `.gitignore`; se estiver ilegível, o
app avisa e cai no de fábrica em vez de quebrar.

O preset de fábrica é deliberadamente **conservador**, em 12 meses:

| Parâmetro | Valor |
|---|---|
| Horizonte | 12 meses |
| Vendedores | tabela por mês — 2 desde o início |
| Aquisição | expressão `2 * v` — duas clínicas por vendedor por mês |
| Churn mensal | 3% |
| Consultórios por clínica | 4 |
| Vagas por consultório/dia · dias/mês | 16 · 26 |
| Curva de maturação | expressão `min(0.3, 0.05 * t)` — regime de 30% no 6º mês |
| Sazonalidade | 0,90 a 1,10 (mais forte no fim do ano) |
| Valor médio por atendimento | R$ 180 |
| Taxa por atendimento | R$ 1,50 + 2% |
| Mensalidade · trial · conversão | R$ 149 · 1 mês · 60% |
| Custo operacional | expressão `4500` — estrutura enxuta e plana |
| Processamento | 0% do volume — o pagamento cai direto na conta da clínica |
| Inadimplência | 4% ao mês sobre a fatura |
| Comissão do vendedor | 20% da receita recebida |

Nesse cenário o resultado acumulado fica negativo nos três primeiros meses e o payback chega
no **mês 4**. Em 12 meses: R$ 252,0 mil de receita, R$ 48,4 mil de comissão e R$ 139,6 mil de
resultado, com cerca de 22 clínicas ativas no fim. Cada vendedor leva R$ 24,2 mil no período —
número magro que o modelo mostra de propósito.

## Entrada de dados

Fora dos três campos de `expressao`, nenhum input é texto livre: percentuais e valores
têm spin box com mínimo e máximo, o mês inicial é um seletor mês/ano, e a escolha entre
lista e expressão é por radio. As listas por mês (vendedores, aquisição e custo) são geradas a partir do
mês inicial e do horizonte, então nunca têm lacuna nem mês fora de ordem.

As expressões seguem o padrão [expr-eval](https://github.com/silentmatt/expr-eval)
(avaliadas por [`py-expression-eval`](https://pypi.org/project/py-expression-eval/)) e são
validadas enquanto você digita:

- **Vendedores** — variável `n` (mês da simulação). Arredondado e nunca negativo.
- **Aquisição** — variáveis `n` (mês da simulação) e `v` (vendedores ativos no mês). É por
  `v` que o time vira alavanca explícita: `2 * v` são duas clínicas por vendedor por mês, e
  contratar mais gente é mexer na tabela de vendedores, não reescrever a fórmula. O resultado
  é arredondado para o inteiro mais próximo e nunca fica negativo.
- **Maturação** — variável `t` (mês desde a ativação da clínica, a partir de 1). O resultado
  é limitado entre 0 e 1.
- **Custo operacional** — variáveis `n` (mês da simulação) e `a` (clínicas ativas no mês). O
  resultado nunca fica negativo. É aqui que entram os degraus de estrutura, que uma soma de
  custo fixo com custo por clínica não consegue representar:
  `8000 + 2500 * ceil(a / 50)` contrata um suporte a cada 50 clínicas, e
  `if(n > 6, 20000, 8000)` sobe a estrutura depois do sexto mês.

Essa normalização é sempre aplicada, mesmo que a fórmula já use `min`/`max`.

## Inadimplência

O pagamento do atendimento cai direto na conta da clínica; a plataforma fatura comissão e
mensalidade no fim do mês. Isso zera o custo de processamento — a taxa da operadora de
pagamento é da clínica — mas cria risco de crédito, e é isso que a `taxa_inadimplencia` modela.

A clínica inadimplente operou o mês inteiro, então o mês tem os dois efeitos:

- a **receita faturada** daquela fatia vira perda, lançada nos custos (`perda_inadimplencia`);
- a clínica **perde o acesso à agenda online e sai da base**, contada em `clinicas_inadimplentes`
  e fora da simulação a partir do mês seguinte.

O retorno de quem quita a dívida não é modelado: a saída é definitiva, como o churn. Por
isso a vida média do LTV é `1 ÷ (churn + inadimplência)` — a base esvazia pelos dois lados.

O segundo efeito pesa muito mais que o primeiro: além da fatura não paga, a base final
encolhe e leva junto a receita de todos os meses seguintes.

## Comissão do vendedor

Os vendedores não têm fixo: ganham `comissao_vendedor_percentual` sobre a receita
**recebida** das clínicas que trouxeram, enquanto a clínica continuar na carteira deles.
Por isso a comissão incide depois do desconto de inadimplência — fatura que não foi paga
não comissiona ninguém.

Não há bounty por clínica assinada: sem taxa de implantação, pagar na assinatura premia
volume em vez do acompanhamento contínuo, que é o trabalho que sustenta a recorrência.
Não existe custo de aquisição por clínica: gasto de marketing, se houver, é mensal e vai
na expressão de custo operacional.

Não há piso nem fixo: a comissão é a remuneração inteira, o que deixa a receita dos
primeiros meses bem magra. O modelo não esconde isso, e é informação para levar à mesa
antes de fechar o acordo.

## Os dois motores

O laço mensal é um só; o que muda entre os modos é **como a base perde clínicas**, isolado
em `motor.Continua` e `motor.Sorteio`:

- **Determinístico** (`Continua`) — sai a fração exata. Com 10 clínicas e churn de 3%, ficam
  9,7. É o modo de todos os botões normais: mesmos parâmetros, sempre o mesmo número.
- **Com dados** (`Sorteio`) — cada clínica do cohort é um ensaio de Bernoulli, sorteado por
  binomial. As clínicas ficam inteiras: 10 clínicas viram 10 ou 9, nunca 9,7.

Por rodarem o mesmo laço, os dois não podem divergir por descuido — não existe um segundo
motor para sair de sincronia. Zerando churn, inadimplência e não-conversão, os dois modos
dão o mesmo número.

Isso importa porque azar é **caminho, não média**: perder uma clínica no mês 1 custa a receita
dela em todos os meses seguintes, e perder no mês 7 quase não custa. O modo com dados produz
essa dependência de trajetória; o determinístico, por construção, distribui a perda de forma
uniforme no tempo.

A inadimplência é apurada **por cohort**, não sobre a receita média da base — clínica nova
fatura muito menos que clínica madura, e cobrar a média superestima a perda.

## Calcular sorte

`F6` mantém todos os parâmetros fixos, pergunta duas metas — o **resultado acumulado** do
período e o **resultado líquido do último mês** — mais quantas rodadas simular, e responde
quantas delas bateram as duas. Roda em segundo plano, com barra de progresso e cancelamento —
o resultado parcial do que já rodou continua valendo.

As duas metas juntas separam o cenário que fecha no azul por inércia daquele que termina
**ganhando dinheiro no ritmo atual**: dá para terminar com acumulado alto e o último mês já
minguando, e o inverso também acontece. Por isso o diálogo mostra, além do total que bateu as
duas, quantas rodadas bateram cada meta isoladamente — é assim que se vê qual das duas
está travando o cenário.

Além da porcentagem, o diálogo mostra em que **percentil** o número determinístico caiu e a
faixa p10/p50/p90 das rodadas, tanto do acumulado quanto do último mês. Proporção é uma
estatística estável: 10 mil rodadas dão a resposta com menos de meio ponto de incerteza, bem
melhor que a média, que oscila mais de 1%.

## Contrato JSON

`versao_schema` (hoje `1.0`), `metadados`, `parametros` e `resultados` — este último separado
justamente para permitir os dois modos de abertura. Percentuais são gravados como fração
(`0.02` = 2%), do mesmo jeito que `ocupacao_media_percentual` nos resultados. O arquivo sai
indentado e com acentos preservados, para dar pra editar na mão.

Na importação, versão de schema diferente vira aviso (nunca erro silencioso), campo ausente
assume o default documentado e valor fora do domínio é corrigido — tudo listado num diálogo
de avisos.

Os arquivos vão para `simulacoes/`, que está no `.gitignore`.

## Fim do trial

A mensalidade é o que mantém a clínica na plataforma: sem assinatura não há agenda online.
Então a conversão ao fim do trial é modelada como **churn**, não como camada gratuita — a
clínica que não assina sai da base no mês em que a cobrança começaria, e some do churn do
mês. Quem converte paga integralmente a partir dali.

Deixar a conversão em 100% desliga o efeito e faz o trial ser só um adiamento da cobrança.

## KPIs derivados

A maioria é soma direta do período. Os três que envolvem convenção:

- **Payback** — primeiro mês com resultado acumulado ≥ 0.
- **LTV médio** — receita média por clínica ativa/mês × vida média, com vida média =
  1 ÷ (churn + inadimplência).
- **Crescimento médio da base** — média geométrica da variação mês a mês das clínicas ativas.

## Estrutura

```
main.py                     entrada
pricing_tool/
  calendario.py             aritmética de meses YYYY-MM
  expressoes.py             expr-eval + normalização de domínio
  parametros.py             dataclasses dos parâmetros e o preset padrão
  motor.py                  cálculo mês a mês e KPIs
  documento.py              import/export, defaults e validação
  ui/
    janela.py               janela, barra de ações e modos de abertura
    formulario.py           formulário de parâmetros
    tabelas_entrada.py      listas de aquisição e de maturação
    campos.py               campos restritos ao domínio
    resultados.py           KPIs e tabela mensal
    graficos.py             gráficos (QtCharts)
    formato.py / estilo.py  formatação pt-BR e folha de estilo
```
