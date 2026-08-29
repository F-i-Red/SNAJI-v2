# -*- coding: utf-8 -*-
"""
Afinação da recuperação híbrida.

Percorre vários pesos de fusão entre BM25 (palavras) e embeddings
(significado) e mostra qual dá melhores resultados nos casos de referência.
Os vectores já estão em cache, por isso a varredura é rápida.

Uso (pasta backend, ambiente virtual activo):

    python ferramentas/afinar_recuperacao.py

Depois, escreve o melhor valor no .env:

    SNAJI_PESO_BM25=0.6
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rag.motor import RAGJuridico, _normalizar  # noqa: E402
from ferramentas.testar_recuperacao import CASOS, K  # noqa: E402

PESOS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
K_RRF = 60.0


def posicoes(valores: np.ndarray) -> np.ndarray:
    p = np.empty(len(valores), dtype=np.int32)
    p[np.argsort(-valores, kind="stable")] = np.arange(len(valores))
    return p


def main() -> None:
    rag = RAGJuridico()
    try:
        from app.rag.semantico import indice_semantico
        if not indice_semantico.disponivel:
            print("\n  Embeddings indisponíveis — nada para afinar.")
            print("  Confirme SNAJI_EMBEDDINGS=1 no .env e volte a correr.\n")
            return
    except Exception:
        print("\n  Embeddings indisponíveis — nada para afinar.\n")
        return

    # Pré-calcula os dois sinais por caso (a parte cara faz-se uma só vez).
    # A pergunta passa primeiro pela reescrita jurídica, para a afinação
    # ser feita sobre o mesmo texto que o sistema usa em produção.
    try:
        from app.rag.reescrita import reescrever
    except Exception:
        def reescrever(t, llm=None):  # type: ignore
            return t

    sinais = []
    for caso in CASOS:
        texto = reescrever(caso["texto"])
        bm = rag._bm25.get_scores(_normalizar(texto, expandir=True))
        sem = indice_semantico.similaridades(texto)
        sinais.append((posicoes(bm), posicoes(sem), set(caso["esperados"])))

    total_esperados = sum(len(c["esperados"]) for c in CASOS)

    print()
    print("=" * 68)
    print("  Afinação do peso da fusão híbrida")
    print(f"  (0.0 = só embeddings · 1.0 = só BM25) · top-{K}")
    print("=" * 68)
    print()

    melhor = (None, -1)
    for peso in PESOS:
        acertos_total = 0
        por_caso = []
        for pos_bm, pos_sem, esperados in sinais:
            fundido = peso / (K_RRF + pos_bm + 1) + (1 - peso) / (K_RRF + pos_sem + 1)
            topo = np.argsort(-fundido, kind="stable")[:K]
            obtidos = {
                f"{rag._chunks[i]['diploma']}-{rag._chunks[i]['artigo']}" for i in topo
            }
            n = len(esperados & obtidos)
            acertos_total += n
            por_caso.append(f"{n}/{len(esperados)}")
        pct = 100.0 * acertos_total / total_esperados
        barra = "█" * int(pct / 3)
        print(f"  peso {peso:.1f}  {acertos_total:2}/{total_esperados} ({pct:3.0f}%)  "
              f"[{'  '.join(por_caso)}]  {barra}")
        if acertos_total > melhor[1]:
            melhor = (peso, acertos_total)

    print()
    print("-" * 68)
    print(f"  MELHOR: peso {melhor[0]:.1f} com {melhor[1]}/{total_esperados} "
          f"({100.0 * melhor[1] / total_esperados:.0f}%)")
    print(f"  Escreva no .env:  SNAJI_PESO_BM25={melhor[0]:.1f}")
    print("-" * 68)
    print()
    print("  Ordem dos casos: laboral · arrendamento · penal · consumo")
    print()
    print("  Se o melhor resultado continuar baixo, experimente um modelo")
    print("  maior no .env (implica novo descarregamento e recálculo):")
    print("    SNAJI_MODELO_EMBEDDING=intfloat/multilingual-e5-base")
    print()


if __name__ == "__main__":
    main()
