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

K = 20


def main() -> None:
    rag = RAGJuridico()
    try:
        from app.rag.semantico import indice_semantico
        tem_semantico = indice_semantico.disponivel
    except Exception:
        tem_semantico = False

    print()
    print("=" * 78)
    print(f"  Diagnóstico da recuperação de normas   (top-{K})")
    print(f"  Embeddings: {'disponíveis' if tem_semantico else 'INDISPONÍVEIS — só BM25'}")
    print("=" * 78)
    print("  Cada caso é testado com os três motores, para se ver qual falha:")
    print("    BM25      → correspondência de palavras")
    print("    SEMÂNTICO → correspondência de significado (embeddings)")
    print("    HÍBRIDO   → fusão dos dois (é o que o SNAJI usa)")

    totais = {"BM25": 0, "SEMÂNTICO": 0, "HÍBRIDO": 0}
    total_esperados = 0

    for caso in CASOS:
        esperados = caso["esperados"]
        total_esperados += len(esperados)
        print()
        print(f"▸ {caso['nome']}")
        print(f"  esperados : {', '.join(esperados)}")

        motores = [
            ("BM25", rag.search_bm25(caso["texto"], top_k=K)),
            ("SEMÂNTICO", rag.search_semantico(caso["texto"], top_k=K)),
            ("HÍBRIDO", rag.search(caso["texto"], top_k=K)),
        ]
        for nome, res in motores:
            if res is None:
                print(f"  {nome:10}: (indisponível)")
                continue
            obtidos = [f"{c.diploma}-{c.artigo}" for c in res]
            acertos = [e for e in esperados if e in obtidos]
            totais[nome] += len(acertos)
            marca = "✓" if acertos else " "
            print(f"  {nome:10}: {len(acertos)}/{len(esperados)} {marca}  {', '.join(obtidos)}")

    print()
    print("-" * 78)
    for nome in ("BM25", "SEMÂNTICO", "HÍBRIDO"):
        n = totais[nome]
        pct = (100.0 * n / total_esperados) if total_esperados else 0.0
        print(f"  {nome:10}: {n:2}/{total_esperados} artigos de referência ({pct:.0f}%)")
    print("-" * 78)
    print()
    print("  Como ler: se SEMÂNTICO acerta e HÍBRIDO não, o problema é a fusão.")
    print("  Se SEMÂNTICO também falha, o problema é o modelo ou o corpus.")
    print()


if __name__ == "__main__":
    main()
