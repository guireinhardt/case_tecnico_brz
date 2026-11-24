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
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from zoneinfo import ZoneInfo

CENTAVO = Decimal("0.01")
# Fuso de referência para transformar data e hora em data (premissa P11).
# A base IANA conhece o horário de verão que vigorou até 2019; um offset
# fixo de -03:00 erraria datas antigas.
BRASILIA = ZoneInfo("America/Sao_Paulo")


class Motivo(str, Enum):
    """Por que um dado foi rejeitado. Vai para o relatório como código."""

    AUSENTE = "campo ausente"
    NEGATIVO = "valor negativo"
    ZERO = "valor zero"
    AMBIGUO = "formato ambíguo"
    NAO_RECONHECIDO = "formato não reconhecido"
    MAIS_DE_DUAS_CASAS = "mais de duas casas decimais"
    FORMATO_CNJ_INVALIDO = "formato CNJ inválido"
    FORMATO_DATA_INVALIDO = "formato de data inválido"
    DATA_INEXISTENTE = "data inexistente"
    FUSO_AUSENTE = "data e hora sem fuso horário"


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


# ---------------------------------------------------------------------------
# Número do processo (CNJ)
# ---------------------------------------------------------------------------


class ProcessoInvalido(ValueError):
    """O número do processo não pode ser convertido sem adivinhar."""

    def __init__(self, motivo: Motivo, bruto: object) -> None:
        super().__init__(f"{motivo.value}: {bruto!r}")
        self.motivo = motivo
        self.bruto = bruto


@dataclass(frozen=True)
class Processo:
    """Número do processo normalizado.

    chave: os 20 dígitos, usada para cruzar arquivos e gravar no banco.
    correcoes: o que precisou ser ajustado no formato, na ordem em que aconteceu.
    dv_valido: resultado da conferência do dígito verificador (só alerta).
    """

    chave: str
    correcoes: tuple[str, ...] = ()
    dv_valido: bool = False

    @property
    def formatado(self) -> str:
        """A chave com a máscara NNNNNNN-DD.AAAA.J.TR.OOOO, para exibição."""
        c = self.chave
        return f"{c[0:7]}-{c[7:9]}.{c[9:13]}.{c[13]}.{c[14:16]}.{c[16:20]}"


# Com máscara. O primeiro grupo aceita de 1 a 7 dígitos para permitir
# completar os zeros à esquerda (premissa P8); os demais têm tamanho exato.
_CNJ_COM_MASCARA = re.compile(r"^(\d{1,7})-(\d{2})\.(\d{4})\.(\d)\.(\d{2})\.(\d{4})$")
# Sem máscara: exatamente 20 dígitos.
_CNJ_SEM_MASCARA = re.compile(r"^\d{20}$")


def normalizar_processo(bruto: object) -> Processo:
    """Converte o número do processo na chave de 20 dígitos.

    Aceita a forma com máscara ou os 20 dígitos. Levanta ProcessoInvalido
    quando o número é ausente ou está em qualquer outro formato.
    """
    correcoes: list[str] = []

    # Passo 1: ausente.
    if bruto is None:
        raise ProcessoInvalido(Motivo.AUSENTE, bruto)

    # Passo 2: só texto é aceito. Um int já perdeu os zeros à esquerda
    # (00234562120208260053 vira 234562120208260053) e bool é int em Python.
    if not isinstance(bruto, str):
        raise ProcessoInvalido(Motivo.FORMATO_CNJ_INVALIDO, bruto)

    # Passo 3: espaços ao redor.
    texto = bruto.strip()
    if not texto:
        raise ProcessoInvalido(Motivo.AUSENTE, bruto)
    if texto != bruto:
        correcoes.append("espaços removidos")

    # Passo 4: forma com máscara (a documentada pelo tribunal).
    com_mascara = _CNJ_COM_MASCARA.match(texto)
    if com_mascara:
        sequencial, dv, ano, justica, tribunal, origem = com_mascara.groups()
        if len(sequencial) < 7:
            sequencial = sequencial.zfill(7)
            correcoes.append("zeros à esquerda completados")
        chave = sequencial + dv + ano + justica + tribunal + origem

    # Passo 5: só os 20 dígitos.
    elif _CNJ_SEM_MASCARA.match(texto):
        chave = texto
        correcoes.append("recebido sem máscara")

    # Passo 6: qualquer outra coisa seria palpite.
    else:
        raise ProcessoInvalido(Motivo.FORMATO_CNJ_INVALIDO, bruto)

    return Processo(chave, tuple(correcoes), _dv_valido(chave))


def _dv_valido(chave: str) -> bool:
    """Confere o dígito verificador (Res. CNJ 65/2008, ISO 7064 módulo 97).

    O DV vai para o final do número e o resto da divisão por 97 deve ser 1.
    """
    sequencial, dv, resto = chave[0:7], chave[7:9], chave[9:20]
    return int(sequencial + resto + dv) % 97 == 1


# ---------------------------------------------------------------------------
# Datas
# ---------------------------------------------------------------------------


class DataInvalida(ValueError):
    """A data não pode ser convertida sem adivinhar."""

    def __init__(self, motivo: Motivo, bruto: object) -> None:
        super().__init__(f"{motivo.value}: {bruto!r}")
        self.motivo = motivo
        self.bruto = bruto


@dataclass(frozen=True)
class Data:
    """Data convertida (só dia) e as correções de formato feitas."""

    valor: date
    correcoes: tuple[str, ...] = ()


@dataclass(frozen=True)
class DataHora:
    """Data e hora com fuso, e as correções de formato feitas."""

    valor: datetime
    correcoes: tuple[str, ...] = ()


# "2025-03-10": o formato documentado.
_DATA_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
# "10/04/2025": sempre lido como dia/mês (padrão brasileiro, premissa P10).
_DATA_BRASILEIRA = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
# "2025-04-02T23:30:00-03:00" ou "...Z". O fuso é opcional no padrão só
# para que a ausência dele tenha um motivo próprio (FUSO_AUSENTE).
_DATA_HORA_ISO = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(?P<fuso>Z|[+-]\d{2}:\d{2})?$"
)


def normalizar_data(bruto: object) -> Data:
    """Converte uma data bruta em date (premissas P10-P12).

    Aceita AAAA-MM-DD, DD/MM/AAAA e data e hora com fuso; esta última vira
    a data correspondente em Brasília. Levanta DataInvalida nos demais casos.
    """
    texto, correcoes = _texto_obrigatorio(bruto)

    if _DATA_ISO.match(texto):
        return Data(_criar_data(texto, bruto), tuple(correcoes))

    brasileira = _DATA_BRASILEIRA.match(texto)
    if brasileira:
        dia, mes, ano = brasileira.groups()
        correcoes.append("formato DD/MM/AAAA convertido")
        return Data(_criar_data(f"{ano}-{mes}-{dia}", bruto), tuple(correcoes))

    if _DATA_HORA_ISO.match(texto):
        instante = _criar_data_hora(texto, bruto)
        correcoes.append("data e hora convertida para a data de Brasília")
        return Data(instante.astimezone(BRASILIA).date(), tuple(correcoes))

    raise DataInvalida(Motivo.FORMATO_DATA_INVALIDO, bruto)


def normalizar_data_hora(bruto: object) -> DataHora:
    """Converte data e hora com fuso em datetime (premissa P13).

    Usado em atualizado_em, que decide qual versão de um evento é a mais
    nova. Exige fuso: sem ele, a ordem entre duas versões pode sair errada.
    """
    texto, correcoes = _texto_obrigatorio(bruto)
    if not _DATA_HORA_ISO.match(texto):
        raise DataInvalida(Motivo.FORMATO_DATA_INVALIDO, bruto)
    return DataHora(_criar_data_hora(texto, bruto), tuple(correcoes))


def _texto_obrigatorio(bruto: object) -> tuple[str, list[str]]:
    """Etapas comuns às datas: ausente, tipo e espaços ao redor."""
    if bruto is None:
        raise DataInvalida(Motivo.AUSENTE, bruto)
    if not isinstance(bruto, str):
        raise DataInvalida(Motivo.FORMATO_DATA_INVALIDO, bruto)
    texto = bruto.strip()
    if not texto:
        raise DataInvalida(Motivo.AUSENTE, bruto)
    return texto, (["espaços removidos"] if texto != bruto else [])


def _criar_data(iso: str, bruto: object) -> date:
    """O formato já foi conferido; aqui só falha data impossível (31/02)."""
    try:
        return date.fromisoformat(iso)
    except ValueError:
        raise DataInvalida(Motivo.DATA_INEXISTENTE, bruto) from None


def _criar_data_hora(texto: str, bruto: object) -> datetime:
    """Interpreta data e hora ISO já conferida pelo padrão; exige fuso."""
    if _DATA_HORA_ISO.match(texto).group("fuso") is None:
        raise DataInvalida(Motivo.FUSO_AUSENTE, bruto)
    # Python 3.10 não aceita o sufixo "Z" no fromisoformat (só a partir do
    # 3.11), e o projeto declara suporte ao 3.10.
    if texto.endswith("Z"):
        texto = texto[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(texto)
    except ValueError:
        raise DataInvalida(Motivo.DATA_INEXISTENTE, bruto) from None

