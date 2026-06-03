import re, json
from pathlib import Path
from dataclasses import dataclass

@dataclass
class Artigo:
    diploma: str
    codigo: str
    numero: str
    epigrase: str
    texto: str
    fonte: str
    def para_chunk(self):
        return {"diploma":self.codigo,"artigo":self.numero,
                "epigrase":self.epigrase,"texto":self.texto,"fonte":self.fonte}

DIPLOMAS = {
    "crp_raw.txt":     {"nome":"Constituição da República Portuguesa","codigo":"CRP", "fonte":"parlamento.pt/legislacao/documents/constpt2005.pdf"},
    "ct_raw.txt":      {"nome":"Código do Trabalho",                   "codigo":"CT",  "fonte":"pgdlisboa.pt (Lei n.º 7/2009)"},
    "cc_raw.txt":      {"nome":"Código Civil",                         "codigo":"CC",  "fonte":"pgdlisboa.pt (DL n.º 47344/66)"},
    "rgpd_raw.txt":    {"nome":"RGPD",                                 "codigo":"RGPD","fonte":"eur-lex.europa.eu (Reg. UE 2016/679)"},
    "cp_raw.txt":      {"nome":"Código Penal",                         "codigo":"CP",  "fonte":"pgdlisboa.pt (DL n.º 400/82)"},
    "cpc_cpp_raw.txt": {"nome":"Código de Processo Civil e Penal",     "codigo":"CPC", "fonte":"pgdlisboa.pt (Lei n.º 41/2013 + DL n.º 78/87)"},
}

PADRAO = re.compile(r"Artigo\s+(\d+[A-Z]?)\.º\s*\n(?:\(([^)]*)\)\s*\n)?", re.UNICODE)

def extrair(texto, codigo, fonte, nome):
    artigos, matches = [], list(PADRAO.finditer(texto))
    for i, m in enumerate(matches):
        numero, epigrase = m.group(1), (m.group(2) or "").strip()
        corpo = texto[m.end(): matches[i+1].start() if i+1<len(matches) else len(texto)].strip()
        corpo = re.sub(r"\n{3,}", "\n\n", corpo)
        if len(corpo) >= 10:
            artigos.append(Artigo(nome, codigo, numero, epigrase, corpo, fonte))
    return artigos

def construir():
    d = Path(__file__).parent
    todos = []
    for f, meta in DIPLOMAS.items():
        p = d/f
        if not p.exists(): print(f"[AVISO] {f} não encontrado"); continue
        arts = extrair(p.read_text(encoding="utf-8"), meta["codigo"], meta["fonte"], meta["nome"])
        print(f"[OK] {meta['codigo']:6s}: {len(arts):3d} artigos  ({f})")
        todos.extend(arts)
    saida = d/"corpus.json"
    saida.write_text(json.dumps([a.para_chunk() for a in todos], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[CORPUS] Total: {len(todos)} artigos  →  {saida}")
    return saida

if __name__ == "__main__":
    construir()
