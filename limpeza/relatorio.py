"""Gera a base limpa (CSV) e o relatório (Markdown).

As saídas são determinísticas: rodar duas vezes com os mesmos arquivos
produz os mesmos bytes (sem data de execução, ordem fixa).
"""
from __future__ import annotations

import csv
import json
from decimal import Decimal
from pathlib import Path

from limpeza.leitura import Leitura
from limpeza.normalizacao import Processo
from limpeza.pagamentos import ResultadoPagamentos
from limpeza.precatorios import ResultadoPrecatorios
from limpeza.resultado import Destino


def escrever_saidas(
    saida: Path,
    leituras: list[Leitura],
    precatorios: ResultadoPrecatorios,
    pagamentos: ResultadoPagamentos,
) -> None:
    saida.mkdir(parents=True, exist_ok=True)
    _precatorios_csv(saida / "precatorios.csv", precatorios, pagamentos)
    _pagamentos_csv(saida / "pagamentos.csv", pagamentos)
    _rejeitados_csv(saida / "rejeitados.csv", precatorios, pagamentos)
    (saida / "relatorio.md").write_text(
        _relatorio_md(leituras, precatorios, pagamentos), encoding="utf-8", newline="\n"
    )


def _escrever_csv(caminho: Path, cabecalho: list[str], linhas: list[list]) -> None:
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.writer(arquivo, lineterminator="\n")
        escritor.writerow(cabecalho)
        escritor.writerows(linhas)


def _juntar(itens: list[str]) -> str:
    return " | ".join(itens)


def _formatar(valor) -> str:
    return "" if valor is None else str(valor)


def _precatorios_csv(caminho, precatorios, pagamentos) -> None:
    _escrever_csv(
        caminho,
        ["processo", "ente_devedor", "valor_face", "apresentado_em", "prazo_pagamento",
         "total_pago", "situacao", "divergencias", "alertas", "correcoes"],
        [
            [p.processo, _formatar(p.ente_devedor), _formatar(p.valor_face),
             _formatar(p.apresentado_em), _formatar(p.prazo_pagamento),
             pagamentos.total_pago(p.chave), p.situacao,
             _juntar(p.divergencias), _juntar(p.alertas), _juntar(p.correcoes)]
            for p in precatorios.precatorios.values()
        ],
    )


def _pagamentos_csv(caminho, pagamentos) -> None:
    _escrever_csv(
        caminho,
        ["evento_id", "processo", "tipo", "valor", "valor_com_sinal", "pago_em",
         "atualizado_em", "origem", "correcoes", "alertas"],
        [
            [p.evento_id, Processo(p.chave).formatado, p.tipo, p.valor, p.valor_com_sinal,
             p.pago_em, p.atualizado_em.isoformat(), p.registro.origem,
             _juntar(p.correcoes), _juntar(p.alertas)]
            for p in pagamentos.aceitos
        ],
    )


def _todos_rejeitados(precatorios, pagamentos):
    return precatorios.rejeitados + pagamentos.rejeitados


def _rejeitados_csv(caminho, precatorios, pagamentos) -> None:
    _escrever_csv(
        caminho,
        ["origem", "destino", "motivo", "conteudo"],
        [
            [r.registro.origem, r.destino.value, r.motivo,
             json.dumps(r.registro.campos, ensure_ascii=False, default=str)]
            for r in _todos_rejeitados(precatorios, pagamentos)
        ],
    )


def _relatorio_md(leituras, precatorios, pagamentos) -> str:
    linhas: list[str] = ["# Relatório da limpeza", ""]
    linhas += [
        "Gerado por `python -m limpeza`. Premissas e dúvidas em `DIAGNOSTICO.md`.",
        "",
        "## 1. Arquivos lidos",
        "",
        "| Arquivo | Codificação | Registros | Observações |",
        "|---|---|---|---|",
    ]
    for leitura in leituras:
        observacoes = "<br>".join(leitura.observacoes) or "—"
        linhas.append(
            f"| {leitura.arquivo} | {leitura.codificacao} | {len(leitura.registros)} | {observacoes} |"
        )

    destinos = [r.destino for r in pagamentos.rejeitados]
    descartados = destinos.count(Destino.DESCARTADO)
    em_duvida = destinos.count(Destino.EM_DUVIDA)
    linhas += [
        "",
        "## 2. Conservação dos eventos de pagamento",
        "",
        "Todo evento de entrada tem exatamente um destino; nada some em silêncio.",
        "",
        "| Entrada | Aceitos | Descartados | Em dúvida |",
        "|---|---|---|---|",
        f"| {pagamentos.entrada} | {len(pagamentos.aceitos)} | {descartados} | {em_duvida} |",
        "",
        "## 3. Precatórios",
        "",
        "| Processo | Situação | Ente devedor | Valor de face | Apresentado em | Prazo | Total pago |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in precatorios.precatorios.values():
        linhas.append(
            f"| {p.processo} | **{p.situacao}** | {_formatar(p.ente_devedor)} | "
            f"{_formatar(p.valor_face)} | {_formatar(p.apresentado_em)} | "
            f"{_formatar(p.prazo_pagamento)} | {pagamentos.total_pago(p.chave)} |"
        )
    for titulo, atributo in (("Divergências", "divergencias"), ("Alertas", "alertas"),
                             ("Correções de formato", "correcoes")):
        linhas += ["", f"### {titulo}", ""]
        itens = [
            f"- **{p.processo}**: {item}"
            for p in precatorios.precatorios.values()
            for item in getattr(p, atributo)
        ]
        linhas += itens or ["Nenhuma."]

    linhas += [
        "",
        "## 4. Pagamentos aceitos",
        "",
        "| Evento | Origem | Processo | Tipo | Valor | Pago em | Correções | Alertas |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for p in pagamentos.aceitos:
        linhas.append(
            f"| {p.evento_id} | {p.registro.origem} | {Processo(p.chave).formatado} | {p.tipo} | "
            f"{p.valor_com_sinal} | {p.pago_em} | {'<br>'.join(p.correcoes) or '—'} | "
            f"{'<br>'.join(p.alertas) or '—'} |"
        )
    total = sum((p.valor_com_sinal for p in pagamentos.aceitos), Decimal("0.00"))
    linhas += ["", f"Total líquido aceito: **{total}**."]

    linhas += [
        "",
        "## 5. Registros descartados ou em dúvida",
        "",
        "| Origem | Destino | Motivo |",
        "|---|---|---|",
    ]
    for r in _todos_rejeitados(precatorios, pagamentos):
        linhas.append(f"| {r.registro.origem} | **{r.destino.value}** | {r.motivo} |")
    linhas.append("")
    return "\n".join(linhas)
