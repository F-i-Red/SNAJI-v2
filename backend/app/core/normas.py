"""
Preparação do texto das normas enviado ao modelo.

O texto de cada artigo era truncado a 150-300 caracteres, o que cortava a
esmagadora maioria dos artigos do corpus — frequentemente antes da alínea que
resolvia o caso. O modelo assinalava não poder citar com precisão, e a solidez
da análise descia por uma limitação que não era da lei nem dele.
"""
from __future__ import annotations

import os

try:
    MAX_CARACTERES_NORMA = int(os.getenv("SNAJI_MAX_CARACTERES_NORMA", "2500"))
except ValueError:
    MAX_CARACTERES_NORMA = 2500


def formatar_normas(chunks, com_epigrafe: bool = True) -> str:
    """Lista de normas em texto, para inserir no pedido ao modelo."""
    linhas = []
    for c in chunks:
        epi = getattr(c, "epigrase", "") if com_epigrafe else ""
        corpo = c.texto[:MAX_CARACTERES_NORMA]
        reticencias = " […]" if len(c.texto) > MAX_CARACTERES_NORMA else ""
        linhas.append(
            f"• Art. {c.artigo}.º {c.diploma} — "
            f"{(epi + ': ') if epi else ''}{corpo}{reticencias}"
        )
    return "\n".join(linhas) or "— sem normas recuperadas —"
