"""
Processador de Acórdãos (dgsi.pt) — SNAJI (Especificação V8, §5.2)
===================================================================
Converte páginas de acórdãos do dgsi.pt (coladas em ficheiros .txt na pasta
`acordaos_raw/`) no ficheiro `acordaos.json` que alimenta o motor de
jurisprudência.

FONTE: www.dgsi.pt — bases jurídico-documentais dos tribunais superiores.
Prioridade (Especificação V8): Acórdãos Uniformizadores de Jurisprudência
(AUJ) do STJ e acórdãos de fixação de jurisprudência penal.

O QUE O PROCESSADOR EXTRAI de cada página colada:
  - tribunal (STJ, TRL, TRP, TRC, TRE, TRG, TC — inferido do cabeçalho)
  - número de processo, relator, data, votação
  - descritores (palavras-chave do próprio dgsi)
  - sumário (integral) e excerto do texto da decisão
  - ECLI, quando presente
  - normas citadas no sumário — VALIDADAS contra o corpus legislativo
    (só entram em `normas_citadas` as que existem no corpus.json;
     as restantes ficam em `normas_nao_verificadas`)
  - classificação AUJ automática (uniformização/fixação de jurisprudência)

USO:
    1) Colar cada acórdão do dgsi num .txt dentro de:
         backend/app/rag/corpus/acordaos_raw/
    2) cd backend
    3) py app/rag/corpus/processador_acordaos.py

Saída: backend/app/rag/corpus/acordaos.json
(o MotorJurisprudencia carrega-o automaticamente no arranque seguinte)
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

# ── Diplomas reconhecidos nas citações (nome por extenso → sigla) ───────────

DIPLOMAS_POR_NOME: dict[str, str] = {
    "código civil": "CC",
    "código de processo civil": "CPC",
    "código penal": "CP",
    "código de processo penal": "CPP",
    "código do trabalho": "CT",
    "código do procedimento administrativo": "CPA",
    "código da insolvência": "CIRE",
    "código das sociedades comerciais": "CSC",
    "constituição da república portuguesa": "CRP",
    "constituição": "CRP",
    "lei de defesa do consumidor": "LDC",
}
SIGLAS = {"CC", "CPC", "CP", "CPP", "CT", "CPA", "CIRE", "CSC", "CRP", "RGPD", "LDC", "LJP"}

TRIBUNAIS = [
    ("supremo tribunal de justiça", "STJ"),
    ("tribunal constitucional", "TC"),
    ("relação de lisboa", "TRL"),
    ("relação do porto", "TRP"),
    ("relação de coimbra", "TRC"),
    ("relação de évora", "TRE"),
    ("relação de guimarães", "TRG"),
    ("supremo tribunal administrativo", "STA"),
]

_CAMPOS = [
    "Processo", "Nº Convencional", "N.º Convencional", "Relator", "Descritores",
    "Data do Acordão", "Data do Acórdão", "Votação", "Texto Integral",
    "Meio Processual", "Decisão", "Sumário", "Decisão Texto Integral",
    "Área Temática", "Legislação Nacional", "Jurisprudência Nacional",
    "Referência de Publicação", "Privacidade", "Indicações Eventuais",
]
_PADRAO_CAMPO = re.compile(
    r"^[ \t]*(" + "|".join(re.escape(c) for c in _CAMPOS) + r")[ \t]*:",
    re.MULTILINE,
)


def _extrair_campos(texto: str) -> dict[str, str]:
    """Divide a página do dgsi nos seus campos rotulados."""
    campos: dict[str, str] = {}
    matches = list(_PADRAO_CAMPO.finditer(texto))
    for i, m in enumerate(matches):
        nome = m.group(1).replace("N.º", "Nº").replace("Acórdão", "Acordão")
        fim = matches[i + 1].start() if i + 1 < len(matches) else len(texto)
        valor = texto[m.end():fim].strip().strip("\t ").strip()
        # guarda o primeiro valor de cada campo (o dgsi não repete)
        campos.setdefault(nome, valor)
    return campos


def _detectar_tribunal(texto: str) -> str:
    t = texto.lower()
    for nome, sigla in TRIBUNAIS:
        if nome in t:
            return sigla
    return "STJ"  # por omissão (as AUJ são do STJ)


def _detectar_ecli(texto: str) -> str:
    m = re.search(r"ECLI:PT:[A-Z0-9:.\-]+", texto)
    return m.group() if m else ""


def _e_auj(texto: str, campos: dict[str, str]) -> bool:
    t = (texto[:4000] + " " + campos.get("Meio Processual", "") + " "
         + campos.get("Nº Convencional", "")).lower()
    return ("uniformiza" in t) or ("fixação de jurisprudência" in t) or ("fixacao de jurisprudencia" in t)


def _extrair_normas(texto: str) -> list[str]:
    """
    Extrai citações de normas: 'art. 483.º do CC', 'artigo 351.º do Código
    do Trabalho', 'art. 71.º, n.º 1, do CPP', etc.
    """
    normas: set[str] = set()
    padrao = re.compile(
        r"art(?:igo)?s?\.?\s*(\d+)\.?[ºo°]?(?:\s*-\s*([A-Z]))?"
        r"[^;\n]{0,60}?"
        r"(?:d[oa]s?\s+)((?:C[óo]digo|Constitui[çc][ãa]o|Lei de Defesa)[^,.;)\n]{0,45}|[A-Z]{2,5})",
        re.IGNORECASE,
    )
    for m in padrao.finditer(texto):
        numero = m.group(1) + (f"-{m.group(2)}" if m.group(2) else "")
        ref = m.group(3).strip()
        sigla = ""
        if ref.upper() in SIGLAS:
            sigla = ref.upper()
        else:
            ref_l = ref.lower()
            for nome, s in DIPLOMAS_POR_NOME.items():
                if ref_l.startswith(nome[:20]):
                    sigla = s
                    break
        if sigla:
            normas.add(f"{sigla}-{numero}")
    return sorted(normas)


def _carregar_normas_validas(pasta: Path) -> set[str]:
    corpus = pasta / "corpus.json"
    if not corpus.exists():
        return set()
    dados = json.loads(corpus.read_text(encoding="utf-8"))
    return {f"{a['diploma']}-{a['artigo']}" for a in dados}


def _slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return t[:60] or "acordao"


def processar_acordao(texto: str, nome_ficheiro: str, normas_validas: set[str]) -> dict:
    campos = _extrair_campos(texto)
    tribunal = _detectar_tribunal(texto)

    def _primeira_linha(campo: str) -> str:
        linhas = campos.get(campo, "").splitlines()
        return linhas[0].strip() if linhas else ""

    processo = _primeira_linha("Processo") or nome_ficheiro
    relator = _primeira_linha("Relator").title()
    data_raw = _primeira_linha("Data do Acordão")
    m = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", data_raw)
    data = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else data_raw

    descritores = [
        d.strip().lower()
        for d in re.split(r"[\n;]", campos.get("Descritores", ""))
        if 2 < len(d.strip()) < 80
    ][:12]

    sumario = campos.get("Sumário", "").strip()
    decisao = campos.get("Decisão Texto Integral", "").strip()
    if not sumario and decisao:
        sumario = decisao[:1500]

    auj = _e_auj(texto, campos)
    todas = _extrair_normas(sumario + "\n" + campos.get("Legislação Nacional", ""))
    citadas = [n for n in todas if n in normas_validas] if normas_validas else todas
    nao_verificadas = [n for n in todas if n not in citadas]

    m_url = re.search(r"https?://www\.dgsi\.pt/\S+", texto)

    return {
        "id": f"{tribunal.lower()}-{_slug(processo)}",
        "tribunal": tribunal,
        "numero_processo": processo,
        "data": data,
        "relator": relator,
        "sumario": sumario,
        "descritores": descritores,
        "normas_citadas": citadas,
        "normas_nao_verificadas": nao_verificadas,
        "url": m_url.group() if m_url else "http://www.dgsi.pt",
        "ecli": _detectar_ecli(texto),
        "tipo": "AUJ" if auj else "acordao",
        "ficheiro_origem": nome_ficheiro,
    }


def construir() -> Path:
    pasta = Path(__file__).parent
    pasta_raw = pasta / "acordaos_raw"
    pasta_raw.mkdir(exist_ok=True)

    ficheiros = sorted(pasta_raw.glob("*.txt"))
    if not ficheiros:
        print(f"[AVISO] Sem ficheiros em {pasta_raw}.")
        print("        Cola cada acórdão do dgsi.pt num .txt dentro dessa pasta e volta a correr.")
        return pasta / "acordaos.json"

    normas_validas = _carregar_normas_validas(pasta)
    acordaos: list[dict] = []
    vistos: set[str] = set()

    for f in ficheiros:
        texto = f.read_text(encoding="utf-8", errors="replace")
        a = processar_acordao(texto, f.name, normas_validas)

        problemas = []
        if not a["sumario"]:
            problemas.append("sem sumário")
        if not a["data"]:
            problemas.append("sem data")
        if a["numero_processo"] == f.name:
            problemas.append("sem n.º de processo")
        if a["id"] in vistos:
            print(f"[IGNORADO] {f.name}: duplicado de {a['id']}")
            continue
        vistos.add(a["id"])
        acordaos.append(a)

        marca = "AUJ ★" if a["tipo"] == "AUJ" else "    "
        aviso = f"  [VERIFICAR: {', '.join(problemas)}]" if problemas else ""
        extra = (f" | normas não verificadas: {len(a['normas_nao_verificadas'])}"
                 if a["normas_nao_verificadas"] else "")
        print(f"[OK] {marca} {a['tribunal']:4s} {a['numero_processo'][:28]:28s} "
              f"{a['data']:10s} normas: {len(a['normas_citadas'])}{extra}{aviso}")

    saida = pasta / "acordaos.json"
    saida.write_text(json.dumps(acordaos, ensure_ascii=False, indent=1), encoding="utf-8")
    aujs = sum(1 for a in acordaos if a["tipo"] == "AUJ")
    print(f"\n[JURISPRUDÊNCIA] {len(acordaos)} acórdãos ({aujs} AUJ) → {saida}")
    print("[JURISPRUDÊNCIA] O motor carrega este ficheiro no próximo arranque do servidor.")
    return saida


if __name__ == "__main__":
    construir()
