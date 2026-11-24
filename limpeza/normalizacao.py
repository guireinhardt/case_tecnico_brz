"""Normalizadores: convertem valores brutos dos arquivos em tipos confiáveis.

Princípio que guia todas as funções deste módulo:

* Corrigir o FORMATO é permitido, porque preserva o significado
  ("2.500,50" -> 2500.50). A correção é devolvida para entrar no relatório.
* Reinterpretar o SIGNIFICADO não é permitido. Quando a única saída seria
  adivinhar, a função levanta uma exceção com o motivo, e quem chamou
  decide se o registro é descartado ou fica em dúvida.

Funções puras: não leem arquivos nem guardam estado, por isso são fáceis
de testar.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum

CENTAVO = Decimal("0.01")


class Motivo(str, Enum):
    """Por que um valor foi rejeitado. Vai para o relatório como código."""

    AUSENTE = "valor ausente"
    NEGATIVO = "valor negativo"
    ZERO = "valor zero"
    AMBIGUO = "formato ambíguo"
    NAO_RECONHECIDO = "formato não reconhecido"
    MAIS_DE_DUAS_CASAS = "mais de duas casas decimais"


class ValorInvalido(ValueError):
    """O valor não pode ser convertido sem adivinhar."""

    def __init__(self, motivo: Motivo, bruto: object) -> None:
        super().__init__(f"{motivo.value}: {bruto!r}")
        self.motivo = motivo
        self.bruto = bruto


@dataclass(frozen=True)
class Valor:
    """Valor convertido e, se houve, a descrição da correção feita."""

    valor: Decimal
    correcao: str | None = None


# "2.500,50", "45.000,00", "750,5": separador de milhar opcional, vírgula decimal.
_BRASILEIRO = re.compile(r"^(\d{1,3}(\.\d{3})+|\d+),\d{1,2}$")
# "2.500", "1.000.000": pode ser milhar brasileiro ou decimal americano.
_AMBIGUO = re.compile(r"^\d{1,3}(\.\d{3})+$")
# "45000.00", "8000": o formato documentado, só que como texto.
_PONTO_DECIMAL = re.compile(r"^\d+(\.\d{1,2})?$")


def normalizar_valor(bruto: object) -> Valor:
    """Converte um valor monetário bruto em Decimal com 2 casas.

    Aceita número JSON (int/float/Decimal) e texto nos formatos brasileiro
    ou com ponto decimal. Levanta ValorInvalido quando o valor é ausente,
    zero, negativo, ambíguo ou desconhecido.
    """
    if bruto is None:
        raise ValorInvalido(Motivo.AUSENTE, bruto)

    # bool vem antes de int: em Python, isinstance(True, int) é verdadeiro,
    # e True viraria 1 real.
    if isinstance(bruto, bool):
        raise ValorInvalido(Motivo.NAO_RECONHECIDO, bruto)

    if isinstance(bruto, (int, float, Decimal)):
        # str(float) dá a representação mais curta (0.1 -> "0.1"), evitando
        # Decimal(0.1) = 0.1000000000000000055511151231257827...
        numero = Decimal(str(bruto)) if isinstance(bruto, float) else Decimal(bruto)
        return Valor(_validar(numero, bruto))

    if isinstance(bruto, str):
        texto = bruto.strip()
        if not texto:
            raise ValorInvalido(Motivo.AUSENTE, bruto)
        negativo = texto.startswith("-")
        corpo = texto[1:] if negativo else texto

        if _BRASILEIRO.match(corpo):
            numero = Decimal(corpo.replace(".", "").replace(",", "."))
            correcao = "formato brasileiro convertido"
        elif _AMBIGUO.match(corpo):
            raise ValorInvalido(Motivo.AMBIGUO, bruto)
        elif _PONTO_DECIMAL.match(corpo):
            numero = Decimal(corpo)
            correcao = "número recebido como texto"
        else:
            raise ValorInvalido(Motivo.NAO_RECONHECIDO, bruto)

        return Valor(_validar(-numero if negativo else numero, bruto), correcao)

    raise ValorInvalido(Motivo.NAO_RECONHECIDO, bruto)


def _validar(numero: Decimal, bruto: object) -> Decimal:
    """Regras comuns a qualquer origem: finito, positivo, no máximo centavos."""
    try:
        if not numero.is_finite():
            raise ValorInvalido(Motivo.NAO_RECONHECIDO, bruto)
        if numero < 0:
            raise ValorInvalido(Motivo.NEGATIVO, bruto)
        if numero == 0:
            raise ValorInvalido(Motivo.ZERO, bruto)
        # Arredondar 10.005 para 10.00 ou 10.01 mudaria dinheiro em silêncio
        # (o banco faria isso sozinho, já que a coluna é NUMERIC(15,2)).
        if numero != numero.quantize(CENTAVO):
            raise ValorInvalido(Motivo.MAIS_DE_DUAS_CASAS, bruto)
        return numero.quantize(CENTAVO)
    except InvalidOperation:
        raise ValorInvalido(Motivo.NAO_RECONHECIDO, bruto) from None
