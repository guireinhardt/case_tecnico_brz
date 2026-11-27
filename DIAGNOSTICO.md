# Diagnóstico, prevenção e dúvidas

**Resumo.** Os números não batem porque o script soma pagamentos repetidos,
soma estornos como se fossem pagamentos e descarta em silêncio o que não
consegue importar. Além disso, a conferência compara os arquivos do jeito
que estão escritos, mas eles chegam em formatos diferentes: isso gera
divergências falsas e esconde as verdadeiras. O relatório completo da
limpeza está em [saida/relatorio.md](saida/relatorio.md).

## 1. Diagnóstico

Ordenado do mais grave para o menos grave. As linhas citadas são do arquivo
original. Nesta seção, nos arquivos JSON, a linha é a do `{` que abre o
registro (a mesma usada em `saida/relatorio.md`); na seção 2, algumas
citações apontam direto a linha do campo.

```
 D7 tribunal.csv fora do leiaute ─┐
 D8 documentação desatualizada ───┼─► D6 comparação exata ─► D5 divergências reais escondidas
 identificador CNJ em 2 formas ───┘
 D9 datas em 3 formatos ─────────────► D4 prazo errado
 D10 schema sem unicidade/versão ────► D1 total inflado
                                  └──► D2 descarte silencioso
 D8 documentação ────────────────────► D3 estorno somado
```

### D1. A importação soma eventos repetidos e infla o total pago — causa raiz

- **O que acontece.** No processo 0012345, o arquivo traz o ev-001 duas
  vezes, uma com 15.000,00 e outra com 15.500,00, e o ev-002 duas vezes com
  2.500,50. Somando todos os valores, como o script faz hoje, o total dá
  **35.501,00**. O valor real é **18.000,50**: o ev-001 é um único pagamento
  que o tribunal corrigiu de 15.000,00 para 15.500,00 (mesmo `evento_id`,
  `atualizado_em` mais recente), e o ev-002 é uma cópia repetida, que só
  conta uma vez.
- **Evidência.** ev-001 em `pagamentos.json:2` e `:66`; ev-002 em `:10` e
  `:26`. O tribunal envia todo dia os eventos dos **últimos 7 dias**, o
  script **soma cada valor** ao total e, quando falha, o operador roda **o
  mesmo arquivo de novo** (`ENUNCIADO.md`, fluxo, passos 1 e 2). Nada no
  banco impede o mesmo evento de entrar mais de uma vez: `evento_id` não é
  único (`schema.sql:11`).
- **Impacto.** O total pago fica quase o dobro do real nesse processo. Como
  cada evento aparece em até 7 arquivos diários, a soma pode chegar a 7
  vezes o valor real. Com o total pago inflado, o saldo devedor parece menor
  do que é, e a equipe deixa de cobrar o que ainda é devido.
- **Relação.** Causa. Viabilizada pela falta de unicidade no banco (D10).

### D2. Eventos que não importam são descartados sem aviso — causa

- **O que acontece.** Hoje, quando um pagamento não consegue ser importado,
  ele é descartado em silêncio (`ENUNCIADO.md`, fluxo, passo 5). Pelas
  regras do banco, quatro eventos do arquivo cairiam nisso: ev-004 sem valor
  (`pagamentos.json:34`, viola `NOT NULL`), ev-009 com valor −200 (`:82`,
  viola `CHECK (valor > 0)`), ev-010 com o processo vazio (`:90`) e ev-011
  (`:98`), cujo precatório 0067890 não existe no hub, o que viola a chave
  estrangeira.
- **Impacto.** O ev-011 é um pagamento real de R$ 4.000,00, de um precatório
  que está na lista oficial do tribunal (`tribunal.csv:6`). Ele some do
  total e ninguém fica sabendo. Os R$ 750,00 do ev-010 nem têm dono
  identificado.
- **Relação.** Causa. Agravado por D5 (o 0067890 falta no cadastro).

### D3. O estorno é somado como se fosse pagamento — causa

- **O que acontece.** A documentação diz que o tipo é **sempre
  "pagamento"** (`DOCUMENTACAO_TRIBUNAL.md:15`), e o script soma cada valor.
  Mas o ev-007 (`pagamentos.json:58`) chega como `tipo: "estorno"` de
  5.000,00, no mesmo processo e no dia seguinte ao pagamento ev-006 (`:50`).
  Somando os dois, o total dá **10.000,00**. O `schema.sql` aceita o tipo
  estorno (`schema.sql:12`), mas o processo de importação não sabia dele.
- **Impacto.** O processo 0034567 aparece com 10.000,00 pagos, quando o
  correto é **0,00**: o valor foi pago e depois devolvido.
- **Relação.** Causa, consequência da documentação desatualizada (D8).

### D4. O prazo de pagamento no hub está errado em 2 de 5 precatórios — causa

- **O que acontece.** Pela regra do `ENUNCIADO.md`, quem é apresentado até
  2 de abril tem prazo até 31/12 do ano seguinte. Dois precatórios estão
  errados no hub, por motivos diferentes:
  - **0012345, erro de regra.** Apresentado em 02/04/2025 (só a data, sem
    hora nem fuso). O hub diz **2027-12-31** (`hub.csv:2`), mas o correto é
    **2026-12-31**: "até 2 de abril" inclui o próprio dia 2.
  - **0056789, erro de fuso.** Apresentado em `2025-04-03T01:00:00Z`
    (`apresentacoes.json:18`). O `Z` é UTC; em Brasília eram 22h do dia
    **2**. O hub diz **2027-12-31** (`hub.csv:6`), mas o correto é
    **2026-12-31**.
  - O hub ainda dá prazos diferentes para dois precatórios apresentados no
    mesmo dia: 0012345 → 2027 e 0045678 → 2026 (`hub.csv:2` e `:5`). Nenhuma
    regra única explica os dois; pode ser bug ou edição manual (dúvida O3).
- **Impacto.** A equipe usa o prazo para priorizar a carteira. Esses
  precatórios aparecem com **um ano a mais** de prazo do que têm de fato, e
  ficam para trás na fila.
- **Relação.** Causa. Agravada pelos formatos de data misturados (D9).

### D5. Divergências reais de cadastro entre tribunal e hub — consequência

- **Evidência.**
  - 0023456: valor de face **30.000,00** no tribunal (`tribunal.csv:3`) e
    **31.000,00** no hub (`hub.csv:3`).
  - 0045678: ente devedor **União** no tribunal (`tribunal.csv:5`) e
    **Município de Santos** no hub (`hub.csv:5`).
  - 0067890 está no tribunal (`tribunal.csv:6`) e **não está no hub**.
  - 0056789 está no hub (`hub.csv:6`) e **não está no tribunal**.
- **Impacto.** Valor de face errado distorce o saldo devedor; ente errado
  significa cobrar o devedor errado; um precatório fora do sistema não é
  acompanhado (e seus pagamentos caem em D2).
- **Relação.** Consequência: a conferência manual não consegue achar essas
  diferenças no meio dos falsos alarmes de D6.

### D6. A conferência "exatamente como está escrito" gera falsos alarmes — consequência

- **Evidência.** O operador compara nome do ente e número do processo
  literalmente (`ENUNCIADO.md`, fluxo, passo 3). Mas o mesmo ente vem como
  `MUNICIPIO DE SAO PAULO` (`hub.csv:2`) e `Município de São Paulo`
  (`tribunal.csv:2`); o mesmo processo vem com máscara (`tribunal.csv:3`) e
  sem (`hub.csv:3`); e lido como UTF-8, o `tribunal.csv` mostra
  `Munic�pio de S�o Paulo` em todas as linhas.
- **Impacto.** Praticamente toda linha parece divergente. As divergências
  reais de D5 ficam escondidas no ruído, e o 0023456 parece ser dois
  processos diferentes, um em cada arquivo.
- **Relação.** Consequência de D7 e D8.

### D7. O `tribunal.csv` não segue o leiaute documentado — causa

- **Evidência.** A documentação define UTF-8, separador vírgula e ponto
  decimal (`DOCUMENTACAO_TRIBUNAL.md:20` a `:26`). O arquivo está em
  **Windows-1252** (o byte `0xED`, "í" de "Município", na posição 72 é
  inválido em UTF-8), usa **`;`** como separador, **CRLF** nas quebras de
  linha e valores no formato brasileiro (`45.000,00`).
- **Hipótese.** Essa combinação é exatamente o que o Excel em português
  produz ao salvar um CSV, e o fluxo diz que o operador "abre o arquivo no
  Excel, confere, **salva**" (`ENUNCIADO.md`, passo 3). Não dá para
  confirmar sem o arquivo original do e-mail (dúvida O1). Se confirmado, o
  Excel também é um risco para os números: um processo sem máscara vira
  número e perde os zeros à esquerda.
- **Relação.** Causa de D6.

### D8. A documentação do tribunal está desatualizada e incompleta — causa

- **Evidência.** Os dados contradizem a documentação em quase todo campo:
  `tipo` "sempre pagamento", mas chega `estorno` (`pagamentos.json:58`);
  `valor` é número, mas chega `"2.500,50"` como texto (`:10`); data
  AAAA-MM-DD, mas chega `10/04/2025` (`:10`); processo com máscara, mas chega
  sem (`:42`). A documentação não descreve o `apresentacoes.json`, não define
  fuso horário, campos obrigatórios, se um `evento_id` repetido é uma nova
  versão nem se o `tribunal.csv` é a lista completa.
- **Relação.** Causa de D3, D7 e parte de D1.

### D9. A data de apresentação chega em três formatos — causa

- **Evidência.** No mesmo campo `apresentado_em`: só data (`2025-04-02`,
  `apresentacoes.json:2`), data e hora em −03:00 (`:14`) e data e hora em
  UTC (`2025-04-03T01:00:00Z`, `:18`). O hub copia o texto como veio
  (`hub.csv:5` e `:6`).
- **Impacto.** Quem lê a data sem considerar o fuso erra o dia, e o dia
  decide o ano do prazo (D4).
- **Relação.** Causa de D4.

### D10. O banco não protege contra nenhum desses erros — causa

- **Evidência.** `schema.sql`: `evento_id` sem `UNIQUE` e sem coluna de
  versão (`atualizado_em`); `numero_processo CHAR(20)`, que completa com
  espaços um número curto e não cabe o formato com máscara (25 caracteres);
  não há coluna para a data de apresentação nem para o prazo (que o hub
  exporta); não há onde registrar o que foi recusado; o "total pago" do
  fluxo não está no schema, sinal de que é acumulado fora dele (dúvida O2).
- **Relação.** Causa de D1 e D2.

### Observações menores

- **Dígito verificador.** Os 6 números de processo têm DV inválido pelo
  módulo 97 (Res. CNJ 65/2008). É coerente com "processos e valores são
  fictícios" (`ENUNCIADO.md:3`); a limpeza só alerta (P9).
- **Pagamento antes da apresentação.** O ev-001 foi pago em 10/03/2025
  (`pagamentos.json:66`) e o precatório 0012345 foi apresentado em
  02/04/2025 (`apresentacoes.json:2`). Fica como alerta e dúvida (O7).

### O que a limpeza entrega

`python -m limpeza` lê os arquivos como vieram e grava em `saida/`:

| Eventos de entrada | Aceitos | Descartados | Em dúvida |
|---|---|---|---|
| 13 | 8 | 4 | 1 |

| Processo | Situação | Total pago |
|---|---|---|
| 0012345-10.2019.8.26.0053 | divergente (prazo) | 18.000,50 |
| 0023456-21.2020.8.26.0053 | divergente (valor de face) | 9.200,00 |
| 0034567-32.2018.8.26.0405 | conferido | 0,00 |
| 0045678-43.2021.5.02.0011 | divergente (ente devedor) | 3.000,00 |
| 0067890-65.2016.8.26.0053 | ausente no hub | 4.000,00 |
| 0056789-54.2017.4.03.6100 | ausente no tribunal (e prazo) | 0,00 |

Os totais foram conferidos contra um gabarito calculado à mão
(`tests/test_gabarito.py`).

## 2. Premissas adotadas na limpeza

Decisões tomadas onde a documentação é omissa ou contraditória. Cada uma
está coberta por testes e tem uma dúvida correspondente na seção 4.

| # | Premissa | Evidência | Dúvida |
|---|---|---|---|
| P1 | Vírgula é sempre separador decimal (padrão brasileiro). Texto com notação americana (`2,500.50`) é rejeitado, não interpretado. | `pagamentos.json:13` e `tribunal.csv:2-6` usam o padrão brasileiro; nenhum arquivo usa o americano | T1 |
| P2 | Valor com mais de 2 casas decimais é rejeitado, não arredondado: arredondar exige escolher um critério (meio para cima ou meio para o par) que ninguém documentou, e os dois dão resultados diferentes. | `schema.sql:13` (`NUMERIC(15,2)` arredondaria em silêncio). Caso não ocorre nos dados atuais. | T2 |
| P3 | Valor zero ou negativo é rejeitado. | `schema.sql:13` (`CHECK (valor > 0)`) | T3 |
| P4 | Valor com símbolo de moeda (`R$`) é rejeitado como formato não reconhecido. | Caso não ocorre nos dados atuais. | T1 |
| P5 | `tipo: "estorno"` é aceito e subtrai do total pago, apesar de a documentação dizer "sempre pagamento". | `schema.sql:12` já prevê estorno com valor positivo; ev-007 (`pagamentos.json:59-64`) tem o mesmo processo e valor do ev-006, um dia depois | T4 |
| P6 | Valor negativo com `tipo: "pagamento"` fica **em dúvida**, fora dos totais: não há pagamento anterior para estornar e o total do processo ficaria negativo. | ev-009 (`pagamentos.json:83-88`) é o único evento do processo 0056789 | T3 |
| P7 | A chave de cruzamento do processo são os 20 dígitos do CNJ, sem máscara; relatórios exibem a forma com máscara. As duas formas se convertem uma na outra sem perda. | `schema.sql:3` (`CHAR(20)` não comporta os 25 caracteres da forma com máscara); `hub.csv:3` e `pagamentos.json:44` trazem o número sem máscara | T5 |
| P8 | Só são aceitas as duas formas vistas nos dados: máscara completa `NNNNNNN-DD.AAAA.J.TR.OOOO` ou exatamente 20 dígitos. Número sem máscara é aceito, mas registrado como correção (descumpre o leiaute). Na forma com máscara, o número sequencial (`NNNNNNN`) com menos de 7 dígitos é completado com zeros à esquerda e registrado como correção; os demais segmentos precisam ter o tamanho exato, e sem máscara são exigidos exatamente 20 dígitos. | `DOCUMENTACAO_TRIBUNAL.md:12` define a máscara; os separadores delimitam o segmento, então a posição dos zeros não é ambígua. Risco aceito: se o dígito faltou por erro de digitação (e não por zero perdido), o número completado aponta para outro processo. Caso não ocorre nos dados atuais. | T5, T7 |
| P9 | Dígito verificador inválido gera **alerta**, não rejeição. Os 6 números do caso têm DV inválido (cálculo módulo 97, Res. CNJ 65/2008); rejeitar esvaziaria a base inteira. | todos os processos de `tribunal.csv`, `hub.csv`, `pagamentos.json` e `apresentacoes.json`; ENUNCIADO.md:3 ("processos e valores são fictícios") | T6 |
| P10 | Toda data é convertida para um único padrão, AAAA-MM-DD (o da documentação). Data com barras é sempre lida como DD/MM/AAAA (padrão brasileiro, como a vírgula em P1) e registrada como correção; data impossível (`31/02`) é rejeitada. | `DOCUMENTACAO_TRIBUNAL.md:14` define AAAA-MM-DD; ev-002 traz `10/04/2025` (`pagamentos.json:14` e `:30`), e o `atualizado_em` do mesmo evento (`2025-04-10`, linha 16) confirma dia/mês | T8 |
| P11 | Data com hora (`apresentado_em`) vira a data correspondente no fuso de São Paulo (`America/Sao_Paulo`, com as regras históricas de horário de verão). | `apresentacoes.json:20` e `hub.csv:6` trazem `2025-04-03T01:00:00Z`: dia 3 em UTC, mas 22h do dia 2 em Brasília, o que muda o prazo do processo 0056789 de 2027 para 2026. Os tribunais dos dados (TJSP, TRT2, TRF3) têm sede em São Paulo, então horário de Brasília e horário local do tribunal coincidem | T9 |
| P12 | Data com hora **sem fuso** é rejeitada. O Brasil tem quatro fusos (−2 a −5) e, perto da meia-noite, a escolha do fuso decide o dia. | Caso não ocorre nos dados atuais. | T9 |
| P13 | `atualizado_em` é mantido como data e hora completas e **exige fuso**: é ele que decide qual versão de um evento repetido vale, e sem fuso a ordem entre versões pode sair errada. | todos os `atualizado_em` de `pagamentos.json` trazem `-03:00`; ev-001 tem duas versões (`pagamentos.json:8` e `:72`) | T10 |
| P14 | Quando tribunal e hub divergem em valor de face ou ente devedor, **o tribunal prevalece** na base limpa e o valor do hub fica registrado como divergência. Precatório que só existe em uma das fontes entra com alerta. | o tribunal é a fonte oficial da dívida; 0023456 (`tribunal.csv:3` x `hub.csv:3`), 0045678 (`tribunal.csv:5` x `hub.csv:5`) | O5 |
| P15 | Diferença só de maiúsculas, acentos ou espaços no nome do ente não é divergência (é registrada como correção). | `hub.csv:2` (`MUNICIPIO DE SAO PAULO`) x `tribunal.csv:2` (`Município de São Paulo`) | — |
| P16 | Prazo = 31/12 do ano seguinte se apresentado **até 2 de abril, inclusive**; senão, 31/12 do ano subsequente ao seguinte. | `ENUNCIADO.md`, seção "Contexto" | O3 |
| P17 | Cópia idêntica de um evento é descartada. | ev-002 em `pagamentos.json:10` e `:26` | T10 |
| P18 | Entre versões diferentes do mesmo `evento_id`, vale a de `atualizado_em` mais recente; as outras são descartadas como substituídas. Se a versão mais recente for inválida, o evento fica fora, sem voltar a uma versão antiga. Versões diferentes com o mesmo `atualizado_em` ficam em dúvida. | ev-001 em `pagamentos.json:2` (15.000,00) e `:66` (15.500,00) | T10 |
| P19 | Evento sem valor ou sem processo é **descartado** (fora dos totais, listado no relatório com o motivo). Evento de precatório que só consta no tribunal é aceito com alerta. | ev-004 (`pagamentos.json:34`), ev-010 (`:90`), ev-011 (`:98`) | T11, O4 |

## 3. Prevenção

### No processo

| Mudança | Evita |
|---|---|
| Guardar cada arquivo recebido **sem abrir**, com o hash SHA-256, antes de qualquer processamento. Ninguém abre nem salva os arquivos no Excel. | D7 |
| Trocar a conferência manual pelo relatório gerado (`python -m limpeza`), que compara pela chave normalizada e só aponta divergências reais. | D5, D6 |
| Toda ocorrência "em dúvida" vira pendência com responsável e prazo; um alerta (e-mail ou chat) é enviado quando um lote tem ocorrências. | D2 |
| Pedir ao tribunal uma versão do leiaute que documente estorno, formatos, fuso, campos obrigatórios, o arquivo de apresentações e o significado de `evento_id` repetido; validar cada arquivo contra esse leiaute na chegada. | D3, D8, D9 |
| Se possível, receber os arquivos por um canal automatizado (API ou SFTP) em vez de e-mail. | D7 |

### No script de importação

| Mudança | Evita |
|---|---|
| **Upsert por `evento_id`**: inserir o evento ou, se já existir, substituir só quando o `atualizado_em` recebido for mais recente. Nunca somar a um total guardado. | D1 |
| Importar cada arquivo **numa transação**: falhou no meio, nada fica gravado, e rodar de novo o mesmo arquivo é seguro. | D1 |
| Usar as mesmas regras de normalização da limpeza (valor, CNJ, datas com fuso), cobertas por testes. | D4, D6, D9 |
| Gravar todo registro recusado em `ocorrencia_importacao`, com origem, motivo e conteúdo bruto, e conferir "lidos = aceitos + descartados + em dúvida" a cada lote. | D2 |
| Terminar com código de erro e alerta quando o arquivo for inválido ou a conservação não fechar. | D2 |
| Tratar `estorno` como subtração. | D3 |

### No banco

O script completo está em [sql/prevencao.sql](sql/prevencao.sql) (PostgreSQL,
aplicado sobre o `schema.sql`). **Ele foi revisado, mas não foi executado**
num banco real: não havia PostgreSQL disponível no ambiente. Antes de usar,
rodar num banco de teste.

| Mudança | Evita |
|---|---|
| `numero_processo` passa a `VARCHAR(20)` com `CHECK` de 20 dígitos | D6, D10 |
| `apresentado_em DATE` e `prazo_pagamento` como **coluna gerada** pela regra constitucional | D4 |
| `pagamento.atualizado_em` e `UNIQUE (evento_id)` | D1 |
| `precatorio_total_pago`: total calculado dos eventos (estorno subtrai), nunca acumulado | D1, D3 |
| `lote_importacao` (hash único por arquivo; `CHECK` de conservação) e `ocorrencia_importacao` | D1, D2 |
| Índice em `pagamento.precatorio_id` | desempenho do total |

## 4. Dúvidas

### Ao tribunal

- **T1.** Qual o formato oficial do campo `valor`? A documentação diz "número
  com ponto decimal", mas ev-002 chega como texto no padrão brasileiro
  (`"2.500,50"`, `pagamentos.json:13`). Outros formatos podem aparecer?
- **T2.** Um valor pode ter mais de 2 casas decimais? Se sim, qual critério
  de arredondamento o tribunal usa (meio para cima ou meio para o par)?
- **T3.** O que significa valor negativo com `tipo: "pagamento"` (ev-009,
  `pagamentos.json:85`)? É estorno, ajuste ou erro?
- **T4.** Estorno é um tipo oficial? A documentação diz que o tipo é "sempre
  pagamento", mas ev-007 chega como `"estorno"`. O estorno referencia o
  evento original?
- **T5.** O número do processo pode vir sem máscara? A documentação define o
  formato com máscara, mas ev-005 (`pagamentos.json:44`) chega sem.
- **T6.** Os números de processo passam pela validação do dígito verificador
  antes de serem enviados? Em produção, DV inválido deve bloquear o registro?
- **T7.** O número sequencial do processo pode chegar sem os zeros à esquerda
  (ex.: `23456-21.2020.8.26.0053`)? Completar com zeros é seguro, ou isso
  indica erro de digitação que deve bloquear o registro?
- **T8.** Qual o formato oficial de `data_pagamento`? A documentação diz
  AAAA-MM-DD, mas ev-002 chega como `10/04/2025` (`pagamentos.json:14`).
  Datas com barra são sempre dia/mês?
- **T9.** Para o prazo constitucional, a data de apresentação é a do horário
  de Brasília ou a do horário local do tribunal? E por que `apresentado_em`
  chega em três formatos (só data, data e hora em −03:00 e em UTC,
  `apresentacoes.json:4, 16, 20`)? Data e hora sem fuso pode aparecer?
- **T10.** `atualizado_em` sempre traz o fuso? Um evento com o mesmo
  `evento_id` e `atualizado_em` mais recente substitui o anterior (ev-001)?

- **T11.** O `tribunal.csv` é a lista completa de precatórios ou só os que
  mudaram? O 0056789 (`hub.csv:6`) não aparece nele: foi quitado, cancelado
  ou ficou de fora por erro?

### À operação

- **O1.** O `tribunal.csv` que recebemos é o arquivo original do e-mail ou a
  versão salva no Excel? (Explicaria Windows-1252, `;` e o formato
  brasileiro, D7.)
- **O2.** Onde fica gravado o "total pago" que o script soma? O `schema.sql`
  não tem essa coluna.
- **O3.** Como o hub calcula o prazo hoje, e ele pode ser editado à mão? O
  0012345 e o 0045678 foram apresentados no mesmo dia local e têm prazos
  diferentes (`hub.csv:2` e `:5`).
- **O4.** Por que o precatório 0067890 (`tribunal.csv:6`) não está no hub?
- **O5.** Qual é o valor de face correto do 0023456 (30.000 ou 31.000) e o
  devedor do 0045678 (União ou Município de Santos)? O hub pode ter um valor
  atualizado que o tribunal ainda não tem?
- **O6.** Com que frequência o script falhou e foi reexecutado? Existe log?
  Isso permite estimar quanto o total pago está inflado hoje.
- **O7.** Pagamento antes da data de apresentação (ev-001) é possível, ou é
  erro de cadastro?
