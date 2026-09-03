"""
Pseudonimização de dados pessoais antes do envio para serviços externos.

Porquê: o texto do caso escrito pelo cidadão vai integralmente para o modelo
de linguagem. Enquanto esse modelo for um serviço externo, tudo o que a
pessoa escrever — número de contribuinte, telefone, morada, IBAN — sai do
sistema. Esta camada substitui esses elementos por marcadores antes do
envio e repõe-nos na resposta, de modo que o utilizador não nota diferença
mas os identificadores nunca atravessam a fronteira.

Alcance honesto desta implementação:
- Cobre identificadores com formato reconhecível: NIF, NISS, cartão de
  cidadão, telefone, email, IBAN, matrícula, código postal, número de
  utente de saúde e datas de nascimento.
- NÃO cobre nomes de pessoas. Detectar nomes em texto livre exige
  reconhecimento de entidades nomeadas (um modelo treinado para o efeito);
  tentá-lo por expressões regulares produziria falsos positivos graves
  ("Tribunal Judicial de Lisboa", "Código Civil") e falsos negativos
  perigosos. É o passo seguinte, e está assinalado como tal.

Por isso: esta camada reduz a exposição, não a elimina. A eliminação real
só chega com o modelo de linguagem a correr em infraestrutura própria.
"""
from __future__ import annotations

import re

# Ordem importa: os padrões mais específicos primeiro, para o IBAN não ser
# consumido pelo padrão de números longos, etc.
_PADROES: list[tuple[str, re.Pattern]] = [
    # A ordem é significativa. Os padrões ancorados numa palavra-chave
    # ("NIF 213456789", "nasci em 03/07/1988") vêm primeiro: sem isso, o
    # padrão genérico de telefone apanhava números de contribuinte, e o
    # padrão de IBAN — tolerante a espaços — engolia datas.
    #
    # As variantes cobertas foram levantadas por ensaio deliberado de formas
    # hostis: abreviaturas com pontos ("n.i.f."), ausência de separador
    # ("NIF213456789"), enumerações ("o meu e o da minha mulher: X e Y") e a
    # palavra-chave depois do valor ("14/02/1991 (data de nascimento)").
    ("NIF", re.compile(
        r"\b(?:n\.?\s?i\.?\s?f\.?|nif|niss|nipc|contribuinte|"
        r"n\.?[ºo°]?\s*fiscal|n[uú]mero\s+fiscal)[^\d\n]{0,25}(\d{9})\b", re.I)),
    # Segundo e seguintes números de uma enumeração: só apanha quando o que
    # vem antes já foi mascarado como NIF.
    # A distância tolerada cobre frases como "o meu e o do meu marido é X"
    # ou "os nossos números são X e Y", mantendo-se dentro da mesma frase
    # (não atravessa ponto final nem mudança de linha).
    # Não apanha valores monetários: um número de nove dígitos seguido de
    # "euros" ou "€" é um montante, não um contribuinte.
    ("NIF", re.compile(r"\[NIF_\d+\][^\d\n.]{0,40}(\d{9})\b(?!\s*(?:euros?|€))")),

    ("NUM_UTENTE", re.compile(
        r"\b(?:utente|sns)\b[^\d\n]{0,25}(\d{9})\b", re.I)),

    ("DATA_NASCIMENTO", re.compile(
        r"\b(?:nasci|nascid[oa]|d\.?\s?n\.?|data\s+de\s+nascimento)"
        r"[^\d\n]{0,20}(\d{1,2}[/-]\d{1,2}[/-]\d{4})\b", re.I)),
    ("DATA_NASCIMENTO", re.compile(
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})(?=[^\d\n]{0,6}\(?\s*(?:data\s+de\s+)?nascim)", re.I)),
    ("DATA_NASCIMENTO", re.compile(
        r"\b(?:nasci|nascid[oa])\s+(?:em|a)\s+"
        r"(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})", re.I)),

    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b")),

    # IBAN em todas as formas correntes, e o NIB (21 dígitos sem prefixo).
    ("IBAN", re.compile(r"\bPT\s?50[\s-]?(?:\d[\s-]?){21}\b", re.I)),
    ("NIB", re.compile(r"(?<![\d.])(?:\d[\s-]?){20}\d(?![\d.])")),

    # Cartão de cidadão: com dígito de controlo, ou apenas os dígitos quando
    # precedido da designação.
    ("CARTAO_CIDADAO", re.compile(r"\b\d{8}\s?\d?\s?[A-Z]{2}\d\b")),
    ("CARTAO_CIDADAO", re.compile(
        r"\b(?:cart[aã]o\s+de\s+cidad[aã]o|cc|bi|bilhete\s+de\s+identidade)\b"
        r"[^\d\n]{0,20}(\d{7,8})\b", re.I)),

    ("MATRICULA", re.compile(
        r"\b(?:[A-Z]{2}[\s-]\d{2}[\s-][A-Z]{2}|\d{2}[\s-][A-Z]{2}[\s-]\d{2}|"
        r"[A-Z]{2}[\s-]\d{2}[\s-]\d{2}|\d{2}[\s-]\d{2}[\s-][A-Z]{2})\b")),

    ("CODIGO_POSTAL", re.compile(r"\b\d{4}-\d{3}\b")),

    # Telefones portugueses: 9 dígitos começados por 2 (fixos, de todos os
    # indicativos regionais) ou por 9 (telemóveis), com agrupamento livre.
    # Não apanha montantes: um número de nove dígitos seguido de "euros" ou
    # "€" é um valor, não um telefone. Sem esta guarda, "custou 250000000
    # euros" era mascarado.
    ("TELEFONE", re.compile(
        r"(?<![\d\-/.])(?:(?:\+|00)\s?351[\s-]?|\(\+351\)[\s-]?)?"
        r"[29](?:[\s-]?\d){8}(?![\d\-/])(?!\s*(?:euros?|€))")),
]



def pseudonimizar(texto: str) -> tuple[str, dict[str, str]]:
    """
    Substitui identificadores por marcadores.
    Devolve o texto tratado e o mapa para reposição posterior.
    """
    if not texto:
        return texto, {}

    mapa: dict[str, str] = {}
    contadores: dict[str, int] = {}
    resultado = texto

    for etiqueta, padrao in _PADROES:
        def _troca(m: re.Match) -> str:
            # Quando o padrão captura um grupo, só esse grupo é substituído:
            # a palavra-chave ("NIF:", "nasci em") permanece, para o modelo
            # continuar a perceber de que tipo de dado se trata.
            tem_grupo = m.lastindex is not None
            original = m.group(1) if tem_grupo else m.group(0)
            prefixo = m.group(0)[: m.start(1) - m.start(0)] if tem_grupo else ""
            # Reutiliza o mesmo marcador para o mesmo valor
            for marcador, valor in mapa.items():
                if valor == original:
                    return prefixo + marcador
            contadores[etiqueta] = contadores.get(etiqueta, 0) + 1
            marcador = f"[{etiqueta}_{contadores[etiqueta]}]"
            mapa[marcador] = original
            return prefixo + marcador

        resultado = padrao.sub(_troca, resultado)

    return resultado, mapa


def repor(texto: str, mapa: dict[str, str]) -> str:
    """Repõe os valores originais no texto devolvido pelo modelo."""
    if not texto or not mapa:
        return texto
    for marcador, original in mapa.items():
        texto = texto.replace(marcador, original)
    return texto


def resumo(mapa: dict[str, str]) -> dict[str, int]:
    """Contagem por tipo, para registo de auditoria (sem os valores)."""
    contagem: dict[str, int] = {}
    for marcador in mapa:
        tipo = marcador.strip("[]").rsplit("_", 1)[0]
        contagem[tipo] = contagem.get(tipo, 0) + 1
    return contagem
