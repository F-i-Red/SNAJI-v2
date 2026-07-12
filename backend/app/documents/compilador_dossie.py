"""
Compilador de Dossiê — SNAJI
=============================
A peça mais ambiciosa: recebe vários documentos de um processo — a petição do
autor, a contestação do réu, a acusação, a sentença, requerimentos — e organiza
tudo num DOSSIÊ COERENTE:

  1. Identifica o PAPEL de cada documento (quem fala: autor/acusação, réu/defesa,
     tribunal) a partir do tipo de peça detetado.
  2. ORDENA os documentos pela marcha processual real (petição antes de
     contestação; acusação antes de defesa; sentença no fim).
  3. Consolida as CITAÇÕES de todos os documentos, distinguindo válidas de
     inexistentes (reaproveita o verificador de peças).
  4. Constrói uma CRONOLOGIA e um mapa de posições (o que cada parte alega),
     para o profissional ver o caso inteiro de relance.

Determinístico: não depende de LLM. Com LLM, um resumo executivo do confronto
de posições pode ser acrescentado, mas a organização — o mais valioso — é
sempre feita contra regras claras.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from app.documents.analisador_pecas import AnalisadorPecas, AnalisePeca

logger = structlog.get_logger(__name__)


# Cada tipo de peça → papel processual e ordem na marcha do processo
# (ordem menor = mais cedo no processo)
_TIPO_PARA_PAPEL = {
    "Petição inicial":        ("Autor / Requerente", 1),
    "Acusação":               ("Acusação / Ministério Público", 1),
    "Contestação":            ("Réu / Defesa", 2),
    "Requerimento":           ("Parte (requerimento)", 3),
    "Recurso / Alegações":    ("Recorrente", 4),
    "Sentença / Decisão":     ("Tribunal", 5),
    "Peça processual (tipo não determinado)": ("Indeterminado", 6),
}


@dataclass
class DocumentoNoDossie:
    nome_ficheiro: str
    tipo: str
    papel: str
    ordem: int
    num_paginas: int
    resumo: str
    citacoes_validas: list[str] = field(default_factory=list)
    citacoes_invalidas: list[str] = field(default_factory=list)
    prazos: list[str] = field(default_factory=list)


@dataclass
class Dossie:
    documentos: list[DocumentoNoDossie] = field(default_factory=list)
    total_paginas: int = 0
    todas_citacoes_validas: list[str] = field(default_factory=list)
    todas_citacoes_invalidas: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    def para_dict(self) -> dict:
        return {
            "num_documentos": len(self.documentos),
            "total_paginas": self.total_paginas,
            "documentos": [
                {
                    "nome_ficheiro": d.nome_ficheiro,
                    "tipo": d.tipo,
                    "papel": d.papel,
                    "ordem": d.ordem,
                    "num_paginas": d.num_paginas,
                    "resumo": d.resumo,
                    "citacoes_validas": d.citacoes_validas,
                    "citacoes_invalidas": d.citacoes_invalidas,
                    "prazos": d.prazos,
                }
                for d in self.documentos
            ],
            "citacoes_validas_unicas": sorted(set(self.todas_citacoes_validas)),
            "citacoes_invalidas_unicas": sorted(set(self.todas_citacoes_invalidas)),
            "total_citacoes_invalidas": len(set(self.todas_citacoes_invalidas)),
            "avisos": self.avisos,
        }


class CompiladorDossie:
    """Organiza vários documentos de um processo num dossiê coerente."""

    def __init__(self, llm_client=None):
        self._analisador = AnalisadorPecas(llm_client=llm_client)

    def compilar(self, documentos: list[tuple[str, str, int]]) -> Dossie:
        """
        documentos: lista de (nome_ficheiro, texto, num_paginas).
        Devolve o dossiê organizado.
        """
        dossie = Dossie()
        if not documentos:
            dossie.avisos.append("Nenhum documento recebido.")
            return dossie

        for nome, texto, paginas in documentos:
            if not (texto or "").strip():
                dossie.avisos.append(f"{nome}: sem texto legível (ignorado na organização).")
                continue
            analise: AnalisePeca = self._analisador.analisar(texto, nome, paginas)
            papel, ordem = _TIPO_PARA_PAPEL.get(
                analise.tipo_provavel, ("Indeterminado", 6)
            )
            validas = [f"{c.diploma}-{c.artigo}" for c in analise.citacoes_validas]
            invalidas = [f"{c.diploma}-{c.artigo}" for c in analise.citacoes_invalidas]
            dossie.documentos.append(DocumentoNoDossie(
                nome_ficheiro=nome,
                tipo=analise.tipo_provavel,
                papel=papel,
                ordem=ordem,
                num_paginas=paginas,
                resumo=analise.resumo,
                citacoes_validas=validas,
                citacoes_invalidas=invalidas,
                prazos=analise.prazos_desencadeados,
            ))
            dossie.total_paginas += paginas
            dossie.todas_citacoes_validas.extend(validas)
            dossie.todas_citacoes_invalidas.extend(invalidas)

        # Ordenar pela marcha processual (ordem), mantendo estável por nome
        dossie.documentos.sort(key=lambda d: (d.ordem, d.nome_ficheiro))

        if dossie.todas_citacoes_invalidas:
            dossie.avisos.append(
                f"{len(set(dossie.todas_citacoes_invalidas))} citação(ões) do dossiê "
                "não consta(m) do corpus — verificar."
            )
        # Sinalizar peças com papel indeterminado (o profissional confirma)
        indets = [d.nome_ficheiro for d in dossie.documentos if d.papel == "Indeterminado"]
        if indets:
            dossie.avisos.append(
                "Documento(s) sem tipo processual claro (confirmar o papel): "
                + ", ".join(indets)
            )

        logger.info("dossie.compilado", docs=len(dossie.documentos),
                    paginas=dossie.total_paginas)
        return dossie
