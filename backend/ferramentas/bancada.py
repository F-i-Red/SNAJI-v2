# -*- coding: utf-8 -*-
"""
Bancada de medição da recuperação, com reescritas fixas.

As reescritas foram capturadas de execuções reais do sistema com LLM, e ficam
aqui congeladas para que as comparações entre versões do motor sejam
reprodutíveis — sem variação do modelo e sem consumir API.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

CASOS = [
    {
        "nome": "Laboral — despedimento verbal de grávida",
        "texto": (
            "Trabalho há 6 anos como técnica de armazém numa empresa em Sintra, com "
            "contrato sem termo. Ontem o meu chefe disse-me apenas verbalmente que estou "
            "despedida a partir de amanhã, porque a empresa precisa de cortar custos. "
            "Não recebi nenhuma carta, nenhum processo disciplinar, nada por escrito. "
            "Estou grávida de 5 meses e a empresa sabe disso. Que direitos tenho? "
            "Que prazos tenho para reagir?"
        ),
        "termos": (
            "despedimento ilícito; forma escrita do despedimento; despedimento verbal; "
            "ilicitude do despedimento; processo disciplinar; nota de culpa; "
            "protecção da parentalidade; trabalhadora grávida; "
            "apreciação judicial do despedimento; efeitos da ilicitude; "
            "despedimento por extinção do posto de trabalho; despedimento colectivo"
        ),
        "esperados": ["CT-63", "CT-338", "CT-351", "CT-381", "CT-387", "CT-389", "CT-367"],
    },
    {
        "nome": "Arrendamento — aumento de renda e ameaça de despejo",
        "texto": (
            "Vivo num apartamento arrendado em Lisboa desde 2019, com contrato escrito. "
            "Pago 850 euros de renda. O senhorio enviou carta simples a dizer que a renda "
            "passa para 1190 euros, um aumento de 40% de uma só vez. Não indica fundamento "
            "legal nem o coeficiente anual de actualização. Diz que se não aceitar tenho de "
            "sair de casa no fim do mês. Tenho dois filhos menores."
        ),
        "termos": (
            "arrendamento urbano para habitação; actualização da renda; "
            "coeficiente de actualização anual; comunicação da actualização de renda; "
            "requisitos formais da comunicação; resolução do contrato de arrendamento; "
            "denúncia pelo senhorio; oposição à renovação; despejo"
        ),
        "esperados": ["CC-1077", "CC-1083", "CC-1069", "CC-1101", "CC-1110"],
    },
    {
        "nome": "Penal + civil — agressão com indemnização",
        "texto": (
            "Um vizinho empurrou-me contra o portão da garagem durante uma discussão sobre "
            "estacionamento. Caí, parti o pulso direito e os óculos. Estive 3 semanas de "
            "baixa, tive 240 euros de despesas médicas. Há duas testemunhas e as câmaras "
            "gravaram. Apresentei queixa na PSP. Que crime está em causa? Posso pedir "
            "indemnização no mesmo processo?"
        ),
        "termos": (
            "ofensa à integridade física simples; ofensa à integridade física por "
            "negligência; direito de queixa; procedimento criminal dependente de queixa; "
            "princípio de adesão; pedido de indemnização civil em processo penal; "
            "responsabilidade civil extracontratual; obrigação de indemnizar"
        ),
        "esperados": ["CP-143", "CP-148", "CPP-71", "CPP-72", "CC-483"],
    },
    {
        "nome": "Consumo — reparação recusada na garantia",
        "texto": (
            "Comprei uma máquina de lavar há 14 meses. Avariou-se e a loja diz que a "
            "garantia já não cobre e que tenho de pagar a reparação. Não me deram qualquer "
            "explicação por escrito. O que posso fazer?"
        ),
        "termos": (
            "contrato de compra e venda de bens de consumo; garantia legal de conformidade; "
            "falta de conformidade do bem; presunção de anterioridade do defeito; "
            "direitos do consumidor; reparação ou substituição da coisa; "
            "venda de coisa defeituosa; direito à qualidade dos bens e serviços"
        ),
        "esperados": ["LDC-3", "LDC-4", "LDC-9", "CC-913", "CC-914"],
    },
]


def medir(rag, k: int = 8, com_termos: bool = True, silencioso: bool = False) -> float:
    total_ok = total = 0
    for c in CASOS:
        consulta = c["texto"] + ("\n" + c["termos"] if com_termos else "")
        obtidos = [f"{x.diploma}-{x.artigo}" for x in rag.search(consulta, top_k=k)]
        ok = [e for e in c["esperados"] if e in obtidos]
        total_ok += len(ok)
        total += len(c["esperados"])
        if not silencioso:
            falta = [e for e in c["esperados"] if e not in obtidos]
            print(f"  {c['nome'][:44]:46} {len(ok)}/{len(c['esperados'])}"
                  f"{('  falta: ' + ', '.join(falta)) if falta else ''}")
    pct = 100.0 * total_ok / total
    if not silencioso:
        print(f"  {'TOTAL':46} {total_ok}/{total} ({pct:.0f}%)")
    return pct


if __name__ == "__main__":
    from app.rag.motor import RAGJuridico
    import os
    os.environ["SNAJI_REESCRITA"] = "0"   # a reescrita já vem congelada
    os.environ["SNAJI_EMBEDDINGS"] = "0"  # medir só o motor lexical
    rag = RAGJuridico()
    for k in (8, 12, 15, 20, 25):
        print(f"\n=== top-{k} ===")
        medir(rag, k=k)
