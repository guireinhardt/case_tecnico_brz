"""Testes da leitura dos arquivos.

A primeira parte usa os arquivos reais do caso (somente leitura). A segunda
usa arquivos sintéticos em pasta temporária para os casos de erro.
"""
from decimal import Decimal
from pathlib import Path

import pytest

from limpeza.leitura import ArquivoInvalido, ler_csv, ler_json

DADOS = Path(__file__).resolve().parent.parent / "case-candidato" / "dados"


# --- Arquivos reais ---

def test_tribunal_csv_e_lido_como_windows_1252_com_ponto_e_virgula():
    leitura = ler_csv(
        DADOS / "tribunal.csv",
        ["numero_processo", "ente_devedor", "valor_face"],
    )
    assert leitura.codificacao == "cp1252"
    assert [r.linha for r in leitura.registros] == [2, 3, 4, 5, 6]
    # Acentos certos: sem a detecção, viria "Munic�pio de S�o Paulo".
    assert leitura.registros[0].campos["ente_devedor"] == "Município de São Paulo"
    assert leitura.registros[3].campos["ente_devedor"] == "União"
    # Valor continua texto bruto: converter é papel do normalizador.
    assert leitura.registros[0].campos["valor_face"] == "45.000,00"

    observacoes = " | ".join(leitura.observacoes)
    assert "Windows-1252, não UTF-8" in observacoes
    assert "separador ';', não ','" in observacoes
    assert "CRLF" in observacoes


def test_hub_csv_e_lido_como_utf8_sem_observacoes():
    leitura = ler_csv(
        DADOS / "hub.csv",
        ["processo", "ente", "valor_face", "apresentado_em", "prazo_pagamento"],
    )
    assert leitura.codificacao == "utf-8"
    assert leitura.observacoes == []
    assert [r.linha for r in leitura.registros] == [2, 3, 4, 5, 6]
    assert leitura.registros[1].campos["processo"] == "00234562120208260053"


def test_pagamentos_json_guarda_a_linha_de_cada_evento():
    leitura = ler_json(DADOS / "pagamentos.json")
    eventos = [(r.campos["evento_id"], r.linha) for r in leitura.registros]
    assert len(eventos) == 13
    assert eventos[0] == ("ev-001", 2)
    assert eventos[3] == ("ev-002", 26)   # a duplicata do ev-002
    assert eventos[8] == ("ev-001", 66)   # a segunda versão do ev-001
    assert leitura.registros[8].origem == "pagamentos.json:66"


def test_pagamentos_json_mantem_tipos_brutos_sem_float():
    registros = ler_json(DADOS / "pagamentos.json").registros
    assert registros[0].campos["valor"] == Decimal("15000.0")  # nunca float
    assert isinstance(registros[0].campos["valor"], Decimal)
    assert registros[1].campos["valor"] == "2.500,50"           # texto, como veio
    assert registros[2].campos["valor"] == 8000                 # int, como veio
    assert registros[4].campos["valor"] is None                  # null, como veio


def test_apresentacoes_json():
    leitura = ler_json(DADOS / "apresentacoes.json")
    assert [r.linha for r in leitura.registros] == [2, 6, 10, 14, 18, 22]
    assert leitura.registros[4].campos["apresentado_em"] == "2025-04-03T01:00:00Z"


# --- Arquivos sintéticos ---

def test_csv_com_linha_de_tamanho_errado_vira_observacao(tmp_path):
    arquivo = tmp_path / "x.csv"
    arquivo.write_bytes(b"a,b\n1,2\n3\n4,5\n")
    leitura = ler_csv(arquivo, ["a", "b"])
    assert [r.linha for r in leitura.registros] == [2, 4]
    assert leitura.observacoes == ["linha 3: 1 campos, cabeçalho tem 2"]


def test_csv_sem_coluna_obrigatoria_e_rejeitado(tmp_path):
    arquivo = tmp_path / "x.csv"
    arquivo.write_bytes(b"a,c\n1,2\n")
    with pytest.raises(ArquivoInvalido, match="colunas ausentes"):
        ler_csv(arquivo, ["a", "b"])


def test_csv_com_bom_utf8(tmp_path):
    arquivo = tmp_path / "x.csv"
    arquivo.write_bytes("﻿a,b\nSão,2\n".encode("utf-8"))
    leitura = ler_csv(arquivo, ["a", "b"])
    assert leitura.registros[0].campos == {"a": "São", "b": "2"}
    assert any("BOM" in o for o in leitura.observacoes)


def test_json_que_nao_e_lista_e_rejeitado(tmp_path):
    arquivo = tmp_path / "x.json"
    arquivo.write_bytes(b'{"a": 1}')
    with pytest.raises(ArquivoInvalido, match="lista"):
        ler_json(arquivo)


def test_json_truncado_e_rejeitado(tmp_path):
    # Simula um arquivo cortado no meio (download ou e-mail incompleto).
    arquivo = tmp_path / "x.json"
    arquivo.write_bytes(b'[\n  {"a": 1},\n  {"a": 2')
    with pytest.raises(ArquivoInvalido, match="JSON inválido"):
        ler_json(arquivo)


def test_json_lista_vazia(tmp_path):
    arquivo = tmp_path / "x.json"
    arquivo.write_bytes(b"[]")
    assert ler_json(arquivo).registros == []
