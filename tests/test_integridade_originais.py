"""Garante que nenhum código do projeto alterou os arquivos originais.

Os hashes foram tirados do zip recebido com o desafio. Se este teste
falhar, algum passo (código, editor, Git) modificou um original.
"""
import hashlib
from pathlib import Path

import pytest

DADOS = Path(__file__).resolve().parent.parent / "case-candidato" / "dados"

SHA256_ORIGINAIS = {
    "apresentacoes.json": "0da8be22859b58fa618fae00fedad2afead6605da6c6184e7de8e8d26a93ccc2",
    "hub.csv": "75fcf6e07dc05078c35b5c7d4a3b1d38cfb3df165ab05cf5d73e155a73b83108",
    "pagamentos.json": "83e761b199bfea3413e4b614ac2c55643f2ccd0bd294d365af02a839de8f2cf8",
    "tribunal.csv": "0ce8aab43966f28bb12920956b38bb2573454c49c997f20e0dae07a8c7b2c841",
}


@pytest.mark.parametrize("nome, esperado", SHA256_ORIGINAIS.items())
def test_original_nao_foi_alterado(nome, esperado):
    conteudo = (DADOS / nome).read_bytes()
    assert hashlib.sha256(conteudo).hexdigest() == esperado


def test_nenhum_arquivo_novo_em_dados():
    assert sorted(p.name for p in DADOS.iterdir()) == sorted(SHA256_ORIGINAIS)
