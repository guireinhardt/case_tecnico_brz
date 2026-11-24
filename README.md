# case_tecnico_brz

Diagnóstico e limpeza dos arquivos de precatórios: eventos de pagamento do
tribunal, lista de precatórios do tribunal e exportação do nosso sistema (hub).

O diagnóstico, as premissas adotadas e as dúvidas estão em
[DIAGNOSTICO.md](DIAGNOSTICO.md).

## Estrutura

```
case-candidato/          material original do desafio (nunca é alterado)
limpeza/
  normalizacao.py        converte valor, número CNJ e datas em tipos confiáveis
  leitura.py             lê CSV e JSON como vieram, guardando arquivo:linha
tests/                   testes (pytest)
DIAGNOSTICO.md           diagnóstico, premissas, prevenção e dúvidas
```

## Como rodar

Requer Python 3.10 ou mais recente.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # Linux/Mac
pip install -r requirements.txt
pytest -v
```

Dependências: `pytest` e `tzdata` (base de fusos horários; no Windows o
Python não traz a própria, e as datas precisam do fuso `America/Sao_Paulo`).

## Garantias sobre os arquivos originais

- `tests/test_integridade_originais.py` confere o SHA-256 de cada arquivo de
  `case-candidato/dados/` contra o zip recebido. Se algum byte mudar, o teste
  falha.
- `.gitattributes` marca esses arquivos como binários, para o Git não
  converter as quebras de linha (CRLF) ao versionar.

## Uso de IA

_A preencher._
