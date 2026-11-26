"""Ponto de entrada: python -m limpeza [--dados PASTA] [--saida PASTA]

Lê os quatro arquivos como vieram (sem alterá-los), aplica as regras e
grava a base limpa e o relatório na pasta de saída.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from limpeza.leitura import ArquivoInvalido, ler_csv, ler_json
from limpeza.pagamentos import ResultadoPagamentos, processar_pagamentos
from limpeza.precatorios import ResultadoPrecatorios, montar_precatorios
from limpeza.relatorio import escrever_saidas

RAIZ = Path(__file__).resolve().parent.parent
DADOS_PADRAO = RAIZ / "case-candidato" / "dados"
SAIDA_PADRAO = RAIZ / "saida"


def executar(dados: Path, saida: Path) -> tuple[ResultadoPrecatorios, ResultadoPagamentos]:
    # Ordem necessária: os pagamentos dependem dos precatórios já cruzados.
    tribunal = ler_csv(dados / "tribunal.csv", ["numero_processo", "ente_devedor", "valor_face"])
    hub = ler_csv(
        dados / "hub.csv",
        ["processo", "ente", "valor_face", "apresentado_em", "prazo_pagamento"],
        codificacao_esperada="UTF-8 (exportação do hub)",
    )
    apresentacoes = ler_json(dados / "apresentacoes.json")
    pagamentos = ler_json(dados / "pagamentos.json")

    precatorios = montar_precatorios(tribunal.registros, hub.registros, apresentacoes.registros)
    resultado = processar_pagamentos(pagamentos.registros, precatorios.precatorios)
    escrever_saidas(saida, [pagamentos, tribunal, hub, apresentacoes], precatorios, resultado)
    return precatorios, resultado


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m limpeza", description=__doc__)
    parser.add_argument("--dados", type=Path, default=DADOS_PADRAO)
    parser.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    args = parser.parse_args(argv)

    try:
        precatorios, pagamentos = executar(args.dados, args.saida)
    except (ArquivoInvalido, FileNotFoundError) as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 1

    print(
        f"{len(precatorios.precatorios)} precatórios, {pagamentos.entrada} eventos: "
        f"{len(pagamentos.aceitos)} aceitos, {len(pagamentos.rejeitados)} descartados ou em dúvida."
    )
    print(f"Saída em {args.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
