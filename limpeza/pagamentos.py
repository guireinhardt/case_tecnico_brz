"""Regras dos eventos de pagamento.

Ordem de processamento (a ordem importa):
1. Sem evento_id ou sem atualizado_em válido: descartado (não dá para
   saber a que evento pertence nem qual versão é a mais nova).
2. Agrupa por evento_id. Cópia idêntica: descartada (P17). Entre versões
   diferentes, vale a de atualizado_em mais recente; as outras são
   descartadas como substituídas (P18). Empate com conteúdo diferente: em
   dúvida, porque não há como escolher.
3. Só a versão vencedora é validada. Se ela for inválida, o evento inteiro
   fica fora: não se volta para uma versão antiga.
4. Total pago = soma dos pagamentos menos os estornos (P5), sempre
   calculado a partir dos eventos, nunca acumulado.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from limpeza.leitura import Registro
from limpeza.normalizacao import (
    DataInvalida,
    Motivo,
    ProcessoInvalido,
    ValorInvalido,
    normalizar_data,
    normalizar_data_hora,
    normalizar_processo,
    normalizar_valor,
)
from limpeza.precatorios import Precatorio
from limpeza.resultado import Destino, Rejeitado

TIPOS = ("pagamento", "estorno")


@dataclass
class Pagamento:
    """Evento aceito na base limpa."""

    evento_id: str
    chave: str
    tipo: str
    valor: Decimal
    pago_em: date
    atualizado_em: datetime
    registro: Registro
    correcoes: list[str] = field(default_factory=list)
    alertas: list[str] = field(default_factory=list)

    @property
    def valor_com_sinal(self) -> Decimal:
        return -self.valor if self.tipo == "estorno" else self.valor


@dataclass
class ResultadoPagamentos:
    entrada: int
    aceitos: list[Pagamento]
    rejeitados: list[Rejeitado]

    def total_pago(self, chave: str) -> Decimal:
        return sum(
            (p.valor_com_sinal for p in self.aceitos if p.chave == chave), Decimal("0.00")
        )


class _Recusa(Exception):
    def __init__(self, destino: Destino, motivo: str) -> None:
        self.destino = destino
        self.motivo = motivo


def processar_pagamentos(
    registros: list[Registro], precatorios: dict[str, Precatorio]
) -> ResultadoPagamentos:
    aceitos: list[Pagamento] = []
    rejeitados: list[Rejeitado] = []

    # Passo 1: identificar o evento e a versão.
    grupos: dict[str, list[tuple[datetime, Registro]]] = {}
    for registro in registros:
        evento_id = registro.campos.get("evento_id")
        if not isinstance(evento_id, str) or not evento_id.strip():
            rejeitados.append(Rejeitado(registro, Destino.DESCARTADO, "evento_id: campo ausente"))
            continue
        try:
            atualizado = normalizar_data_hora(registro.campos.get("atualizado_em")).valor
        except DataInvalida as erro:
            rejeitados.append(Rejeitado(
                registro, Destino.DESCARTADO, f"atualizado_em: {erro.motivo.value}"
            ))
            continue
        grupos.setdefault(evento_id.strip(), []).append((atualizado, registro))

    # Passos 2 e 3: escolher a versão e validar.
    for evento_id, versoes in grupos.items():
        vencedora = _escolher_versao(versoes, rejeitados)
        if vencedora is None:
            continue
        atualizado, registro = vencedora
        try:
            aceitos.append(_validar(evento_id, atualizado, registro, precatorios))
        except _Recusa as recusa:
            rejeitados.append(Rejeitado(registro, recusa.destino, recusa.motivo))

    aceitos.sort(key=lambda p: p.registro.linha)
    rejeitados.sort(key=lambda r: r.registro.linha)

    # Invariante: todo registro de entrada tem exatamente um destino.
    if len(aceitos) + len(rejeitados) != len(registros):
        raise AssertionError(
            f"conservação violada: {len(registros)} de entrada, "
            f"{len(aceitos)} aceitos + {len(rejeitados)} rejeitados"
        )
    return ResultadoPagamentos(len(registros), aceitos, rejeitados)


def _escolher_versao(versoes, rejeitados):
    unicas: list[tuple[datetime, Registro]] = []
    for atualizado, registro in versoes:
        copia_de = next((r for _, r in unicas if r.campos == registro.campos), None)
        if copia_de is not None:
            rejeitados.append(Rejeitado(
                registro, Destino.DESCARTADO, f"duplicata idêntica de {copia_de.origem} (P17)"
            ))
        else:
            unicas.append((atualizado, registro))

    mais_recente = max(a for a, _ in unicas)
    empatadas = [(a, r) for a, r in unicas if a == mais_recente]
    antigas = [(a, r) for a, r in unicas if a != mais_recente]

    if len(empatadas) > 1:
        origens = ", ".join(r.origem for _, r in empatadas)
        for _, registro in empatadas:
            rejeitados.append(Rejeitado(
                registro, Destino.EM_DUVIDA,
                f"versões diferentes com o mesmo atualizado_em ({origens})",
            ))
        vencedora = None
        referencia = origens
    else:
        vencedora = empatadas[0]
        referencia = vencedora[1].origem

    for _, registro in antigas:
        rejeitados.append(Rejeitado(
            registro, Destino.DESCARTADO,
            f"versão substituída por {referencia}, de atualizado_em mais recente (P18)",
        ))
    return vencedora


def _validar(evento_id, atualizado, registro, precatorios) -> Pagamento:
    campos = registro.campos
    correcoes: list[str] = []
    alertas: list[str] = []

    try:
        processo = normalizar_processo(campos.get("processo"))
    except ProcessoInvalido as erro:
        raise _Recusa(Destino.DESCARTADO, f"processo: {erro.motivo.value}") from None
    correcoes += [f"processo {c}" for c in processo.correcoes]

    try:
        valor = normalizar_valor(campos.get("valor"))
    except ValorInvalido as erro:
        if erro.motivo == Motivo.NEGATIVO:
            raise _Recusa(
                Destino.EM_DUVIDA,
                f"valor negativo ({erro.bruto}) com tipo '{campos.get('tipo')}': "
                "não há pagamento anterior a estornar (P6)",
            ) from None
        raise _Recusa(Destino.DESCARTADO, f"valor: {erro.motivo.value}") from None
    if valor.correcao:
        correcoes.append(f"valor {valor.correcao}")

    try:
        pago_em = normalizar_data(campos.get("data_pagamento"))
    except DataInvalida as erro:
        raise _Recusa(Destino.DESCARTADO, f"data_pagamento: {erro.motivo.value}") from None
    correcoes += [f"data_pagamento {c}" for c in pago_em.correcoes]

    tipo = campos.get("tipo")
    if tipo not in TIPOS:
        raise _Recusa(Destino.EM_DUVIDA, f"tipo desconhecido: {tipo!r}")
    if tipo == "estorno":
        alertas.append("tipo 'estorno' não previsto na documentação; subtraído do total (P5)")

    precatorio = precatorios.get(processo.chave)
    if precatorio is None:
        raise _Recusa(
            Destino.EM_DUVIDA,
            f"precatório {processo.formatado} não consta no tribunal nem no hub",
        )
    if not precatorio.no_hub:
        alertas.append("precatório não consta no nosso sistema (hub.csv)")
    if precatorio.apresentado_em and pago_em.valor < precatorio.apresentado_em:
        alertas.append(
            f"pago em {pago_em.valor}, antes da apresentação do precatório "
            f"({precatorio.apresentado_em})"
        )

    return Pagamento(
        evento_id, processo.chave, tipo, valor.valor, pago_em.valor, atualizado,
        registro, correcoes, alertas,
    )
