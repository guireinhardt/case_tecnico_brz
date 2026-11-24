"""Testes do normalizador do número de processo (CNJ).

Regra central (premissa P7): as duas formas de entrada, com e sem máscara,
viram UMA chave de 20 dígitos. A máscara só existe para exibição.
"""
import pytest

from limpeza.normalizacao import Motivo, ProcessoInvalido, normalizar_processo

CHAVE_0023456 = "00234562120208260053"

# Os 6 números que aparecem nos arquivos do caso.
NUMEROS_DO_CASO = [
    "0012345-10.2019.8.26.0053",
    "0023456-21.2020.8.26.0053",
    "0034567-32.2018.8.26.0405",
    "0045678-43.2021.5.02.0011",
    "0056789-54.2017.4.03.6100",
    "0067890-65.2016.8.26.0053",
]


# --- As duas formas aceitas ---

def test_com_mascara_aceito_sem_correcao():
    # tribunal.csv:3, pagamentos.json:20
    processo = normalizar_processo("0023456-21.2020.8.26.0053")
    assert processo.chave == CHAVE_0023456
    assert processo.correcoes == ()


def test_sem_mascara_aceito_com_anotacao():
    # hub.csv:3, pagamentos.json:44 (ev-005)
    processo = normalizar_processo("00234562120208260053")
    assert processo.chave == CHAVE_0023456
    assert processo.correcoes == ("recebido sem máscara",)


def test_as_duas_formas_geram_a_mesma_chave():
    # É este teste que resolve a falsa divergência do 0023456 entre
    # tribunal.csv:3 e hub.csv:3.
    com_mascara = normalizar_processo("0023456-21.2020.8.26.0053")
    sem_mascara = normalizar_processo("00234562120208260053")
    assert com_mascara.chave == sem_mascara.chave


def test_formatado_devolve_a_mascara():
    processo = normalizar_processo("00234562120208260053")
    assert processo.formatado == "0023456-21.2020.8.26.0053"


# --- Correções de formato ---

def test_espacos_ao_redor_sao_removidos():
    processo = normalizar_processo("  0023456-21.2020.8.26.0053  ")
    assert processo.chave == CHAVE_0023456
    assert processo.correcoes == ("espaços removidos",)


def test_correcoes_se_acumulam_na_ordem_em_que_acontecem():
    processo = normalizar_processo(" 00234562120208260053 ")
    assert processo.correcoes == ("espaços removidos", "recebido sem máscara")


def test_numero_sequencial_curto_e_completado_com_zeros():
    # Premissa P8 / dúvida T7. Não ocorre nos dados atuais.
    processo = normalizar_processo("23456-21.2020.8.26.0053")
    assert processo.chave == CHAVE_0023456
    assert processo.correcoes == ("zeros à esquerda completados",)


# --- Rejeitados ---

@pytest.mark.parametrize(
    "bruto",
    [
        "",     # pagamentos.json:92 (ev-010)
        "   ",
        None,
    ],
)
def test_processo_ausente_e_rejeitado(bruto):
    with pytest.raises(ProcessoInvalido) as erro:
        normalizar_processo(bruto)
    assert erro.value.motivo == Motivo.AUSENTE
    assert erro.value.bruto == bruto


@pytest.mark.parametrize(
    "bruto",
    [
        "0023456 21 2020 8 26 0053",   # espaços no lugar dos separadores
        "0023456.21-2020.8.26.0053",   # separadores trocados
        "0023456-21.2020.8.26.005A",   # letra
        "002345621202082600531",       # 21 dígitos
        "234562120208260053",          # 18 dígitos sem máscara: não dá para saber onde faltam
        "0023456-21.2020.8.26.53",     # só o sequencial é completado; o órgão precisa de 4 dígitos
        "00000000-21.2020.8.26.0053",  # sequencial com 8 dígitos
        234562120208260053,            # int: zeros à esquerda já foram perdidos pelo JSON
        True,
    ],
)
def test_formato_invalido_e_rejeitado(bruto):
    with pytest.raises(ProcessoInvalido) as erro:
        normalizar_processo(bruto)
    assert erro.value.motivo == Motivo.FORMATO_CNJ_INVALIDO
    assert erro.value.bruto == bruto


# --- Dígito verificador: alerta, não rejeição (premissa P9) ---

def test_dv_valido_e_reconhecido():
    # Mesmo processo de tribunal.csv:2 com o DV correto (72). Conferido por
    # fórmula independente (ISO 7064): 0012345 2019 8 26 0053 72 mod 97 == 1.
    # Sem este caso, uma função que sempre devolvesse False passaria nos testes.
    assert normalizar_processo("0012345-72.2019.8.26.0053").dv_valido is True


@pytest.mark.parametrize("numero", NUMEROS_DO_CASO)
def test_numeros_do_caso_tem_dv_invalido_mas_sao_aceitos(numero):
    processo = normalizar_processo(numero)  # não pode levantar exceção
    assert processo.dv_valido is False
