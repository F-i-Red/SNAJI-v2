# -*- coding: utf-8 -*-
"""Testes do atualizador de acórdãos (ferramentas/atualizador_acordaos.py).

O extrator é testado contra texto REAL das páginas do STJ (fixtures copiadas
de stj.pt), sem depender da rede. Garante que futuras alterações ao site ou ao
regex não partem a recolha em silêncio.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rag.motor import RAGJuridico, NORMAS_VALIDAS  # noqa: E402

RAGJuridico()  # popula NORMAS_VALIDAS

from ferramentas.atualizador_acordaos import (  # noqa: E402
    extrair_acordaos_de_pagina,
    extrair_normas,
)

# Texto real copiado das páginas oficiais do STJ (uniformização de jurisprudência)
FIXTURE_STJ = """
<div>Acórdão do Supremo Tribunal de Justiça n.º 5/2025 Processo 92/07.1TELSB-M.S1, de 19-02-2025
«O prazo de prescrição do procedimento pelo crime de fraude fiscal qualificada, p. e p. no artigo
104.º, n.º 2, al. a), do RGIT, inicia-se no momento da entrega da correspondente declaração à
administração fiscal.» Leonor Furtado (Relatora) DR n.º 90/2025</div>
<div>Acórdão do Supremo Tribunal de Justiça n.º 8/2025: «Decorrido o período de suspensão da
execução de pena de prisão, a pena suspensa prescreve decorridos 4 anos contados do termo daquele
período, nos termos da alínea d) do n.º 1 do artigo 122.º, do Código Penal.»</div>
<div>Acórdão do Supremo Tribunal de Justiça n.º 4/2025: «A indemnização atribuída ao trabalhador
ilicitamente despedido, em substituição da reintegração, é parcialmente impenhorável, nos termos
do n.º 1 do artigo 738.º do Código de Processo Civil.»</div>
<div>Acórdão do Supremo Tribunal de Justiça n.º 11/2025: «A deliberação dos sócios a que se refere
o art.º 242.º n.º 2 do Código das Sociedades Comerciais deve ocorrer no prazo de 90 dias.»</div>
"""


class TestExtratorAcordaos:
    def test_extrai_todos_os_acordaos_da_fixture(self):
        acs = extrair_acordaos_de_pagina(
            FIXTURE_STJ, "https://www.stj.pt/uniformizacao-de-jurisprudencia/criminais/",
            NORMAS_VALIDAS)
        numeros = {a["numero_processo"] for a in acs}
        assert "Acórdão STJ n.º 5/2025" in numeros
        assert "Acórdão STJ n.º 8/2025" in numeros
        assert "Acórdão STJ n.º 4/2025" in numeros
        assert "Acórdão STJ n.º 11/2025" in numeros

    def test_captura_processo_e_data_quando_presentes(self):
        acs = extrair_acordaos_de_pagina(FIXTURE_STJ, "https://www.stj.pt/x/", NORMAS_VALIDAS)
        a5 = next(a for a in acs if "5/2025" in a["numero_processo"])
        assert a5["processo"] == "92/07.1TELSB-M.S1"
        assert a5["data"] == "19-02-2025"

    def test_normas_validadas_contra_corpus(self):
        """As normas citadas nos sumários são verificadas — nunca inventadas."""
        acs = extrair_acordaos_de_pagina(FIXTURE_STJ, "https://www.stj.pt/x/", NORMAS_VALIDAS)
        a8 = next(a for a in acs if "8/2025" in a["numero_processo"])
        assert "CP-122" in a8["normas_citadas"]
        a4 = next(a for a in acs if "4/2025" in a["numero_processo"])
        assert "CPC-738" in a4["normas_citadas"]
        a11 = next(a for a in acs if "11/2025" in a["numero_processo"])
        assert "CSC-242" in a11["normas_citadas"]

    def test_norma_inexistente_vai_para_nao_verificadas(self):
        validas, nao_verif = extrair_normas(
            "nos termos do artigo 99999.º do Código Civil", NORMAS_VALIDAS)
        assert validas == []
        assert "CC-99999" in nao_verif

    def test_sumario_curto_e_ignorado(self):
        """Fragmentos sem sumário substantivo não entram na base."""
        lixo = 'Acórdão do Supremo Tribunal de Justiça n.º 1/2020 «curto»'
        acs = extrair_acordaos_de_pagina(lixo, "https://www.stj.pt/x/", NORMAS_VALIDAS)
        assert acs == []
