# Relatório da limpeza

Gerado por `python -m limpeza`. Premissas e dúvidas em `DIAGNOSTICO.md`.

## 1. Arquivos lidos

| Arquivo | Codificação | Registros | Observações |
|---|---|---|---|
| pagamentos.json | utf-8 | 13 | quebras de linha no padrão Windows (CRLF) |
| tribunal.csv | cp1252 | 5 | codificação Windows-1252, não UTF-8 como documentado (primeiro byte inválido em UTF-8 na posição 72: 0xED)<br>quebras de linha no padrão Windows (CRLF)<br>separador ';', não ',' como documentado |
| hub.csv | utf-8 | 5 | — |
| apresentacoes.json | utf-8 | 6 | quebras de linha no padrão Windows (CRLF) |

## 2. Conservação dos eventos de pagamento

Todo evento de entrada tem exatamente um destino; nada some em silêncio.

| Entrada | Aceitos | Descartados | Em dúvida |
|---|---|---|---|
| 13 | 8 | 4 | 1 |

## 3. Precatórios

| Processo | Situação | Ente devedor | Valor de face | Apresentado em | Prazo | Total pago |
|---|---|---|---|---|---|---|
| 0012345-10.2019.8.26.0053 | **divergente** | Município de São Paulo | 45000.00 | 2025-04-02 | 2026-12-31 | 18000.50 |
| 0023456-21.2020.8.26.0053 | **divergente** | Município de São Paulo | 30000.00 | 2025-04-03 | 2027-12-31 | 9200.00 |
| 0034567-32.2018.8.26.0405 | **conferido** | Estado de São Paulo | 12500.00 | 2024-02-29 | 2025-12-31 | 0.00 |
| 0045678-43.2021.5.02.0011 | **divergente** | União | 9800.00 | 2025-04-02 | 2026-12-31 | 3000.00 |
| 0067890-65.2016.8.26.0053 | **ausente no hub** | Município de São Paulo | 7000.00 | 2023-12-31 | 2025-12-31 | 4000.00 |
| 0056789-54.2017.4.03.6100 | **ausente no tribunal** | Estado de São Paulo | 22000.00 | 2025-04-02 | 2026-12-31 | 0.00 |

### Divergências

- **0012345-10.2019.8.26.0053**: prazo de pagamento: hub 2027-12-31 (hub.csv:2), calculado 2026-12-31 (apresentado em 2025-04-02)
- **0023456-21.2020.8.26.0053**: valor de face: tribunal 30000.00 (tribunal.csv:3), hub 31000.00 (hub.csv:3); diferença 1000.00
- **0045678-43.2021.5.02.0011**: ente devedor: tribunal 'União' (tribunal.csv:5), hub 'Município de Santos' (hub.csv:5)
- **0056789-54.2017.4.03.6100**: prazo de pagamento: hub 2027-12-31 (hub.csv:6), calculado 2026-12-31 (apresentado em 2025-04-02)

### Alertas

- **0012345-10.2019.8.26.0053**: dígito verificador do CNJ inválido (P9)
- **0023456-21.2020.8.26.0053**: dígito verificador do CNJ inválido (P9)
- **0034567-32.2018.8.26.0405**: dígito verificador do CNJ inválido (P9)
- **0045678-43.2021.5.02.0011**: dígito verificador do CNJ inválido (P9)
- **0067890-65.2016.8.26.0053**: dígito verificador do CNJ inválido (P9)
- **0067890-65.2016.8.26.0053**: não consta no nosso sistema (hub.csv)
- **0056789-54.2017.4.03.6100**: dígito verificador do CNJ inválido (P9)
- **0056789-54.2017.4.03.6100**: não consta na lista do tribunal (tribunal.csv)

### Correções de formato

- **0012345-10.2019.8.26.0053**: hub.csv:2: ente 'MUNICIPIO DE SAO PAULO' é o mesmo que 'Município de São Paulo' (diferença só de maiúsculas/acentos)
- **0012345-10.2019.8.26.0053**: tribunal.csv:2: valor de face formato brasileiro convertido
- **0023456-21.2020.8.26.0053**: hub.csv:3: processo recebido sem máscara
- **0023456-21.2020.8.26.0053**: tribunal.csv:3: valor de face formato brasileiro convertido
- **0034567-32.2018.8.26.0405**: tribunal.csv:4: valor de face formato brasileiro convertido
- **0045678-43.2021.5.02.0011**: tribunal.csv:5: valor de face formato brasileiro convertido
- **0045678-43.2021.5.02.0011**: apresentacoes.json:14: apresentado_em data e hora convertida para a data de Brasília
- **0067890-65.2016.8.26.0053**: tribunal.csv:6: valor de face formato brasileiro convertido
- **0056789-54.2017.4.03.6100**: apresentacoes.json:18: apresentado_em data e hora convertida para a data de Brasília

## 4. Pagamentos aceitos

| Evento | Origem | Processo | Tipo | Valor | Pago em | Correções | Alertas |
|---|---|---|---|---|---|---|---|
| ev-002 | pagamentos.json:10 | 0012345-10.2019.8.26.0053 | pagamento | 2500.50 | 2025-04-10 | valor formato brasileiro convertido<br>data_pagamento formato DD/MM/AAAA convertido | — |
| ev-003 | pagamentos.json:18 | 0023456-21.2020.8.26.0053 | pagamento | 8000.00 | 2025-05-02 | — | — |
| ev-005 | pagamentos.json:42 | 0023456-21.2020.8.26.0053 | pagamento | 1200.00 | 2025-06-01 | processo recebido sem máscara | — |
| ev-006 | pagamentos.json:50 | 0034567-32.2018.8.26.0405 | pagamento | 5000.00 | 2025-02-20 | — | — |
| ev-007 | pagamentos.json:58 | 0034567-32.2018.8.26.0405 | estorno | -5000.00 | 2025-02-21 | — | tipo 'estorno' não previsto na documentação; subtraído do total (P5) |
| ev-001 | pagamentos.json:66 | 0012345-10.2019.8.26.0053 | pagamento | 15500.00 | 2025-03-10 | — | pago em 2025-03-10, antes da apresentação do precatório (2025-04-02) |
| ev-008 | pagamentos.json:74 | 0045678-43.2021.5.02.0011 | pagamento | 3000.00 | 2025-07-15 | — | — |
| ev-011 | pagamentos.json:98 | 0067890-65.2016.8.26.0053 | pagamento | 4000.00 | 2025-08-10 | — | precatório não consta no nosso sistema (hub.csv) |

Total líquido aceito: **34200.50**.

## 5. Registros descartados ou em dúvida

| Origem | Destino | Motivo |
|---|---|---|
| pagamentos.json:2 | **descartado** | versão substituída por pagamentos.json:66, de atualizado_em mais recente (P18) |
| pagamentos.json:26 | **descartado** | duplicata idêntica de pagamentos.json:10 (P17) |
| pagamentos.json:34 | **descartado** | valor: campo ausente |
| pagamentos.json:82 | **em dúvida** | valor negativo (-200) com tipo 'pagamento': não há pagamento anterior a estornar (P6) |
| pagamentos.json:90 | **descartado** | processo: campo ausente |
