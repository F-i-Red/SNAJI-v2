"""
Rotas do Motor de Cenários — SNAJI (Especificação V8, §2 e §3)

POST /cenarios → gera até 3 cenários de resolução (garantista, legalista,
consequencialista), com saída dupla (registo técnico + linguagem clara),
fundamentação validada contra o corpus e regra da convergência.

Aceita texto livre ou, preferencialmente, o `texto_para_analise` devolvido
pela conclusão do AgenteInstrutor.
"""

from __future__ import annotations

import os
from typing import Optional

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.db.utilizadores import Utilizador
from app.security.dependencias import requer_permissao
from app.security.rbac import Permissao
from app.analytics.registo import registar
from app.reasoning.motor_cenarios import MotorCenarios, RESSALVA_CENARIOS

router = APIRouter()
logger = structlog.get_logger(__name__)

# Dependência em variável de módulo (permite override em testes)
dep_cenarios = requer_permissao(Permissao.SUBMETER_CASO)

_motor: Optional[MotorCenarios] = None


def get_motor() -> MotorCenarios:
    """Motor único; usa LLM se ANTHROPIC_API_KEY existir, stub caso contrário."""
    global _motor
    if _motor is None:
        llm = None
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if api_key:
            try:
                import anthropic
                llm = anthropic.Anthropic(api_key=api_key)
                logger.info("cenarios.llm.ativo")
            except Exception as exc:
                logger.warning("cenarios.llm.indisponivel", erro=str(exc))
        _motor = MotorCenarios(llm_client=llm)
    return _motor


class CenariosRequest(BaseModel):
    texto: str = Field(..., min_length=20, max_length=20000,
                       description="Texto do caso ou texto_para_analise do Instrutor")
    top_k_normas: int = Field(default=8, ge=3, le=15)
    explicar: bool = Field(default=False,
                           description="Se True, inclui o percurso de explicabilidade (etapas da análise)")


class CenarioOut(BaseModel):
    lente: str
    lente_descricao_tecnica: str
    lente_descricao_cidada: str
    titulo: str
    sentido: str
    solucao_tecnica: str
    solucao_cidada: str
    riscos: str
    riscos_cidadao: str
    solidez: str
    fundamentacao_normas: list[str]
    normas_rejeitadas: list[str]


class CenariosResponse(BaseModel):
    cenarios: list[CenarioOut]
    convergencia: bool
    sintese_tecnica: str
    sintese_cidada: str
    normas_rejeitadas_total: list[str]
    ressalva: str = RESSALVA_CENARIOS
    via_llm: bool
    percurso: list[dict] | None = None   # explicabilidade (só quando pedida)


@router.post("/cenarios", response_model=CenariosResponse, tags=["Cenários"])
async def gerar_cenarios(
    request: CenariosRequest,
    utilizador: Utilizador = Depends(dep_cenarios),
    motor: MotorCenarios = Depends(get_motor),
) -> CenariosResponse:
    """
    Gera os cenários de resolução do caso pelas três lentes interpretativas.
    Só cenários juridicamente viáveis são devolvidos (1 a 3); em caso de
    convergência das lentes, devolve-se uma única solução assinalada.
    """
    resultado = motor.gerar(request.texto, top_k_normas=request.top_k_normas)
    logger.info(
        "cenarios.api", user_id=utilizador.id,
        n=len(resultado.cenarios), convergencia=resultado.convergencia,
    )
    # Registo analítico anonimizado (Especificação V8, §8)
    registar("cenarios_gerados", {
        "normas_validadas": sorted({n for c in resultado.cenarios
                                    for n in c.fundamentacao_normas}),
        "convergencia": resultado.convergencia,
        "n_cenarios": len(resultado.cenarios),
        "solidez": [c.solidez for c in resultado.cenarios],
        "normas_rejeitadas": len(resultado.normas_rejeitadas_total),
        "via_llm": resultado.via_llm,
    })
    d = resultado.para_dict()
    return CenariosResponse(
        cenarios=[CenarioOut(
            lente=c["lente"],
            lente_descricao_tecnica=c["lente_descricao_tecnica"],
            lente_descricao_cidada=c["lente_descricao_cidada"],
            titulo=c["titulo"],
            sentido=c["sentido"],
            solucao_tecnica=c["solucao_tecnica"],
            solucao_cidada=c["solucao_cidada"],
            riscos=c["riscos"],
            riscos_cidadao=c["riscos_cidadao"],
            solidez=c["solidez"],
            fundamentacao_normas=c["fundamentacao_normas"],
            normas_rejeitadas=c["normas_rejeitadas"],
        ) for c in d["cenarios"]],
        convergencia=d["convergencia"],
        sintese_tecnica=d["sintese_tecnica"],
        sintese_cidada=d["sintese_cidada"],
        normas_rejeitadas_total=d["normas_rejeitadas_total"],
        via_llm=d["via_llm"],
        percurso=d["percurso"] if request.explicar else None,
    )
