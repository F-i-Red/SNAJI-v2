"""
Processador do corpus legislativo — SNAJI (Especificação V8, §5.1)
===================================================================
Converte textos integrais de diplomas (ficheiros *_raw.txt) no corpus.json
que alimenta o motor RAG e o validador anti-alucinação.

Compatível com os formatos reais das fontes oficiais:
  - Diário da República consolidado:  "Artigo 483.º" + epígrafe em linha própria
  - PGD Lisboa:                        "ARTIGO 483º"  + "(Epígrafe)" entre parênteses
  - Números compostos:                 "Artigo 10.º-A", "Artigo 347º-B"
  - Artigos revogados:                 corpo "(Revogado)" → marcados, não excluídos

Mantém o contrato de dados do motor RAG (diploma, artigo, epigrase, texto,
fonte) e acrescenta campos novos: revogado, contexto (Livro/Título/Capítulo/
Secção), versao e data_processamento.

Uso:
    cd backend
    python app/rag/corpus/processador.py
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

# ── Registo dos diplomas (Escalão 1 da Especificação V8) ────────────────────
# Para acrescentar um diploma: 1) guardar o texto integral como <chave>_raw.txt
# nesta pasta; 2) acrescentar uma linha a este dicionário. Nada mais.

DIPLOMAS: dict[str, dict] = {
    "crp_raw.txt":  {"nome": "Constituição da República Portuguesa", "codigo": "CRP",
                     "fonte": "diariodarepublica.pt (versão consolidada)"},
    "cc_raw.txt":   {"nome": "Código Civil", "codigo": "CC",
                     "fonte": "diariodarepublica.pt (DL n.º 47344/66, consolidado)"},
    "cpc_raw.txt":  {"nome": "Código de Processo Civil", "codigo": "CPC",
                     "fonte": "diariodarepublica.pt (Lei n.º 41/2013, consolidado)"},
    "cp_raw.txt":   {"nome": "Código Penal", "codigo": "CP",
                     "fonte": "diariodarepublica.pt (DL n.º 400/82, consolidado)"},
    "cpp_raw.txt":  {"nome": "Código de Processo Penal", "codigo": "CPP",
                     "fonte": "diariodarepublica.pt (DL n.º 78/87, consolidado)"},
    "ct_raw.txt":   {"nome": "Código do Trabalho", "codigo": "CT",
                     "fonte": "diariodarepublica.pt (Lei n.º 7/2009, consolidado)"},
    "cpa_raw.txt":  {"nome": "Código do Procedimento Administrativo", "codigo": "CPA",
                     "fonte": "diariodarepublica.pt (DL n.º 4/2015, consolidado)"},
    "cire_raw.txt": {"nome": "Código da Insolvência e da Recuperação de Empresas",
                     "codigo": "CIRE",
                     "fonte": "diariodarepublica.pt (DL n.º 53/2004, consolidado)"},
    "csc_raw.txt":  {"nome": "Código das Sociedades Comerciais", "codigo": "CSC",
                     "fonte": "diariodarepublica.pt (DL n.º 262/86, consolidado)"},
    "rgpd_raw.txt": {"nome": "RGPD", "codigo": "RGPD",
                     "fonte": "eur-lex.europa.eu (Reg. UE 2016/679)"},
    "ldc_raw.txt":  {"nome": "Lei de Defesa do Consumidor", "codigo": "LDC",
                     "fonte": "diariodarepublica.pt (Lei n.º 24/96, consolidado)"},
    "ljp_raw.txt":  {"nome": "Lei dos Julgados de Paz", "codigo": "LJP",
                     "fonte": "diariodarepublica.pt (Lei n.º 78/2001, consolidado)"},
    # Compatibilidade com o corpus antigo (ficheiro conjunto CPC+CPP):
    "cpc_cpp_raw.txt": {"nome": "Código de Processo Civil e Penal", "codigo": "CPC",
                        "fonte": "pgdlisboa.pt (Lei n.º 41/2013 + DL n.º 78/87)"},
}

# ── Padrões ──────────────────────────────────────────────────────────────────

# Cabeçalho de artigo: "Artigo 483.º", "ARTIGO 483º", "Artigo 10.º-A", "Art. 5.º"
PADRAO_ARTIGO = re.compile(
    r"^[ \t]*(?:Artigo|ARTIGO|Art\.)[ \t]+(\d+)[.\s]*[ºo°](?:[ \t]*-[ \t]*([A-Z]))?[ \t]*$",
    re.MULTILINE,
)

# Cabeçalhos estruturais (contexto): LIVRO I, TÍTULO II, CAPÍTULO III, SECÇÃO I…
PADRAO_ESTRUTURA = re.compile(
    r"^[ \t]*(LIVRO|PARTE|TÍTULO|TITULO|CAPÍTULO|CAPITULO|SECÇÃO|SECCAO|SUBSECÇÃO|SUBSECCAO|ANEXO)"
    r"[ \t]+([IVXLCDM\d]+)[ \t]*$",
    re.MULTILINE | re.IGNORECASE,
)

# Linhas de ruído das fontes (avisos de alterações, navegação, etc.)
PADRAO_RUIDO = re.compile(
    r"^[ \t]*(Contém as seguintes alterações|Ver as alterações|Versão à data|"
    r"\[?\s*voltar ao início|Página \d+|_{5,}|-{5,}|={5,})",
    re.IGNORECASE,
)

PADRAO_REVOGADO = re.compile(r"^\(?\s*revogad[oa]", re.IGNORECASE)


@dataclass
class Artigo:
    diploma: str          # nome por extenso
    codigo: str           # sigla (CC, CP, …)
    numero: str           # "483" ou "10-A"
    epigrase: str         # epígrafe (mantida a grafia histórica do projeto)
    texto: str
    fonte: str
    revogado: bool = False
    contexto: str = ""    # "LIVRO II › TÍTULO I › CAPÍTULO II"
    versao: str = ""      # preenchível quando houver versionamento temporal
    data_processamento: str = field(default_factory=lambda: date.today().isoformat())

    def para_chunk(self) -> dict:
        return {
            # Contrato original do motor RAG (não alterar as chaves):
            "diploma": self.codigo,
            "artigo": self.numero,
            "epigrase": self.epigrase,
            "texto": self.texto,
            "fonte": self.fonte,
            # Campos novos (o motor ignora-os sem problemas):
            "diploma_nome": self.diploma,
            "revogado": self.revogado,
            "contexto": self.contexto,
            "versao": self.versao,
            "data_processamento": self.data_processamento,
        }


def _limpar(texto: str) -> str:
    linhas = [ln for ln in texto.splitlines() if not PADRAO_RUIDO.match(ln)]
    limpo = "\n".join(linhas)
    return re.sub(r"\n{3,}", "\n\n", limpo)


def _extrair_epigrafe(corpo: str) -> tuple[str, str]:
    """
    A epígrafe é a primeira linha não vazia do corpo, se parecer um título:
      - entre parênteses (formato PGDL), ou
      - linha curta sem pontuação final de frase nem numeração de preceito
        (formato DRE consolidado).
    Devolve (epigrafe, corpo_sem_epigrafe).
    """
    linhas = corpo.split("\n")
    i = 0
    while i < len(linhas) and not linhas[i].strip():
        i += 1
    if i >= len(linhas):
        return "", corpo

    cand = linhas[i].strip()

    # Formato com parênteses
    m = re.match(r"^\((.{2,150})\)$", cand)
    if m:
        return m.group(1).strip(), "\n".join(linhas[i + 1:]).strip()

    # Formato DRE: linha curta, sem começar por numeração de preceito
    comeca_preceito = re.match(r"^(\d+\s*[-.)–]|[a-z]\)|§)", cand)
    parece_estrutura = PADRAO_ESTRUTURA.match(cand)
    if (
        len(cand) <= 120
        and not comeca_preceito
        and not parece_estrutura
        and not cand.endswith((".", ";", ":"))
        and not cand.lower().startswith(("artigo", "art."))
    ):
        return cand, "\n".join(linhas[i + 1:]).strip()

    return "", corpo


def extrair(texto: str, codigo: str, fonte: str, nome: str) -> list[Artigo]:
    texto = _limpar(texto)

    # Índice de contexto estrutural por posição
    estruturas = [(m.start(), f"{m.group(1).upper()} {m.group(2).upper()}")
                  for m in PADRAO_ESTRUTURA.finditer(texto)]

    def contexto_em(pos: int) -> str:
        pilha: dict[str, str] = {}
        for p, rotulo in estruturas:
            if p > pos:
                break
            nivel = rotulo.split()[0]
            # Um nível novo limpa os níveis inferiores
            ordem = ["PARTE", "LIVRO", "TÍTULO", "TITULO", "CAPÍTULO",
                     "CAPITULO", "SECÇÃO", "SECCAO", "SUBSECÇÃO", "SUBSECCAO"]
            if nivel in ordem:
                idx = ordem.index(nivel)
                for n in ordem[idx + 1:]:
                    pilha.pop(n, None)
            pilha[nivel] = rotulo
        return " › ".join(pilha.values())

    artigos: list[Artigo] = []
    matches = list(PADRAO_ARTIGO.finditer(texto))

    for i, m in enumerate(matches):
        numero = m.group(1) + (f"-{m.group(2)}" if m.group(2) else "")
        fim = matches[i + 1].start() if i + 1 < len(matches) else len(texto)
        corpo = texto[m.end():fim].strip()

        epigrase, corpo = _extrair_epigrafe(corpo)
        revogado = bool(PADRAO_REVOGADO.match(corpo)) if corpo else True
        if epigrase and PADRAO_REVOGADO.match(epigrase):
            revogado, corpo, epigrase = True, "(Revogado)", ""

        if len(corpo) < 3 and not revogado:
            continue

        artigos.append(Artigo(
            diploma=nome, codigo=codigo, numero=numero,
            epigrase=epigrase, texto=corpo, fonte=fonte,
            revogado=revogado, contexto=contexto_em(m.start()),
        ))
    return artigos


def _relatorio(codigo: str, artigos: list[Artigo], ficheiro: str) -> None:
    revogados = sum(1 for a in artigos if a.revogado)
    com_epigrafe = sum(1 for a in artigos if a.epigrase)
    numeros = []
    for a in artigos:
        base = a.numero.split("-")[0]
        if base.isdigit():
            numeros.append(int(base))
    aviso = ""
    if numeros:
        esperado = max(numeros)
        base_unicos = len(set(numeros))
        if base_unicos < esperado * 0.9:
            aviso = f"  [VERIFICAR: numeração vai até {esperado} mas só há {base_unicos} números-base — possíveis artigos não extraídos]"
    print(f"[OK] {codigo:5s}: {len(artigos):5d} artigos "
          f"({com_epigrafe} c/ epígrafe, {revogados} revogados)  ({ficheiro}){aviso}")

    duplicados = len(artigos) - len({a.numero for a in artigos})
    if duplicados:
        print(f"     [VERIFICAR: {duplicados} números de artigo duplicados em {codigo}]")


def construir() -> Path:
    d = Path(__file__).parent
    todos: list[Artigo] = []
    encontrados = 0

    for ficheiro, meta in DIPLOMAS.items():
        p = d / ficheiro
        if not p.exists():
            continue
        encontrados += 1
        arts = extrair(p.read_text(encoding="utf-8", errors="replace"),
                       meta["codigo"], meta["fonte"], meta["nome"])
        _relatorio(meta["codigo"], arts, ficheiro)
        todos.extend(arts)

    # Ficheiros *_raw.txt não registados
    for p in sorted(d.glob("*_raw.txt")):
        if p.name not in DIPLOMAS:
            print(f"[AVISO] {p.name} existe mas não está registado em DIPLOMAS — ignorado. "
                  f"Acrescenta uma linha ao dicionário DIPLOMAS para o incluir.")

    if encontrados == 0:
        print("[ERRO] Nenhum ficheiro *_raw.txt registado foi encontrado nesta pasta.")
        sys.exit(1)

    saida = d / "corpus.json"
    saida.write_text(
        json.dumps([a.para_chunk() for a in todos], ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    ativos = sum(1 for a in todos if not a.revogado)
    print(f"\n[CORPUS] Total: {len(todos)} artigos ({ativos} em vigor, "
          f"{len(todos) - ativos} revogados)  →  {saida}")
    print(f"[CORPUS] Tamanho: {saida.stat().st_size / 1_048_576:.1f} MB")
    return saida


if __name__ == "__main__":
    construir()
