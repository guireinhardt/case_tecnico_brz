"""Teste de ponta a ponta contra o gabarito montado à mão.

O gabarito foi calculado lendo os arquivos e aplicando as premissas do
DIAGNOSTICO.md, sem rodar o código. O programa só está certo se chegar
nos mesmos números por outro caminho.
"""
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from limpeza.leitura import ler_csv, ler_json
from limpeza.pagamentos import processar_pagamentos
from limpeza.precatorios import montar_precatorios
from limpeza.resultado import Destino

DADOS = Path(__file__).resolve().parent.parent / "case-candidato" / "dados"

# (evento, linha do '{' em pagamentos.json) -> destino esperado
GABARITO_EVENTOS = {
    ("ev-001", 2): Destino.DESCARTADO,   # versão antiga, substituída pela da linha 66
    ("ev-002", 10): Destino.ACEITO,      # valor e data corrigidos de formato
    ("ev-003", 18): Destino.ACEITO,
    ("ev-002", 26): Destino.DESCARTADO,  # duplicata idêntica da linha 10
    ("ev-004", 34): Destino.DESCARTADO,  # valor null
    ("ev-005", 42): Destino.ACEITO,      # processo sem máscara, corrigido
    ("ev-006", 50): Destino.ACEITO,
    ("ev-007", 58): Destino.ACEITO,      # estorno: subtrai
    ("ev-001", 66): Destino.ACEITO,      # versão mais recente (15.500)
    ("ev-008", 74): Destino.ACEITO,
    ("ev-009", 82): Destino.EM_DUVIDA,   # valor negativo
    ("ev-010", 90): Destino.DESCARTADO,  # processo vazio
    ("ev-011", 98): Destino.ACEITO,      # precatório fora do hub: aceito com alerta
}

# Total pago esperado por processo (pagamentos - estornos).
GABARITO_TOTAIS = {
    "00123451020198260053": Decimal("18000.50"),  # 15.500 (ev-001 v2) + 2.500,50 (ev-002)
    "00234562120208260053": Decimal("9200.00"),   # 8.000 (ev-003) + 1.200 (ev-005)
    "00345673220188260405": Decimal("0.00"),      # 5.000 (ev-006) - 5.000 (ev-007)
    "00456784320215020011": Decimal("3000.00"),   # ev-008
    "00567895420174036100": Decimal("0.00"),      # ev-009 em dúvida
    "00678906520168260053": Decimal("4000.00"),   # ev-011
}

# Situação esperada de cada precatório no cruzamento.
GABARITO_PRECATORIOS = {
    "00123451020198260053": ("divergente", date(2026, 12, 31)),           # prazo: hub diz 2027
    "00234562120208260053": ("divergente", date(2027, 12, 31)),           # valor 30.000 x 31.000
    "00345673220188260405": ("conferido", date(2025, 12, 31)),
    "00456784320215020011": ("divergente", date(2026, 12, 31)),           # União x Santos
    "00567895420174036100": ("ausente no tribunal", date(2026, 12, 31)),  # e prazo: hub diz 2027
    # Apresentado em 31/12/2023, depois de 2 de abril: 2023 + 2 = 2025.
    # (O gabarito à mão dizia 2024; o teste revelou o erro do gabarito.)
    "00678906520168260053": ("ausente no hub", date(2025, 12, 31)),
}


@pytest.fixture(scope="module")
def resultado():
    tribunal = ler_csv(DADOS / "tribunal.csv", ["numero_processo", "ente_devedor", "valor_face"])
    hub = ler_csv(
        DADOS / "hub.csv",
        ["processo", "ente", "valor_face", "apresentado_em", "prazo_pagamento"],
    )
    apresentacoes = ler_json(DADOS / "apresentacoes.json")
    pagamentos = ler_json(DADOS / "pagamentos.json")
    precatorios = montar_precatorios(tribunal.registros, hub.registros, apresentacoes.registros)
    return precatorios, processar_pagamentos(pagamentos.registros, precatorios.precatorios)


def test_destino_de_cada_evento(resultado):
    _, pagamentos = resultado
    obtido = {(p.evento_id, p.registro.linha): Destino.ACEITO for p in pagamentos.aceitos}
    for r in pagamentos.rejeitados:
        obtido[(r.registro.campos["evento_id"], r.registro.linha)] = r.destino
    assert obtido == GABARITO_EVENTOS


def test_conservacao_nada_some_nada_aparece(resultado):
    _, pagamentos = resultado
    assert pagamentos.entrada == 13
    assert len(pagamentos.aceitos) == 8
    destinos = [r.destino for r in pagamentos.rejeitados]
    assert destinos.count(Destino.DESCARTADO) == 4
    assert destinos.count(Destino.EM_DUVIDA) == 1


def test_total_pago_por_processo(resultado):
    _, pagamentos = resultado
    for chave, esperado in GABARITO_TOTAIS.items():
        assert pagamentos.total_pago(chave) == esperado, chave


def test_situacao_e_prazo_de_cada_precatorio(resultado):
    precatorios, _ = resultado
    obtido = {
        chave: (p.situacao, p.prazo_pagamento)
        for chave, p in precatorios.precatorios.items()
    }
    assert obtido == GABARITO_PRECATORIOS


def test_tribunal_prevalece_na_divergencia(resultado):
    precatorios, _ = resultado
    p = precatorios.precatorios
    assert p["00234562120208260053"].valor_face == Decimal("30000.00")  # hub: 31.000
    assert p["00456784320215020011"].ente_devedor == "União"            # hub: Santos


def test_grafia_diferente_do_ente_nao_e_divergencia(resultado):
    precatorios, _ = resultado
    p = precatorios.precatorios["00123451020198260053"]  # MUNICIPIO DE SAO PAULO no hub
    assert not any("ente" in d for d in p.divergencias)
    assert any("diferença só de maiúsculas/acentos" in c for c in p.correcoes)


def test_alertas_dos_eventos_aceitos(resultado):
    _, pagamentos = resultado
    alertas = {p.evento_id: " ".join(p.alertas) for p in pagamentos.aceitos}
    assert "estorno" in alertas["ev-007"]
    assert "hub.csv" in alertas["ev-011"]
    assert "antes da apresentação" in alertas["ev-001"]  # pago 10/03, apresentado 02/04
