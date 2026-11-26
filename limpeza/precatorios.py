"""Cruzamento tribunal x hub x apresentações e cálculo do prazo.

Regras (ver DIAGNOSTICO.md):
* P7: os arquivos são cruzados pela chave de 20 dígitos do CNJ.
* P14: quando tribunal e hub divergem, o tribunal prevalece e o valor do
  hub fica registrado como divergência.
* P15: diferença só de maiúsculas, acentos ou espaços no nome do ente não
  é divergência.
* P16: prazo pela regra do ENUNCIADO.md: apresentado até 2 de abril do ano
  Y -> 31/12/(Y+1); depois -> 31/12/(Y+2).
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from limpeza.leitura import Registro
from limpeza.normalizacao import (
    DataInvalida,
    Processo,
    ProcessoInvalido,
    ValorInvalido,
    normalizar_data,
    normalizar_processo,
    normalizar_valor,
)
from limpeza.resultado import Destino, Rejeitado


def calcular_prazo(apresentado_em: date) -> date:
    """Prazo constitucional de pagamento (P16).

    "Até 2 de abril" inclui o próprio dia 2.
    """
    if (apresentado_em.month, apresentado_em.day) <= (4, 2):
        return date(apresentado_em.year + 1, 12, 31)
    return date(apresentado_em.year + 2, 12, 31)


@dataclass
class Precatorio:
    """Precatório consolidado a partir das três fontes."""

    chave: str
    ente_devedor: str | None
    valor_face: Decimal | None
    apresentado_em: date | None
    prazo_pagamento: date | None
    no_tribunal: bool
    no_hub: bool
    divergencias: list[str] = field(default_factory=list)
    alertas: list[str] = field(default_factory=list)
    correcoes: list[str] = field(default_factory=list)

    @property
    def processo(self) -> str:
        return Processo(self.chave).formatado

    @property
    def situacao(self) -> str:
        if not self.no_hub:
            return "ausente no hub"
        if not self.no_tribunal:
            return "ausente no tribunal"
        if self.divergencias:
            return "divergente"
        return "conferido"


@dataclass
class ResultadoPrecatorios:
    precatorios: dict[str, Precatorio]
    rejeitados: list[Rejeitado]


def montar_precatorios(
    tribunal: list[Registro],
    hub: list[Registro],
    apresentacoes: list[Registro],
) -> ResultadoPrecatorios:
    rejeitados: list[Rejeitado] = []
    idx_tribunal = _indexar(tribunal, "numero_processo", rejeitados)
    idx_hub = _indexar(hub, "processo", rejeitados)
    idx_apresentacao = _indexar(apresentacoes, "processo", rejeitados)

    # Ordem: primeiro os do tribunal (lista oficial), depois os só do hub.
    chaves = list(idx_tribunal) + [c for c in idx_hub if c not in idx_tribunal]
    precatorios = {
        chave: _consolidar(
            chave, idx_tribunal.get(chave), idx_hub.get(chave), idx_apresentacao.get(chave)
        )
        for chave in chaves
    }

    for chave, (registro, _) in idx_apresentacao.items():
        if chave not in precatorios:
            rejeitados.append(Rejeitado(
                registro, Destino.EM_DUVIDA,
                "apresentação de processo que não está no tribunal nem no hub",
            ))
    return ResultadoPrecatorios(precatorios, rejeitados)


def _indexar(
    registros: list[Registro], campo: str, rejeitados: list[Rejeitado]
) -> dict[str, tuple[Registro, Processo]]:
    indice: dict[str, tuple[Registro, Processo]] = {}
    for registro in registros:
        try:
            processo = normalizar_processo(registro.campos.get(campo))
        except ProcessoInvalido as erro:
            rejeitados.append(Rejeitado(registro, Destino.DESCARTADO, f"{campo}: {erro.motivo.value}"))
            continue
        if processo.chave in indice:
            primeiro = indice[processo.chave][0]
            rejeitados.append(Rejeitado(
                registro, Destino.EM_DUVIDA,
                f"processo repetido no arquivo (primeira ocorrência em {primeiro.origem})",
            ))
            continue
        indice[processo.chave] = (registro, processo)
    return indice


def _consolidar(chave, tribunal, hub, apresentacao) -> Precatorio:
    p = Precatorio(chave, None, None, None, None, tribunal is not None, hub is not None)

    for fonte in (tribunal, hub, apresentacao):
        if fonte is None:
            continue
        registro, processo = fonte
        for correcao in processo.correcoes:
            p.correcoes.append(f"{registro.origem}: processo {correcao}")
    if not next(f for f in (tribunal, hub, apresentacao) if f)[1].dv_valido:
        p.alertas.append("dígito verificador do CNJ inválido (P9)")

    _consolidar_ente(p, tribunal, hub)
    _consolidar_valor_face(p, tribunal, hub)
    _consolidar_apresentacao(p, hub, apresentacao)

    if tribunal is None:
        p.alertas.append("não consta na lista do tribunal (tribunal.csv)")
    if hub is None:
        p.alertas.append("não consta no nosso sistema (hub.csv)")
    if apresentacao is None and p.apresentado_em is None:
        p.alertas.append("sem data de apresentação: prazo não calculado")
    return p


def _consolidar_ente(p: Precatorio, tribunal, hub) -> None:
    ente_t = tribunal[0].campos.get("ente_devedor", "").strip() if tribunal else ""
    ente_h = hub[0].campos.get("ente", "").strip() if hub else ""
    p.ente_devedor = ente_t or ente_h or None
    if ente_t and ente_h:
        if _comparavel(ente_t) != _comparavel(ente_h):
            p.divergencias.append(
                f"ente devedor: tribunal '{ente_t}' ({tribunal[0].origem}), "
                f"hub '{ente_h}' ({hub[0].origem})"
            )
        elif ente_t != ente_h:
            p.correcoes.append(
                f"{hub[0].origem}: ente '{ente_h}' é o mesmo que '{ente_t}' "
                "(diferença só de maiúsculas/acentos)"
            )


def _consolidar_valor_face(p: Precatorio, tribunal, hub) -> None:
    valores = {}
    for nome, fonte in (("tribunal", tribunal), ("hub", hub)):
        if fonte is None:
            continue
        registro = fonte[0]
        try:
            valor = normalizar_valor(registro.campos.get("valor_face"))
        except ValorInvalido as erro:
            p.alertas.append(f"{registro.origem}: valor de face inválido ({erro.motivo.value})")
            continue
        if valor.correcao and nome == "tribunal":
            p.correcoes.append(f"{registro.origem}: valor de face {valor.correcao}")
        valores[nome] = (valor.valor, registro.origem)

    if "tribunal" in valores:
        p.valor_face = valores["tribunal"][0]
    elif "hub" in valores:
        p.valor_face = valores["hub"][0]
    if len(valores) == 2 and valores["tribunal"][0] != valores["hub"][0]:
        (vt, ot), (vh, oh) = valores["tribunal"], valores["hub"]
        p.divergencias.append(
            f"valor de face: tribunal {vt} ({ot}), hub {vh} ({oh}); diferença {vh - vt}"
        )


def _consolidar_apresentacao(p: Precatorio, hub, apresentacao) -> None:
    datas = {}
    for nome, fonte, campo in (
        ("apresentacoes", apresentacao, "apresentado_em"),
        ("hub", hub, "apresentado_em"),
    ):
        if fonte is None:
            continue
        registro = fonte[0]
        try:
            data = normalizar_data(registro.campos.get(campo))
        except DataInvalida as erro:
            p.alertas.append(f"{registro.origem}: apresentado_em inválido ({erro.motivo.value})")
            continue
        if nome == "apresentacoes":
            for correcao in data.correcoes:
                p.correcoes.append(f"{registro.origem}: apresentado_em {correcao}")
        datas[nome] = (data.valor, registro.origem)

    if not datas:
        return
    p.apresentado_em = (datas.get("apresentacoes") or datas["hub"])[0]
    if len(datas) == 2 and datas["apresentacoes"][0] != datas["hub"][0]:
        p.divergencias.append(
            f"data de apresentação: {datas['apresentacoes'][0]} ({datas['apresentacoes'][1]}), "
            f"hub {datas['hub'][0]} ({datas['hub'][1]})"
        )

    p.prazo_pagamento = calcular_prazo(p.apresentado_em)
    if hub is None:
        return
    try:
        prazo_hub = normalizar_data(hub[0].campos.get("prazo_pagamento")).valor
    except DataInvalida as erro:
        p.alertas.append(f"{hub[0].origem}: prazo_pagamento inválido ({erro.motivo.value})")
        return
    if prazo_hub != p.prazo_pagamento:
        p.divergencias.append(
            f"prazo de pagamento: hub {prazo_hub} ({hub[0].origem}), "
            f"calculado {p.prazo_pagamento} (apresentado em {p.apresentado_em})"
        )


def _comparavel(texto: str) -> str:
    """'MUNICIPIO DE SAO PAULO' e 'Município de São Paulo' ficam iguais."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    return " ".join(sem_acento.casefold().split())
