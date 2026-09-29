# Simulador de Retorno — Agência de Marketing

App desktop (PySide6) que projeta, mês a mês, a evolução de uma agência de marketing digital,
uma empresa **fictícia** usada como cenário de exemplo. A receita vem de três fontes:
**retainer** mensal, **fee de gestão de mídia** (percentual sobre a verba do cliente) e
**taxa de setup** cobrada uma única vez. O custo dominante é a **equipe**, dimensionada pelas
horas que o escopo e a verba de cada cliente exigem. Tudo roda local: sem backend, sem rede,
com o JSON exportado como único artefato de persistência.

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

## Como o modelo funciona

Cada mês, a carteira é dividida em **cohorts** (clientes que entraram no mesmo mês). Para cada
cohort, o **escopo em execução** (`curva_escopo`, de 0 a 100% do escopo pleno) escala tudo de uma vez:

- o **retainer** faturado (`retainer_mensal_pleno × escopo`, com desconto durante o piloto);
- a **verba de mídia** gerenciada (`verba_midia_media × escopo × sazonalidade`), da qual a
  agência recebe apenas o **fee** — a verba em si é do cliente e não entra na receita;
- as **horas** de trabalho: `horas_base_cliente_mes × escopo` mais `horas_por_10mil_midia`
  para cada R$ 10 mil de verba sob gestão.

Somadas as horas de todos os cohorts, a **equipe** é dimensionada por
`ceil(horas ÷ (horas_produtivas × utilização_alvo))` — profissionais inteiros. É a interação
central de uma agência: a receita cresce de forma suave, mas o custo de equipe sobe em
**degraus**, e a margem oscila conforme a carteira se aproxima de cada nova contratação.

Outras interações que o modelo captura:

- **Verba alta é dupla:** rende mais fee, mas também consome mais horas de otimização.
- **Sazonalidade da verba** (Black Friday, Natal) infla fee e horas no pico, podendo
  forçar contratação antes da hora.
- **Piloto:** nos primeiros meses o retainer sai com desconto, mas a entrega é a mesma;
  ao fim do piloto, quem não converte sai da carteira.
- **Setup** entra só no mês de ativação do cliente, dando fôlego ao caixa no início do contrato.
- **Comercial** é remunerado só por comissão sobre a receita **recebida**, e o número de
  comerciais é a alavanca de aquisição (`c` na expressão de novos clientes).

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
| Comerciais | tabela por mês — 2 desde o início |
| Aquisição | expressão `1 * c` — um contrato fechado por comercial por mês |
| Churn mensal | 4% |
| Retainer mensal (escopo pleno) | R$ 7.500 |
| Taxa de setup | R$ 2.500, cobrada uma vez |
| Verba de mídia gerenciada · fee | R$ 15.000 por cliente/mês · 12% |
| Rampa de escopo | expressão `min(1, 0.5 + 0.1 * t)` — 60% no 1º mês, pleno no 5º |
| Sazonalidade da verba | 0,80 (jan) a 1,40 (nov) |
| Piloto · desconto · conversão | 1 mês · 50% · 70% |
| Horas por cliente/mês (escopo pleno) | 45 h + 4 h por R$ 10 mil de verba |
| Horas produtivas · utilização alvo | 140 h por profissional/mês · 75% |
| Custo mensal por profissional | R$ 7.000 |
| Terceiros | 10% do retainer |
| Impostos | 8% da receita |
| Inadimplência | 3% ao mês sobre a fatura |
| Comissão comercial | 8% da receita recebida |
| Custo de estrutura | expressão `9000 + 120 * a` — base fixa mais R$ 120 por cliente ativo |

Partindo de setembro, o resultado acumulado fica negativo nos primeiros seis meses e o payback
chega no **mês 7**. Em 12 meses: R$ 705,7 mil de receita (R$ 513,8 mil de retainer, R$ 131,9 mil
de fee de mídia e R$ 60,0 mil de setup), R$ 301,0 mil de custo de equipe e R$ 101,7 mil de
resultado — margem líquida de 14,4%. A carteira termina com 12 clientes e uma equipe de 6
profissionais, com 61% de utilização média. Cada comercial leva R$ 27,4 mil no período —
número magro que o modelo mostra de propósito.

## Entrada de dados

Fora dos três campos de `expressao`, nenhum input é texto livre: percentuais e valores
têm spin box com mínimo e máximo, o mês inicial é um seletor mês/ano, e a escolha entre
lista e expressão é por radio. As listas por mês (comerciais, aquisição e custo) são geradas a
partir do mês inicial e do horizonte, então nunca têm lacuna nem mês fora de ordem.

As expressões seguem o padrão [expr-eval](https://github.com/silentmatt/expr-eval)
(avaliadas por [`py-expression-eval`](https://pypi.org/project/py-expression-eval/)) e são
validadas enquanto você digita:

- **Comerciais** — variável `n` (mês da simulação). Arredondado e nunca negativo.
- **Aquisição** — variáveis `n` (mês da simulação) e `c` (comerciais ativos no mês). É por
  `c` que o time comercial vira alavanca explícita: `2 * c` são dois contratos por comercial
  por mês, e contratar mais gente é mexer na tabela de comerciais, não reescrever a fórmula.
  O resultado é arredondado para o inteiro mais próximo e nunca fica negativo.
- **Escopo** — variável `t` (mês desde a ativação do cliente, a partir de 1). O resultado é
  limitado entre 0 e 1.
- **Custo de estrutura** — variáveis `n` (mês da simulação) e `a` (clientes ativos no mês). O
  resultado nunca fica negativo. É aqui que entram aluguel, ferramentas e o marketing da
  própria agência, inclusive em degraus que uma soma de custo fixo com custo por cliente não
  representa: `9000 + 2500 * ceil(a / 15)` abre uma nova frente de gestão a cada 15 clientes, e
  `if(n > 6, 20000, 9000)` sobe a estrutura depois do sexto mês.

Essa normalização é sempre aplicada, mesmo que a fórmula já use `min`/`max`.

## Inadimplência

O cliente consome o mês inteiro de entrega antes de ser cobrado. Se não paga, o mês tem os
dois efeitos:

- a **receita faturada** daquela fatia vira perda, lançada nos custos (`perda_inadimplencia`);
- o **contrato é encerrado**: o cliente sai da carteira, contado em `clientes_inadimplentes`,
  e fica fora da simulação a partir do mês seguinte.

O retorno de quem quita a dívida não é modelado: a saída é definitiva, como o churn. Por
isso a vida média do LTV é `1 ÷ (churn + inadimplência)` — a carteira esvazia pelos dois lados.

A inadimplência é apurada **por cohort**, não sobre a receita média da carteira — cliente
novo, em escopo reduzido e piloto com desconto, fatura muito menos que cliente maduro, e
cobrar a média superestima a perda. O efeito mais caro não é a fatura em si, e sim a
carteira menor: ela leva junto a receita de todos os meses seguintes.

## Comissão comercial

Os comerciais não têm fixo: ganham `comissao_comercial_percentual` sobre a receita
**recebida** dos clientes que trouxeram, enquanto o cliente continuar na carteira. Por
isso a comissão incide depois do desconto de inadimplência — fatura que não foi paga
não comissiona ninguém.

Não há bounty por contrato assinado: com um setup único e pequeno diante do retainer, pagar na
assinatura premia volume em vez do relacionamento contínuo, que é o que sustenta a recorrência.
Não existe custo de aquisição por cliente: gasto de marketing próprio, se houver, é mensal
e vai na expressão de custo de estrutura.

Não há piso nem fixo: a comissão é a remuneração inteira, o que deixa a receita dos
primeiros meses bem magra. O modelo não esconde isso, e é informação para levar à mesa
antes de fechar o acordo.

## Os dois motores

O laço mensal é um só; o que muda entre os modos é **como a carteira perde clientes**, isolado
em `motor.Continua` e `motor.Sorteio`:

- **Determinístico** (`Continua`) — sai a fração exata. Com 10 clientes e churn de 4%, ficam
  9,6. É o modo de todos os botões normais: mesmos parâmetros, sempre o mesmo número.
- **Com dados** (`Sorteio`) — cada cliente do cohort é um ensaio de Bernoulli, sorteado por
  binomial. Os clientes ficam inteiros: 10 clientes viram 10 ou 9, nunca 9,6.

Por rodarem o mesmo laço, os dois não podem divergir por descuido — não existe um segundo
motor para sair de sincronia. Zerando churn, inadimplência e não-conversão, os dois modos
dão o mesmo número.

Isso importa porque azar é **caminho, não média**: perder um cliente no mês 1 custa a receita
dele em todos os meses seguintes, e perder no mês 7 quase não custa. O modo com dados produz
essa dependência de trajetória; o determinístico, por construção, distribui a perda de forma
uniforme no tempo.

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

## Fim do piloto

O piloto é um período de retainer com desconto (`desconto_piloto_percentual`, com 100% = grátis)
em que a agência entrega o mesmo trabalho. Ao fim dele, a conversão é modelada como **churn**:
o cliente que não decide continuar sai da carteira no mês em que o retainer cheio começaria, e
some do churn do mês. Quem converte paga integralmente a partir dali.

Deixar a conversão em 100% desliga o efeito e faz o piloto ser só um desconto de entrada.
Com `meses_piloto = 0` a decisão acontece já no primeiro mês.

## KPIs derivados

A maioria é soma direta do período. Os que envolvem convenção:

- **Payback** — primeiro mês com resultado acumulado ≥ 0.
- **Margem líquida** — resultado líquido do período ÷ receita do período.
- **Utilização média da equipe** — média, nos meses com equipe, de horas demandadas ÷ horas
  produtivas totais; fica abaixo da utilização alvo porque a equipe sobe em profissionais inteiros.
- **LTV médio** — receita média por cliente ativo/mês × vida média, com vida média =
  1 ÷ (churn + inadimplência).
- **Crescimento médio da carteira** — média geométrica da variação mês a mês dos clientes ativos.

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
    tabelas_entrada.py      listas de comerciais, aquisição, custo e escopo
    campos.py               campos restritos ao domínio
    resultados.py           KPIs e tabela mensal
    graficos.py             gráficos (QtCharts)
    formato.py / estilo.py  formatação pt-BR e folha de estilo
```
