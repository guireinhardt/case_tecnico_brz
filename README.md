# case_tecnico_brz

Diagnóstico e limpeza dos arquivos de precatórios: eventos de pagamento do
tribunal, lista de precatórios do tribunal e exportação do nosso sistema (hub).

- **Diagnóstico, prevenção e dúvidas:** [DIAGNOSTICO.md](DIAGNOSTICO.md)
- **Relatório gerado pela limpeza:** [saida/relatorio.md](saida/relatorio.md)
- **SQL de prevenção:** [sql/prevencao.sql](sql/prevencao.sql)

## Como rodar

Requer Python 3.10 ou mais recente.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # Linux/Mac
pip install -r requirements.txt

python -m limpeza                 # lê case-candidato/dados/ e grava em saida/
pytest -v                         # roda os testes
```

Opções: `python -m limpeza --dados PASTA --saida PASTA`.

Dependências: `pytest` e `tzdata` (base de fusos horários; no Windows o
Python não traz a própria, e as datas precisam do fuso `America/Sao_Paulo`).

## O que a limpeza gera (`saida/`)

| Arquivo | Conteúdo |
|---|---|
| `precatorios.csv` | precatórios consolidados (tribunal + hub + apresentações), com situação, prazo calculado, total pago, divergências e alertas |
| `pagamentos.csv` | eventos aceitos, com a origem (`arquivo:linha`) e as correções de formato |
| `rejeitados.csv` | registros descartados ou em dúvida, com motivo e conteúdo original |
| `relatorio.md` | o que foi corrigido, descartado ou ficou em dúvida, e por quê |

A saída é determinística: rodar de novo com os mesmos arquivos produz os
mesmos bytes. A pasta fica versionada para leitura sem precisar executar.

## Estrutura

```
case-candidato/          material original do desafio (nunca é alterado)
limpeza/
  leitura.py             lê CSV e JSON como vieram, guardando arquivo:linha
  normalizacao.py        converte valor, número CNJ e datas
  precatorios.py         cruza tribunal x hub x apresentações; calcula o prazo
  pagamentos.py          duplicatas, versões, estornos e destino de cada evento
  relatorio.py           grava a base limpa e o relatório
  __main__.py            python -m limpeza
tests/                   testes (pytest), incluindo o gabarito feito à mão
sql/prevencao.sql        mudanças no banco propostas no diagnóstico
saida/                   resultado da última execução
```

## Como os resultados foram conferidos

- **Gabarito feito à mão** (`tests/test_gabarito.py`): o destino de cada um
  dos 13 eventos e o total pago por processo foram calculados lendo os
  arquivos, sem o código. O programa precisa chegar nos mesmos números.
- **Conservação:** todo registro de entrada tem exatamente um destino
  (aceito, descartado ou em dúvida); o programa interrompe se a conta não
  fechar.
- **Integridade dos originais** (`tests/test_integridade_originais.py`):
  confere o SHA-256 de cada arquivo de `case-candidato/dados/` contra o zip
  recebido. O `.gitattributes` impede o Git de converter as quebras de linha.
- **Verificações independentes:** o dígito verificador do CNJ é conferido por
  uma segunda fórmula; a conversão de fuso é testada num dia de horário de
  verão, em que um offset fixo de −03:00 erraria.

## Uso de IA

Usei o Claude Code para analisar os arquivos e escrever o código.

**O que foi decisão minha.** As regras de negócio foram decididas por mim:
eu procurava entender a lógica de cada caso para tomar a decisão e instruir
a IA. Alguns exemplos:

- Completar com zeros à esquerda o número sequencial do CNJ quando ele vem
  com a máscara (a IA recomendava rejeitar).
- Quando tribunal e hub divergem, o tribunal prevalece (a IA recomendava
  mostrar os dois valores sem escolher).
- Eventos sem valor ou sem processo são descartados (a IA recomendava
  deixar em dúvida).
- Nas datas, levantei que o Brasil tem quatro fusos horários. Isso definiu
  que data e hora sem fuso deve ser rejeitada e gerou a dúvida T9, sobre
  usar o horário local do tribunal.

As decisões e o motivo de cada uma estão em [DIAGNOSTICO.md](DIAGNOSTICO.md)
(premissas P1 a P19).

**Como conferi o que a IA produziu.** Pedi que toda afirmação viesse com a
evidência (arquivo e linha) e conferi nos arquivos originais; algumas
citações estavam erradas e foram corrigidas. Rodei os testes, analisei os
arquivos escritos e refiz à mão o total de alguns processos. O gabarito
feito à mão (`tests/test_gabarito.py`) encontrou um erro de prazo na
análise inicial.

**O que eu faria diferente.** Escreveria mais partes do código eu mesmo,
para entender melhor o projeto. O SQL de prevenção também ficou sem ser
executado num banco real.

Os commits feitos com a IA estão marcados com `Co-Authored-By: Claude`.
