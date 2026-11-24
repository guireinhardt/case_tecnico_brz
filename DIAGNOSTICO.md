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
| P8 | Só são aceitas as duas formas vistas nos dados: máscara completa `NNNNNNN-DD.AAAA.J.TR.OOOO` ou exatamente 20 dígitos. Número sem máscara é aceito, mas registrado como correção (descumpre o leiaute). Números com dígitos faltando não são completados com zeros. | `DOCUMENTACAO_TRIBUNAL.md:12` define a máscara; completar zeros exigiria adivinhar onde faltam | T5 |
| P9 | Dígito verificador inválido gera **alerta**, não rejeição. Os 6 números do caso têm DV inválido (cálculo módulo 97, Res. CNJ 65/2008); rejeitar esvaziaria a base inteira. | todos os processos de `tribunal.csv`, `hub.csv`, `pagamentos.json` e `apresentacoes.json`; ENUNCIADO.md:3 ("processos e valores são fictícios") | T6 |

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

### À operação

_A preencher._
