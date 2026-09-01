"""
Leitura tolerante de JSON produzido por modelos de linguagem.

O modelo cita frequentemente expressões do próprio caso, e os casos dos
cidadãos trazem aspas ("a casa é antiga"). Essas aspas por escapar partem o
JSON e faziam análises completas — já geradas e já pagas — cair para o modo
de contingência. Este módulo repara os dois defeitos mais frequentes: aspas
por escapar dentro de valores, e estruturas deixadas em aberto por respostas
cortadas.
"""
from __future__ import annotations

import json
import re

import structlog

logger = structlog.get_logger(__name__)


def _escapar_aspas_internas(texto: str) -> str:
    """
    Escapa aspas duplas que aparecem dentro de valores de texto do JSON.

    Percorre o texto acompanhando se está dentro de uma string. Uma aspa
    encontrada dentro de uma string só termina o valor se for seguida (após
    espaços) por um dos caracteres que legitimamente se seguem: vírgula, dois
    pontos, chaveta ou parêntesis recto. Caso contrário, é uma aspa de citação
    e é escapada.
    """
    saida: list[str] = []
    dentro = False
    escapado = False
    for i, ch in enumerate(texto):
        if escapado:
            saida.append(ch)
            escapado = False
            continue
        if ch == "\\":
            saida.append(ch)
            escapado = True
            continue
        if ch == '"':
            if not dentro:
                dentro = True
                saida.append(ch)
            else:
                # Uma aspa fecha o valor se o que vem a seguir for ':' ou
                # '}' ou ']' — ou uma vírgula seguida de nova chave/elemento
                # ("..." , "chave":). Se vier vírgula seguida de texto comum,
                # como em «respondeu que "a casa é antiga", sem reparar», é
                # uma aspa de citação e tem de ser escapada.
                resto = texto[i + 1:].lstrip()
                seguinte = resto[:1]
                fecha = seguinte in (":", "}", "]", "")
                if seguinte == ",":
                    depois = resto[1:].lstrip()
                    fecha = depois[:1] in ('"', "{", "[", "")
                if fecha:
                    dentro = False
                    saida.append(ch)
                else:
                    saida.append('\\"')   # aspa de citação: escapar
            continue
        saida.append(ch)
    return "".join(saida)


def ler_json(raw: str, componente: str = "llm") -> dict:
    """Devolve o dicionário; levanta ValueError se for irrecuperável."""
    raw = re.sub(r"```json|```", "", raw or "").strip()

    def _tentar(texto: str) -> dict | None:
        try:
            valor = json.loads(texto)
            return valor if isinstance(valor, dict) else None
        except json.JSONDecodeError:
            return None

    dados = _tentar(raw)
    if dados is not None:
        return dados

    m = re.search(r"\{.*\}", raw, re.DOTALL)
    bloco = m.group() if m else raw
    dados = _tentar(bloco)
    if dados is not None:
        return dados

    reparado = _escapar_aspas_internas(bloco)
    dados = _tentar(reparado)
    if dados is not None:
        logger.info(f"{componente}.json.reparado", motivo="aspas por escapar")
        return dados

    tentativa = reparado.rstrip().rstrip(",")
    for sufixo in ('"}]}', '"}]}}', '"}}', '}]}', ']}', '}}', '}'):
        dados = _tentar(tentativa + sufixo)
        if dados is not None:
            logger.info(f"{componente}.json.reparado", motivo="estrutura incompleta")
            return dados

    # Diagnóstico: sem ver a resposta, não é possível saber se o modelo
    # devolveu texto corrido, uma recusa, ou uma estrutura irreparável.
    logger.warning(
        f"{componente}.json.irrecuperavel",
        tamanho=len(raw),
        inicio=raw[:180].replace("\n", " "),
        fim=raw[-180:].replace("\n", " ") if len(raw) > 180 else "",
    )
    raise ValueError("resposta do modelo não contém JSON recuperável")
