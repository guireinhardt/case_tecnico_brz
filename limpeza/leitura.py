"""Leitura dos arquivos como vieram, preservando a origem de cada registro.

Este módulo NÃO interpreta valores: devolve os campos brutos (texto no CSV,
tipos do JSON) junto com o arquivo e a linha de onde vieram. Converter é
papel dos normalizadores. Assim, todo problema encontrado depois pode ser
citado como evidência no formato "arquivo:linha".

O que a leitura descobre sobre o próprio arquivo (codificação, separador,
quebra de linha) é devolvido em `observacoes`, para entrar no relatório.
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path


class ArquivoInvalido(Exception):
    """O arquivo inteiro não pode ser lido (não só um registro)."""


@dataclass(frozen=True)
class Registro:
    """Um registro bruto e sua origem."""

    arquivo: str
    linha: int
    campos: dict[str, object]

    @property
    def origem(self) -> str:
        """Referência curta para o relatório, ex.: 'pagamentos.json:66'."""
        return f"{self.arquivo}:{self.linha}"


@dataclass
class Leitura:
    """Resultado da leitura de um arquivo."""

    arquivo: str
    codificacao: str
    registros: list[Registro] = field(default_factory=list)
    observacoes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Codificação
# ---------------------------------------------------------------------------


def _decodificar(conteudo: bytes, nome: str, esperada: str) -> tuple[str, str, list[str]]:
    """Tenta UTF-8 estrito; se falhar, Windows-1252 (padrão do Excel pt-BR).

    Devolve o texto, a codificação usada e observações para o relatório.
    """
    observacoes: list[str] = []
    if conteudo.startswith(b"\xef\xbb\xbf"):
        observacoes.append("arquivo começa com BOM UTF-8 (removido na leitura)")
        conteudo = conteudo[3:]
    try:
        texto, codificacao = conteudo.decode("utf-8"), "utf-8"
    except UnicodeDecodeError as erro:
        try:
            texto, codificacao = conteudo.decode("cp1252"), "cp1252"
        except UnicodeDecodeError:
            raise ArquivoInvalido(
                f"{nome}: codificação não reconhecida (nem UTF-8 nem Windows-1252)"
            ) from None
        observacoes.append(
            f"codificação Windows-1252, não {esperada} como documentado "
            f"(primeiro byte inválido em UTF-8 na posição {erro.start}: "
            f"0x{conteudo[erro.start]:02X})"
        )
    if "\r\n" in texto:
        observacoes.append("quebras de linha no padrão Windows (CRLF)")
    return texto, codificacao, observacoes


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


def ler_csv(
    caminho: Path,
    colunas_esperadas: list[str],
    separador_esperado: str = ",",
    codificacao_esperada: str = "UTF-8",
) -> Leitura:
    """Lê um CSV detectando codificação e separador.

    O separador é deduzido do cabeçalho (vírgula ou ponto e vírgula). Linhas
    com quantidade de campos diferente do cabeçalho não são descartadas em
    silêncio: viram observação com a linha.
    """
    nome = caminho.name
    texto, codificacao, observacoes = _decodificar(
        caminho.read_bytes(), nome, codificacao_esperada
    )

    primeira_linha = texto.splitlines()[0] if texto else ""
    separador = ";" if primeira_linha.count(";") > primeira_linha.count(",") else ","
    if separador != separador_esperado:
        observacoes.append(
            f"separador '{separador}', não '{separador_esperado}' como documentado"
        )

    leitor = csv.reader(io.StringIO(texto, newline=""), delimiter=separador)
    try:
        cabecalho = [coluna.strip() for coluna in next(leitor)]
    except StopIteration:
        raise ArquivoInvalido(f"{nome}: arquivo vazio") from None

    faltando = [c for c in colunas_esperadas if c not in cabecalho]
    if faltando:
        raise ArquivoInvalido(f"{nome}: colunas ausentes no cabeçalho: {faltando}")
    extras = [c for c in cabecalho if c not in colunas_esperadas]
    if extras:
        observacoes.append(f"colunas não documentadas: {extras}")

    leitura = Leitura(nome, codificacao, observacoes=observacoes)
    for campos in leitor:
        linha = leitor.line_num
        if not any(c.strip() for c in campos):
            continue  # linha em branco
        if len(campos) != len(cabecalho):
            leitura.observacoes.append(
                f"linha {linha}: {len(campos)} campos, cabeçalho tem {len(cabecalho)}"
            )
            continue
        leitura.registros.append(Registro(nome, linha, dict(zip(cabecalho, campos))))
    return leitura


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------


def ler_json(caminho: Path, codificacao_esperada: str = "UTF-8") -> Leitura:
    """Lê um JSON que é uma lista de objetos, guardando a linha de cada um.

    Números com casas decimais viram Decimal (parse_float), nunca float:
    15000.0 não pode virar uma aproximação binária antes de ser normalizado.
    """
    nome = caminho.name
    texto, codificacao, observacoes = _decodificar(
        caminho.read_bytes(), nome, codificacao_esperada
    )
    leitura = Leitura(nome, codificacao, observacoes=observacoes)

    decodificador = json.JSONDecoder(parse_float=Decimal)
    posicao = _pular_espacos(texto, 0)
    if not texto.startswith("[", posicao):
        raise ArquivoInvalido(f"{nome}: esperado uma lista JSON ('[')")
    posicao = _pular_espacos(texto, posicao + 1)

    # Percorre a lista objeto a objeto, em vez de json.loads de uma vez,
    # para saber em que linha cada objeto começa.
    while not texto.startswith("]", posicao):
        linha = texto.count("\n", 0, posicao) + 1
        try:
            objeto, posicao = decodificador.raw_decode(texto, posicao)
        except json.JSONDecodeError as erro:
            raise ArquivoInvalido(f"{nome}: JSON inválido na linha {erro.lineno}") from None
        if not isinstance(objeto, dict):
            raise ArquivoInvalido(f"{nome}:{linha}: esperado um objeto, veio {type(objeto).__name__}")
        leitura.registros.append(Registro(nome, linha, objeto))

        posicao = _pular_espacos(texto, posicao)
        if texto.startswith(",", posicao):
            posicao = _pular_espacos(texto, posicao + 1)
        elif not texto.startswith("]", posicao):
            linha_erro = texto.count("\n", 0, posicao) + 1
            raise ArquivoInvalido(f"{nome}: JSON inválido na linha {linha_erro}")

    if texto[posicao + 1:].strip():
        raise ArquivoInvalido(f"{nome}: conteúdo após o fim da lista")
    return leitura


def _pular_espacos(texto: str, posicao: int) -> int:
    while posicao < len(texto) and texto[posicao] in " \t\r\n":
        posicao += 1
    return posicao
