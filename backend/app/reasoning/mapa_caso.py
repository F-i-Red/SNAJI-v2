# -*- coding: utf-8 -*-
"""
Mapa do Caso — SNAJI
=====================
A partir do relato ou da peça, responde às perguntas práticas que decidem o
caminho de um processo:

  1. VALOR DA CAUSA — deteta os montantes em euros no texto (CPC-296).
  2. COMPETÊNCIA — com esse valor, cabe nos julgados de paz? (LJP-8: ≤ 15.000 €,
     se a matéria couber no art. 9.º da LJP — a via simples e barata.)
  3. RECURSO — a decisão admitirá recurso? (alçadas; LJP-62: nos julgados de
     paz, recurso quando o valor excede metade da alçada da 1.ª instância.)
  4. PRESCRIÇÃO — deteta datas/idades dos factos e cruza com os prazos das
     áreas detetadas (CC-498: 3 anos resp. civil; CT-337: 1 ano créditos
     laborais; CC-310: 5 anos rendas/juros; CC-309: 20 anos regra geral),
     SINALIZANDO o risco. Nunca conclui que prescreveu — a contagem tem
     interrupções e suspensões que só o profissional avalia.

Determinístico: funciona sem LLM, sobre normas do corpus. É APOIO — orienta,
nunca decide.
"""

from __future__ import annotations

import re
from datetime import date

import structlog

logger = structlog.get_logger(__name__)

# Alçadas de referência (LOSJ art. 44.º — diploma fora do corpus; valores de
# referência a confirmar): 1.ª instância 5.000 €; Relação 30.000 €.
ALCADA_1_INSTANCIA = 5_000.0
ALCADA_RELACAO = 30_000.0
LIMITE_JULGADOS_PAZ = 15_000.0

# Montantes: "4.800 €", "4800 euros", "€ 4.800,50", "15 000 EUR"
_PADRAO_VALOR = re.compile(
    r"(?:€\s*)?(\d{1,3}(?:[.\s]\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?)\s*(?:€|euros?|eur\b)",
    re.IGNORECASE,
)

# Anos (para estimar a idade dos factos) e expressões "há X anos"
_PADRAO_ANO = re.compile(r"\b(19[89]\d|20[0-4]\d)\b")
_PADRAO_HA_ANOS = re.compile(r"\bh[áa]\s+(\d{1,2})\s+anos?\b", re.IGNORECASE)

# Áreas → prazo de prescrição (anos, norma, descrição)
_PRAZOS_PRESCRICAO = [
    (re.compile(r"despedimento|salári|vencimento|entidade\s+patronal|contrato\s+de\s+trabalho|trabalhador", re.I),
     1, "CT-337", "créditos laborais: 1 ano após a cessação do contrato"),
    (re.compile(r"acidente|atropel|dano|responsabilidade\s+civil|indemniza|les[ãa]o|ofensa", re.I),
     3, "CC-498", "responsabilidade civil: 3 anos desde o conhecimento do direito"),
    (re.compile(r"renda|juro|presta[çc][õo]es\s+peri[óo]dicas|quota|alimentos", re.I),
     5, "CC-310", "rendas, juros e prestações periódicas: 5 anos"),
]
_PRAZO_GERAL = (20, "CC-309", "prazo ordinário: 20 anos")


def _para_float(s: str) -> float:
    s = s.replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def mapear_caso(texto: str) -> dict:
    """Constrói o mapa prático do caso a partir do texto."""
    t = texto or ""

    # 1) Valor da causa: o maior montante detetado (heurística; o utilizador confirma)
    valores = sorted({_para_float(m.group(1)) for m in _PADRAO_VALOR.finditer(t)}, reverse=True)
    valores = [v for v in valores if 0 < v < 100_000_000]
    valor = valores[0] if valores else None

    # 2) Competência e 3) recurso, em função do valor
    competencia = None
    recurso = None
    if valor is not None:
        if valor <= LIMITE_JULGADOS_PAZ:
            competencia = {
                "julgado_de_paz_possivel": True,
                "norma": "LJP-8",
                "nota": (f"Com valor de {valor:,.2f} € (≤ 15.000 €), o caso pode caber "
                         "num julgado de paz — a via mais simples, rápida e barata, com "
                         "mediação incluída — desde que a matéria esteja entre as do "
                         "art. 9.º da LJP (obrigações, arrendamento, condomínio, "
                         "responsabilidade civil, entre outras).").replace(",", " ").replace(".00", ",00"),
            }
            excede_metade_alcada = valor > (ALCADA_1_INSTANCIA / 2)
            recurso = {
                "admite_recurso": excede_metade_alcada,
                "norma": "LJP-62",
                "nota": ("No julgado de paz, a decisão admite recurso para o tribunal de "
                         "comarca (valor superior a metade da alçada da 1.ª instância)."
                         if excede_metade_alcada else
                         "No julgado de paz, com este valor a decisão não admite recurso — "
                         "é definitiva (LJP-62: só há recurso acima de metade da alçada "
                         "da 1.ª instância)."),
            }
        else:
            competencia = {
                "julgado_de_paz_possivel": False,
                "norma": "LJP-8",
                "nota": (f"Com valor acima de 15.000 €, o caso segue para o tribunal "
                         "judicial (fora da competência dos julgados de paz)."),
            }
            admite = valor > ALCADA_1_INSTANCIA
            recurso = {
                "admite_recurso": admite,
                "norma": "CPC-629",
                "nota": ("A decisão da 1.ª instância admitirá recurso (valor acima da alçada)."
                         if admite else
                         "Com este valor, a decisão da 1.ª instância não admitirá recurso ordinário."),
            }

    # 4) Prescrição: idade dos factos × prazos das áreas detetadas
    ano_atual = date.today().year
    anos_no_texto = [int(a) for a in _PADRAO_ANO.findall(t)]
    idades = [ano_atual - a for a in anos_no_texto if 0 <= ano_atual - a <= 60]
    idades += [int(m.group(1)) for m in _PADRAO_HA_ANOS.finditer(t)]
    idade_maxima = max(idades) if idades else None

    alertas_prescricao = []
    if idade_maxima is not None and idade_maxima >= 1:
        aplicaveis = [(prazo, norma, desc) for padrao, prazo, norma, desc in _PRAZOS_PRESCRICAO
                      if padrao.search(t)] or [_PRAZO_GERAL]
        for prazo, norma, desc in aplicaveis:
            if idade_maxima >= prazo:
                alertas_prescricao.append({
                    "norma": norma,
                    "alerta": (f"Os factos mais antigos têm ~{idade_maxima} anos e o prazo de "
                               f"prescrição aplicável pode ser de {prazo} ano(s) ({desc}). "
                               "VERIFICAR COM URGÊNCIA — a contagem tem interrupções e "
                               "suspensões que só um profissional avalia."),
                })
            elif idade_maxima >= prazo - 1:
                alertas_prescricao.append({
                    "norma": norma,
                    "alerta": (f"Os factos aproximam-se do prazo de prescrição de {prazo} "
                               f"ano(s) ({desc}). Não deixar passar mais tempo."),
                })

    normas = ["CPC-296"]
    if competencia:
        normas.append(competencia["norma"])
    if recurso:
        normas.append(recurso["norma"])
    normas += [a["norma"] for a in alertas_prescricao]

    logger.info("mapa_caso", valor=valor, alertas=len(alertas_prescricao))
    return {
        "valor_detetado": valor,
        "valores_no_texto": valores[:5],
        "competencia": competencia,
        "recurso": recurso,
        "alertas_prescricao": alertas_prescricao,
        "idade_factos_anos": idade_maxima,
        "normas": normas,
        "aviso": ("Mapa orientativo, calculado automaticamente a partir do texto — "
                  "o valor da causa, a competência e os prazos devem ser confirmados "
                  "por um profissional. O SNAJI apoia; nunca decide."),
    }
