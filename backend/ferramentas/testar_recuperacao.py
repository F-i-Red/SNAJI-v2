# -*- coding: utf-8 -*-
"""
Mede a qualidade da recuperação de normas.

Para que serve: saber, de forma objectiva, se o motor encontra os artigos
que um jurista escolheria para cada caso — e comparar o modo só-BM25 com o
modo híbrido (BM25 + embeddings).

Como usar, a partir da pasta backend, com o ambiente virtual activo:

    python ferramentas/testar_recuperacao.py            # como está configurado
    python ferramentas/testar_recuperacao.py --sem-embeddings   # só BM25

Na primeira execução com embeddings o modelo é descarregado (~470 MB) e os
vectores do corpus são calculados (alguns minutos). Depois fica em cache e
o arranque passa a ser rápido.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if "--sem-embeddings" in sys.argv:
    import os
    os.environ["SNAJI_EMBEDDINGS"] = "0"

from app.rag.motor import RAGJuridico  # noqa: E402

# Casos de teste com os artigos que um jurista esperaria ver.
# Não é uma lista fechada de "certos" — é um alvo de referência.
CASOS = [
    {
        "nome": "Laboral — despedimento verbal de trabalhadora grávida",
        "texto": (
            "Trabalho há 6 anos como técnica de armazém numa empresa em Sintra, "
            "com contrato sem termo. Ontem o meu chefe disse-me apenas verbalmente "
            "que estou despedida a partir de amanhã, porque a empresa precisa de "
            "cortar custos. Não recebi nenhuma carta, nenhum processo disciplinar, "
            "nada por escrito. Estou grávida de 5 meses e a empresa sabe disso. "
            "Que direitos tenho? Que prazos tenho para reagir?"
        ),
        "esperados": ["CT-63", "CT-338", "CT-351", "CT-381", "CT-387", "CT-389", "CT-367"],
    },
    {
        "nome": "Arrendamento — aumento de renda de 40% e ameaça de despejo",
        "texto": (
            "Vivo num apartamento arrendado em Lisboa desde 2019, com contrato "
            "escrito. Pago 850 euros de renda. O senhorio enviou carta simples a "
            "dizer que a renda passa para 1190 euros, um aumento de 40% de uma só "
            "vez. Não indica fundamento legal nem o coeficiente anual de "
            "actualização. Diz que se não aceitar tenho de sair de casa no fim do "
            "mês. Tenho dois filhos menores."
        ),
        "esperados": ["CC-1077", "CC-1083", "CC-1069", "CC-1101", "CC-1110"],
    },
    {
        "nome": "Penal + civil — agressão com pedido de indemnização",
        "texto": (
            "Um vizinho empurrou-me contra o portão da garagem durante uma "
            "discussão sobre estacionamento. Caí, parti o pulso direito e os "
            "óculos. Estive 3 semanas de baixa, tive 240 euros de despesas médicas. "
            "Há duas testemunhas e as câmaras gravaram. Apresentei queixa na PSP. "
            "Que crime está em causa? Posso pedir indemnização no mesmo processo?"
        ),
        "esperados": ["CP-143", "CP-148", "CPP-71", "CPP-72", "CC-483"],
    },
    {
        "nome": "Consumo — reparação recusada dentro da garantia",
        "texto": (
            "Comprei uma máquina de lavar há 14 meses. Avariou-se e a loja diz que "
            "a garantia já não cobre e que tenho de pagar a reparação. Não me "
            "deram qualquer explicação por escrito. O que posso fazer?"
        ),
        "esperados": ["LDC-3", "LDC-4", "LDC-9", "CC-913", "CC-914"],
    },
]

K = 8


def main() -> None:
    rag = RAGJuridico()
    try:
        from app.rag.semantico import indice_semantico
        modo = "HÍBRIDO (BM25 + embeddings)" if indice_semantico.disponivel else "só BM25"
    except Exception:
        modo = "só BM25"

    print()
    print("=" * 74)
    print(f"  Qualidade da recuperação — modo: {modo}   (top-{K})")
    print("=" * 74)

    total_encontrados = 0
    total_esperados = 0

    for caso in CASOS:
        obtidos = [f"{c.diploma}-{c.artigo}" for c in rag.search(caso["texto"], top_k=K)]
        acertos = [e for e in caso["esperados"] if e in obtidos]
        total_encontrados += len(acertos)
        total_esperados += len(caso["esperados"])

        print()
        print(f"▸ {caso['nome']}")
        print(f"  recuperados : {', '.join(obtidos)}")
        print(f"  esperados   : {', '.join(caso['esperados'])}")
        print(f"  acertos     : {len(acertos)}/{len(caso['esperados'])}"
              f"  {'✓ ' + ', '.join(acertos) if acertos else '— nenhum'}")
        em_falta = [e for e in caso["esperados"] if e not in obtidos]
        if em_falta:
            print(f"  em falta    : {', '.join(em_falta)}")

    print()
    print("-" * 74)
    pct = (100.0 * total_encontrados / total_esperados) if total_esperados else 0.0
    print(f"  TOTAL: {total_encontrados}/{total_esperados} artigos de referência recuperados ({pct:.0f}%)")
    print("-" * 74)
    print()
    print("  Compare os dois modos para ver o efeito dos embeddings:")
    print("    python ferramentas/testar_recuperacao.py --sem-embeddings")
    print("    python ferramentas/testar_recuperacao.py")
    print()


if __name__ == "__main__":
    main()
