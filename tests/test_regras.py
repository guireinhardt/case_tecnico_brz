"""Testes unitários das regras de prazo e de versões de eventos."""
from datetime import date
from decimal import Decimal

import pytest

from limpeza.leitura import Registro
from limpeza.pagamentos import processar_pagamentos
from limpeza.precatorios import Precatorio, calcular_prazo
from limpeza.resultado import Destino


# --- Prazo (P16) ---

@pytest.mark.parametrize(
    "apresentado, prazo",
    [
        (date(2025, 4, 2), date(2026, 12, 31)),   # "até 2 de abril" inclui o dia 2
        (date(2025, 4, 3), date(2027, 12, 31)),
        (date(2025, 1, 1), date(2026, 12, 31)),
        (date(2025, 12, 31), date(2027, 12, 31)),
        (date(2024, 2, 29), date(2025, 12, 31)),  # bissexto
    ],
)
def test_prazo_constitucional(apresentado, prazo):
    assert calcular_prazo(apresentado) == prazo


# --- Versões de eventos (P17, P18) ---

CHAVE = "00234562120208260053"
PRECATORIOS = {CHAVE: Precatorio(CHAVE, "Ente", Decimal("1000.00"), date(2025, 1, 1),
                                 date(2026, 12, 31), True, True)}


def _evento(linha, valor, atualizado, evento_id="ev-x"):
    return Registro("p.json", linha, {
        "evento_id": evento_id,
        "processo": "0023456-21.2020.8.26.0053",
        "valor": valor,
        "data_pagamento": "2025-05-01",
        "tipo": "pagamento",
        "atualizado_em": atualizado,
    })


def test_versao_mais_recente_vence_mesmo_se_vier_antes_no_arquivo():
    registros = [
        _evento(1, 200, "2025-05-02T10:00:00-03:00"),  # mais nova, mas aparece primeiro
        _evento(2, 100, "2025-05-01T10:00:00-03:00"),
    ]
    resultado = processar_pagamentos(registros, PRECATORIOS)
    assert [p.valor for p in resultado.aceitos] == [Decimal("200.00")]
    assert "substituída" in resultado.rejeitados[0].motivo


def test_versao_mais_recente_invalida_nao_volta_para_a_antiga():
    registros = [
        _evento(1, 100, "2025-05-01T10:00:00-03:00"),
        _evento(2, None, "2025-05-02T10:00:00-03:00"),  # a mais nova perdeu o valor
    ]
    resultado = processar_pagamentos(registros, PRECATORIOS)
    assert resultado.aceitos == []
    assert {r.destino for r in resultado.rejeitados} == {Destino.DESCARTADO}


def test_versoes_diferentes_com_mesmo_atualizado_em_ficam_em_duvida():
    registros = [
        _evento(1, 100, "2025-05-01T10:00:00-03:00"),
        _evento(2, 200, "2025-05-01T10:00:00-03:00"),
    ]
    resultado = processar_pagamentos(registros, PRECATORIOS)
    assert resultado.aceitos == []
    assert [r.destino for r in resultado.rejeitados] == [Destino.EM_DUVIDA] * 2


def test_mesmo_instante_em_fusos_diferentes_e_empate():
    registros = [
        _evento(1, 100, "2025-05-01T13:00:00Z"),
        _evento(2, 200, "2025-05-01T10:00:00-03:00"),
    ]
    resultado = processar_pagamentos(registros, PRECATORIOS)
    assert [r.destino for r in resultado.rejeitados] == [Destino.EM_DUVIDA] * 2


def test_reprocessar_o_mesmo_arquivo_nao_duplica_o_total():
    # O operador roda de novo o mesmo arquivo após falha (ENUNCIADO, passo 2).
    # Como o total é calculado dos eventos e as cópias são descartadas, o
    # total não muda.
    uma_vez = [_evento(1, 100, "2025-05-01T10:00:00-03:00")]
    duas_vezes = uma_vez + [_evento(2, 100, "2025-05-01T10:00:00-03:00")]
    total_1 = processar_pagamentos(uma_vez, PRECATORIOS).total_pago(CHAVE)
    total_2 = processar_pagamentos(duas_vezes, PRECATORIOS).total_pago(CHAVE)
    assert total_1 == total_2 == Decimal("100.00")


def test_precatorio_desconhecido_fica_em_duvida():
    resultado = processar_pagamentos([_evento(1, 100, "2025-05-01T10:00:00-03:00")], {})
    assert resultado.rejeitados[0].destino == Destino.EM_DUVIDA
