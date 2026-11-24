"""Testes do normalizador de valores monetários.

Cada caso real cita o arquivo e a linha de onde veio. Casos sem citação
são defensivos: não aparecem nos dados, mas protegem contra erros que
mudariam dinheiro em silêncio.
"""
from decimal import Decimal

import pytest

from limpeza.normalizacao import Motivo, ValorInvalido, normalizar_valor


# --- Aceitos sem correção: já vêm como a documentação pede (número JSON) ---

@pytest.mark.parametrize(
    "bruto, esperado",
    [
        (Decimal("15000.0"), Decimal("15000.00")),  # pagamentos.json:5  (ev-001)
        (Decimal("15500.0"), Decimal("15500.00")),  # pagamentos.json:69 (ev-001, 2ª versão)
        (8000, Decimal("8000.00")),                 # pagamentos.json:21 (ev-003, inteiro)
        (750, Decimal("750.00")),                   # pagamentos.json:93 (ev-010)
    ],
)
def test_numero_json_aceito_sem_correcao(bruto, esperado):
    resultado = normalizar_valor(bruto)
    assert resultado.valor == esperado
    assert resultado.correcao is None


def test_float_nao_perde_precisao():
    # Se alguém carregar o JSON sem parse_float=Decimal, 0.1 vira binário
    # impreciso. A conversão precisa devolver exatamente 0.10.
    assert normalizar_valor(0.1).valor == Decimal("0.10")


# --- Corrigidos: o significado é claro, só o formato está fora do leiaute ---

@pytest.mark.parametrize(
    "bruto, esperado",
    [
        ("2.500,50", Decimal("2500.50")),    # pagamentos.json:13 (ev-002)
        ("45.000,00", Decimal("45000.00")),  # tribunal.csv:2
        ("9.800,00", Decimal("9800.00")),    # tribunal.csv:5
        ("1.234.567,89", Decimal("1234567.89")),
        ("750,5", Decimal("750.50")),
    ],
)
def test_texto_formato_brasileiro_e_corrigido(bruto, esperado):
    resultado = normalizar_valor(bruto)
    assert resultado.valor == esperado
    assert resultado.correcao == "formato brasileiro convertido"


def test_texto_com_ponto_decimal_e_corrigido():
    # hub.csv:2 traz "45000.00" -- é o formato documentado, mas como texto.
    resultado = normalizar_valor("45000.00")
    assert resultado.valor == Decimal("45000.00")
    assert resultado.correcao == "número recebido como texto"


def test_espacos_ao_redor_sao_ignorados():
    assert normalizar_valor("  2.500,50 ").valor == Decimal("2500.50")


# --- Rejeitados: corrigir exigiria adivinhar ---

@pytest.mark.parametrize(
    "bruto, motivo",
    [
        (None, Motivo.AUSENTE),               # pagamentos.json:37 (ev-004)
        ("", Motivo.AUSENTE),
        ("   ", Motivo.AUSENTE),
        (-200, Motivo.NEGATIVO),              # pagamentos.json:85 (ev-009)
        ("-2.500,50", Motivo.NEGATIVO),
        (0, Motivo.ZERO),
        ("2.500", Motivo.AMBIGUO),            # 2500 (BR) ou 2,5 (EUA)?
        ("1.000.000", Motivo.AMBIGUO),
        ("2,500.50", Motivo.NAO_RECONHECIDO), # formato americano: não esperado
        ("R$ 100,00", Motivo.NAO_RECONHECIDO),
        ("abc", Motivo.NAO_RECONHECIDO),
        (True, Motivo.NAO_RECONHECIDO),       # em Python, True é int (== 1)
        (Decimal("10.005"), Motivo.MAIS_DE_DUAS_CASAS),
        ("10,005", Motivo.NAO_RECONHECIDO),
    ],
)
def test_valores_rejeitados_com_motivo(bruto, motivo):
    with pytest.raises(ValorInvalido) as erro:
        normalizar_valor(bruto)
    assert erro.value.motivo == motivo
    assert erro.value.bruto == bruto
