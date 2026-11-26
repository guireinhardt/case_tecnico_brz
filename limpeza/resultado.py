"""Tipos compartilhados para registrar o que não entrou na base limpa."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from limpeza.leitura import Registro


class Destino(str, Enum):
    """Para onde vai cada registro de entrada. Todo registro tem exatamente um."""

    ACEITO = "aceito"
    DESCARTADO = "descartado"
    EM_DUVIDA = "em dúvida"


@dataclass(frozen=True)
class Rejeitado:
    """Registro que não entrou na base limpa, com o motivo."""

    registro: Registro
    destino: Destino
    motivo: str
