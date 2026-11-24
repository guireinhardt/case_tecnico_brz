# Diagnóstico, prevenção e dúvidas

> Documento em construção: é atualizado a cada etapa do projeto.

## 1. Diagnóstico

_A preencher (problemas ordenados por gravidade, com evidência, impacto e
relação causa/consequência)._

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

## 3. Prevenção

_A preencher (processo, script de importação e banco, com SQL)._

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

### À operação

_A preencher._
