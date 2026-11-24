"""Testes dos normalizadores de data (P10-P13).

normalizar_data      -> só a data (data_pagamento, apresentado_em)
normalizar_data_hora -> data e hora com fuso (atualizado_em)
"""
from datetime import date, datetime, timedelta, timezone

import pytest

from limpeza.normalizacao import (
    DataInvalida,
    Motivo,
    normalizar_data,
    normalizar_data_hora,
)

BRT = timezone(timedelta(hours=-3))


# --- normalizar_data: formato documentado ---

@pytest.mark.parametrize(
    "bruto, esperado",
    [
        ("2025-03-10", date(2025, 3, 10)),  # pagamentos.json:6 (ev-001)
        ("2024-02-29", date(2024, 2, 29)),  # apresentacoes.json:12 (ano bissexto)
        ("2023-12-31", date(2023, 12, 31)),  # apresentacoes.json:24
    ],
)
def test_data_iso_aceita_sem_correcao(bruto, esperado):
    resultado = normalizar_data(bruto)
    assert resultado.valor == esperado
    assert resultado.correcoes == ()


# --- normalizar_data: correções de formato ---

def test_data_brasileira_convertida_como_dia_mes():
    # pagamentos.json:14 (ev-002). O atualizado_em do mesmo evento
    # (2025-04-10, linha 16) confirma que é 10 de abril.
    resultado = normalizar_data("10/04/2025")
    assert resultado.valor == date(2025, 4, 10)
    assert resultado.correcoes == ("formato DD/MM/AAAA convertido",)


def test_espacos_ao_redor_sao_removidos():
    resultado = normalizar_data(" 2025-03-10 ")
    assert resultado.valor == date(2025, 3, 10)
    assert resultado.correcoes == ("espaços removidos",)


# --- normalizar_data: data e hora vira a data em Brasília (P11) ---

@pytest.mark.parametrize(
    "bruto, esperado",
    [
        # apresentacoes.json:16, hub.csv:5. Já está em -03:00.
        ("2025-04-02T23:30:00-03:00", date(2025, 4, 2)),
        # apresentacoes.json:20, hub.csv:6. Dia 3 em UTC, mas 22h do dia 2
        # em Brasília: muda o prazo do processo 0056789 de 2027 para 2026.
        ("2025-04-03T01:00:00Z", date(2025, 4, 2)),
        # Fronteira da meia-noite em Brasília.
        ("2025-04-03T02:59:59Z", date(2025, 4, 2)),
        ("2025-04-03T03:00:00Z", date(2025, 4, 3)),
        # Horário de verão (extinto em 2019): em dezembro de 2018 Brasília
        # era -02:00. Com um offset fixo de -03:00 o resultado seria 30/11.
        # É o motivo de usar a base de fusos (tzdata) em vez de -03:00 fixo.
        ("2018-12-01T02:30:00Z", date(2018, 12, 1)),
    ],
)
def test_data_e_hora_vira_data_de_brasilia(bruto, esperado):
    resultado = normalizar_data(bruto)
    assert resultado.valor == esperado
    assert resultado.correcoes == ("data e hora convertida para a data de Brasília",)


# --- normalizar_data: rejeitados ---

@pytest.mark.parametrize("bruto", [None, "", "   "])
def test_data_ausente(bruto):
    with pytest.raises(DataInvalida) as erro:
        normalizar_data(bruto)
    assert erro.value.motivo == Motivo.AUSENTE
    assert erro.value.bruto == bruto


@pytest.mark.parametrize("bruto", ["2025-02-29", "31/02/2025", "2025-13-01", "00/04/2025"])
def test_data_inexistente(bruto):
    with pytest.raises(DataInvalida) as erro:
        normalizar_data(bruto)
    assert erro.value.motivo == Motivo.DATA_INEXISTENTE


def test_data_e_hora_sem_fuso_e_rejeitada():
    # P12: o Brasil tem 4 fusos; às 23h30 a escolha decide o dia.
    with pytest.raises(DataInvalida) as erro:
        normalizar_data("2025-04-02T23:30:00")
    assert erro.value.motivo == Motivo.FUSO_AUSENTE


@pytest.mark.parametrize(
    "bruto",
    [
        "10-04-2025",
        "2025/04/10",
        "10/4/2025",   # sem zero à esquerda: fora do padrão DD/MM/AAAA
        "04/10/25",    # ano com 2 dígitos
        "abc",
        20250410,      # número
        True,
    ],
)
def test_formato_de_data_invalido(bruto):
    with pytest.raises(DataInvalida) as erro:
        normalizar_data(bruto)
    assert erro.value.motivo == Motivo.FORMATO_DATA_INVALIDO


# --- normalizar_data_hora (atualizado_em, P13) ---

def test_data_hora_com_fuso_aceita():
    # pagamentos.json:8 (ev-001)
    resultado = normalizar_data_hora("2025-03-10T10:00:00-03:00")
    assert resultado.valor == datetime(2025, 3, 10, 10, 0, tzinfo=BRT)
    assert resultado.correcoes == ()


def test_versoes_do_ev001_ficam_na_ordem_certa():
    # pagamentos.json:8 e :72. É esta comparação que decide qual valor
    # do ev-001 vale (15000 ou 15500).
    primeira = normalizar_data_hora("2025-03-10T10:00:00-03:00").valor
    segunda = normalizar_data_hora("2025-03-11T09:00:00-03:00").valor
    assert segunda > primeira


def test_mesmo_instante_em_fusos_diferentes_e_igual():
    utc = normalizar_data_hora("2025-03-10T13:00:00Z").valor
    brt = normalizar_data_hora("2025-03-10T10:00:00-03:00").valor
    assert utc == brt


def test_data_hora_sem_fuso_e_rejeitada():
    # Sem fuso não dá para comparar versões com segurança.
    with pytest.raises(DataInvalida) as erro:
        normalizar_data_hora("2025-03-10T10:00:00")
    assert erro.value.motivo == Motivo.FUSO_AUSENTE


@pytest.mark.parametrize(
    "bruto, motivo",
    [
        (None, Motivo.AUSENTE),
        ("", Motivo.AUSENTE),
        ("2025-03-10", Motivo.FORMATO_DATA_INVALIDO),  # falta a hora
        ("10/03/2025 10:00", Motivo.FORMATO_DATA_INVALIDO),
        ("2025-02-30T10:00:00-03:00", Motivo.DATA_INEXISTENTE),
        (1741611600, Motivo.FORMATO_DATA_INVALIDO),  # timestamp numérico
    ],
)
def test_data_hora_rejeitada(bruto, motivo):
    with pytest.raises(DataInvalida) as erro:
        normalizar_data_hora(bruto)
    assert erro.value.motivo == motivo
