"""Testes do programa completo, rodando sobre os arquivos reais."""
from pathlib import Path

from limpeza.__main__ import DADOS_PADRAO, executar, main

ARQUIVOS_SAIDA = ["precatorios.csv", "pagamentos.csv", "rejeitados.csv", "relatorio.md"]


def test_gera_todas_as_saidas(tmp_path):
    executar(DADOS_PADRAO, tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(ARQUIVOS_SAIDA)


def test_saida_e_deterministica(tmp_path):
    # Rodar de novo com os mesmos arquivos dá exatamente os mesmos bytes.
    executar(DADOS_PADRAO, tmp_path / "a")
    executar(DADOS_PADRAO, tmp_path / "b")
    for nome in ARQUIVOS_SAIDA:
        assert (tmp_path / "a" / nome).read_bytes() == (tmp_path / "b" / nome).read_bytes()


def test_relatorio_cita_as_evidencias(tmp_path):
    executar(DADOS_PADRAO, tmp_path)
    relatorio = (tmp_path / "relatorio.md").read_text(encoding="utf-8")
    assert "Windows-1252" in relatorio
    assert "pagamentos.json:26" in relatorio   # duplicata do ev-002
    assert "pagamentos.json:2 " in relatorio   # versão substituída do ev-001
    assert "hub 31000.00 (hub.csv:3)" in relatorio


def test_pasta_de_dados_inexistente_retorna_erro(tmp_path, capsys):
    assert main(["--dados", str(tmp_path / "nao-existe"), "--saida", str(tmp_path)]) == 1
    assert "erro" in capsys.readouterr().err
