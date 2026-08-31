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
    # padrão genérico de telefone apanhava números de contribuinte iniciados
    # por 2, e o padrão de IBAN — tolerante a espaços — engolia datas.
    # [^\d]{0,20} permite quebras de linha entre a palavra-chave e o valor:
    # em texto colado de documentos, "nascida\nem 03/07/1988" é comum.
    ("NIF", re.compile(
        r"\b(?:nif|niss|contribuinte)[^\d]{0,20}(\d{9})\b", re.I)),
    ("NUM_UTENTE", re.compile(
        r"\butente[^\d]{0,20}(\d{9})\b", re.I)),
    ("DATA_NASCIMENTO", re.compile(
        r"\b(?:nasci|nascid[oa]|data\s+de\s+nascimento)[^\d]{0,20}"
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})\b", re.I)),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b")),
    ("IBAN", re.compile(r"\bPT50[\s-]?(?:\d[\s-]?){21}\b", re.I)),
    ("MATRICULA", re.compile(
        r"\b(?:[A-Z]{2}-\d{2}-[A-Z]{2}|\d{2}-[A-Z]{2}-\d{2}|[A-Z]{2}-\d{2}-\d{2})\b")),
    ("CODIGO_POSTAL", re.compile(r"\b\d{4}-\d{3}\b")),
    ("CARTAO_CIDADAO", re.compile(r"\b\d{8}\s?\d?\s?[A-Z]{2}\d\b")),
    ("TELEFONE", re.compile(
        r"(?<!\d)(?:\+351[\s-]?)?[92][1236]\d[\s-]?\d{3}[\s-]?\d{3}(?!\d)")),
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
