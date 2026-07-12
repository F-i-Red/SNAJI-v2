# -*- coding: utf-8 -*-
"""
Atualizador de Acórdãos — SNAJI (ferramenta de administração)
==============================================================
Vai às páginas oficiais do Supremo Tribunal de Justiça (stj.pt), recolhe os
Acórdãos Uniformizadores de Jurisprudência (AUJ) publicados, extrai de cada um
o número, processo, data, sumário e normas citadas, valida as normas contra o
corpus legislativo, e funde tudo em `app/rag/corpus/acordaos.json` — sem
duplicar e sem apagar nada.

PRINCÍPIOS (os mesmos do SNAJI):
  - Só entra o que vem da fonte oficial, com URL de origem gravada.
  - As normas citadas são validadas contra o corpus — nunca se inventa.
  - Nada se apaga: os acórdãos existentes ficam; só se ADICIONA o que é novo.
  - Antes de gravar, faz-se backup automático do ficheiro anterior.

USO (no PC, a partir da pasta backend):
    py ferramentas/atualizador_acordaos.py            → atualiza tudo
    py ferramentas/atualizador_acordaos.py --simular  → só mostra o que faria

Depois de correr, reiniciar o backend para o motor carregar a base nova.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

# permitir importar o app/ quando corrido a partir de backend/
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
except ImportError:
    print("ERRO: falta o pacote 'requests'. Instalar com: pip install requests")
    sys.exit(1)

# ── Configuração ─────────────────────────────────────────────────────────────

FICHEIRO_ACORDAOS = Path(__file__).parent.parent / "app" / "rag" / "corpus" / "acordaos.json"

# Páginas de índice do STJ (as três áreas + a geral). O script também segue os
# links "ano" que encontrar nestas páginas (ex.: jurisprudencia-fixada-criminal-ano-2025).
PAGINAS_INDICE = [
    "https://www.stj.pt/uniformizacao-de-jurisprudencia/",
    "https://www.stj.pt/uniformizacao-de-jurisprudencia/civel/",
    "https://www.stj.pt/uniformizacao-de-jurisprudencia/criminais/",
    "https://www.stj.pt/uniformizacao-de-jurisprudencia/social/",
]

CABECALHOS = {"User-Agent": "SNAJI-Atualizador/1.0 (ferramenta de atualização de base juridica)"}
TEMPO_LIMITE = 30

# ── Extração de acórdãos do texto das páginas ────────────────────────────────

# Padrão principal: "Acórdão do Supremo Tribunal de Justiça n.º 5/2025 Processo 92/07..., de 19-02-2025 «sumário»"
# Variantes toleradas: "Acórdão nº 14/2024", aspas «» ou “”, processo/data opcionais.
_PADRAO_ACORDAO = re.compile(
    r"Ac[oó]rd[aã]o\s+(?:do\s+Supremo\s+Tribunal\s+de\s+Justi[çc]a\s+)?"
    r"n\.?[ºo°]\s*(\d+/\d{4})"                                   # 1: número (5/2025)
    r"(?:[\s,]*Proc(?:esso|\.)?(?:\s*n\.?[ºo°])?\s*([\w./\-]+))?"  # 2: processo (opcional)
    r"(?:,?\s*de\s+(\d{2}-\d{2}-\d{4}))?"                          # 3: data (opcional)
    r".{0,80}?"                                                     # relator/ruído até ao sumário
    r"[«“\"]\s*(.+?)\s*[»”\"]",                                    # 4: sumário entre aspas
    re.IGNORECASE | re.DOTALL,
)

# Links de páginas de ano (para seguir a partir dos índices)
_PADRAO_LINK_ANO = re.compile(
    r'href="(https://www\.stj\.pt/uniformizacao-de-jurisprudencia/'
    r'jurisprudencia-(?:fixada|uniformizada)-[a-z]+-ano-\d{4}/?)"'
)

# ── Extração de normas dos sumários (validadas contra o corpus) ──────────────

_DIPLOMAS_TXT = {
    "código do trabalho": "CT", "código civil": "CC", "código penal": "CP",
    "código de processo civil": "CPC", "código de processo penal": "CPP",
    "código de procedimento administrativo": "CPA",
    "código das sociedades comerciais": "CSC",
    "constituição": "CRP", "cire": "CIRE",
}
_PADRAO_NORMA_SUMARIO = re.compile(
    r"art(?:igo|\.)?[ºo°\.]*\s*(\d+)(?:\.[ºo°])?"
    r"(?:.{0,40}?)"
    r"(?:do|da)\s+(C[óo]digo\s+(?:do\s+Trabalho|Civil|Penal|de\s+Processo\s+Civil|"
    r"de\s+Processo\s+Penal|de\s+Procedimento\s+Administrativo|das\s+Sociedades\s+Comerciais)|"
    r"Constitui[çc][ãa]o|CIRE|CPP|CPC|CPA|CSC|CRP|CP|CC|CT)\b",
    re.IGNORECASE,
)


def _slug(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def _normalizar_diploma(raw: str) -> str:
    r = raw.strip().lower()
    for nome, sigla in _DIPLOMAS_TXT.items():
        if nome in r:
            return sigla
    return raw.strip().upper()


def extrair_normas(sumario: str, normas_validas: dict) -> tuple[list[str], list[str]]:
    """Extrai as normas do sumário e separa-as em validadas / não verificadas."""
    validas, nao_verificadas, vistos = [], [], set()
    for m in _PADRAO_NORMA_SUMARIO.finditer(sumario):
        artigo = m.group(1)
        diploma = _normalizar_diploma(m.group(2))
        chave = f"{diploma}-{artigo}"
        if chave in vistos:
            continue
        vistos.add(chave)
        if artigo in normas_validas.get(diploma, set()):
            validas.append(chave)
        else:
            nao_verificadas.append(chave)
    return validas, nao_verificadas


def extrair_acordaos_de_pagina(texto_html: str, url_origem: str,
                               normas_validas: dict) -> list[dict]:
    """Extrai todos os acórdãos reconhecíveis de uma página do STJ."""
    # limpar tags para o regex trabalhar sobre texto corrido
    texto = re.sub(r"<script.*?</script>", " ", texto_html, flags=re.DOTALL)
    texto = re.sub(r"<style.*?</style>", " ", texto, flags=re.DOTALL)
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = re.sub(r"\s+", " ", texto)

    area = ("criminal" if "criminal" in url_origem or "criminais" in url_origem
            else "social" if "social" in url_origem
            else "civel" if "civel" in url_origem else "geral")

    acordaos = []
    for m in _PADRAO_ACORDAO.finditer(texto):
        numero, processo, data, sumario = m.group(1), m.group(2), m.group(3), m.group(4)
        sumario = sumario.strip()
        # cortar sumários truncados pelo site ("[...]" no fim é aceitável; ruído longo não)
        if len(sumario) < 40:
            continue
        if len(sumario) > 1200:
            sumario = sumario[:1200] + "…"
        validas, nao_verif = extrair_normas(sumario, normas_validas)
        acordaos.append({
            "id": "stj-auj-" + _slug(numero),
            "tribunal": "STJ",
            "numero_processo": f"Acórdão STJ n.º {numero}",
            "processo": (processo or "").strip(" ,."),
            "data": data or numero.split("/")[-1],
            "relator": "",
            "sumario": sumario,
            "descritores": ["uniformização de jurisprudência", area],
            "normas_citadas": validas,
            "normas_nao_verificadas": nao_verif,
            "url": url_origem,
            "ecli": "",
            "tipo": "AUJ",
            "ficheiro_origem": f"atualizador ({datetime.now().date().isoformat()})",
        })
    return acordaos


# ── Recolha e fusão ──────────────────────────────────────────────────────────

def descarregar(url: str) -> str | None:
    try:
        r = requests.get(url, headers=CABECALHOS, timeout=TEMPO_LIMITE)
        if r.status_code == 200:
            return r.text
        print(f"  aviso: {url} devolveu {r.status_code}")
    except Exception as exc:
        print(f"  aviso: falha em {url}: {str(exc)[:80]}")
    return None


def main(simular: bool = False) -> None:
    print("═" * 64)
    print("Atualizador de Acórdãos — SNAJI")
    print("═" * 64)

    # 1) Carregar o corpus para validar normas (garante zero invenções)
    print("\n1. A carregar o corpus legislativo (validação de normas)…")
    from app.rag.motor import RAGJuridico, NORMAS_VALIDAS
    RAGJuridico()
    print(f"   corpus pronto: {sum(len(v) for v in NORMAS_VALIDAS.values())} normas válidas")

    # 2) Recolher as páginas de índice + páginas de ano descobertas
    print("\n2. A recolher as páginas do STJ…")
    paginas: dict[str, str] = {}
    for url in PAGINAS_INDICE:
        html = descarregar(url)
        if html:
            paginas[url] = html
            for link in set(_PADRAO_LINK_ANO.findall(html)):
                if link not in paginas:
                    sub = descarregar(link)
                    if sub:
                        paginas[link] = sub
    print(f"   {len(paginas)} páginas recolhidas")

    # 3) Extrair acórdãos de todas as páginas
    print("\n3. A extrair acórdãos…")
    candidatos: dict[str, dict] = {}
    for url, html in paginas.items():
        for ac in extrair_acordaos_de_pagina(html, url, NORMAS_VALIDAS):
            chave = ac["numero_processo"].upper().replace(" ", "")
            # preferir a versão com mais informação (sumário mais longo)
            if chave not in candidatos or len(ac["sumario"]) > len(candidatos[chave]["sumario"]):
                candidatos[chave] = ac
    print(f"   {len(candidatos)} acórdãos distintos encontrados nas páginas")

    # 4) Fundir com a base existente (sem duplicar, sem apagar)
    print("\n4. A fundir com a base existente…")
    atuais = json.loads(FICHEIRO_ACORDAOS.read_text(encoding="utf-8"))
    chaves_atuais = {a.get("numero_processo", "").upper().replace(" ", "").replace("ACÓRDÃO", "ACORDAO")
                     for a in atuais}

    novos = []
    for chave, ac in sorted(candidatos.items()):
        chave_n = chave.replace("ACÓRDÃO", "ACORDAO")
        if chave_n not in chaves_atuais:
            novos.append(ac)

    print(f"   base atual: {len(atuais)} · novos a adicionar: {len(novos)}")
    for ac in novos:
        normas = ", ".join(ac["normas_citadas"]) or "—"
        print(f"     + {ac['numero_processo']} ({ac['descritores'][1]}) · normas: {normas}")

    if simular:
        print("\n[SIMULAÇÃO] Nada foi gravado. Correr sem --simular para aplicar.")
        return

    if not novos:
        print("\nA base já está atualizada — nada a adicionar.")
        return

    # 5) Backup e gravação
    backup = FICHEIRO_ACORDAOS.with_name(
        f"acordaos_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    backup.write_text(json.dumps(atuais, ensure_ascii=False, indent=2), encoding="utf-8")
    atuais.extend(novos)
    FICHEIRO_ACORDAOS.write_text(
        json.dumps(atuais, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n5. Gravado: base passou a {len(atuais)} acórdãos "
          f"(backup do anterior em {backup.name})")
    print("\nReiniciar o backend para o motor carregar a base nova.")


if __name__ == "__main__":
    main(simular="--simular" in sys.argv)
