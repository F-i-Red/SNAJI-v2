"""
Rotas dos Casos — SNAJI
========================
Histórico persistente dos casos do utilizador (o "processo pessoal"):

  GET /casos            → lista dos meus casos (resumo)
  GET /casos/{caso_id}  → caso completo: ficha, alertas e análises anteriores

Os casos são criados automaticamente ao concluir a instrução; as análises
de cenários feitas a partir de um caso ficam-lhe anexadas para consulta futura.
Isolamento estrito: cada utilizador só acede aos seus casos.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException

from app.db.utilizadores import Utilizador
from app.security.dependencias import requer_permissao
from app.security.rbac import Permissao
from app.db import casos_repo

router = APIRouter()
logger = structlog.get_logger(__name__)

dep_casos = requer_permissao(Permissao.SUBMETER_CASO)


@router.get("/casos", tags=["Casos"])
async def listar_casos(utilizador: Utilizador = Depends(dep_casos)) -> list[dict]:
    """Lista os casos do utilizador autenticado (mais recentes primeiro)."""
    return casos_repo.listar_casos(str(utilizador.id))


@router.get("/casos/{caso_id}", tags=["Casos"])
async def obter_caso(caso_id: str, utilizador: Utilizador = Depends(dep_casos)) -> dict:
    """Devolve o caso completo, incluindo o histórico de análises."""
    caso = casos_repo.obter_caso(str(utilizador.id), caso_id)
    if not caso:
        raise HTTPException(status_code=404, detail="Caso não encontrado")
    return caso


@router.delete("/casos/{caso_id}/analises/{indice}", tags=["Casos"])
async def remover_analise(caso_id: str, indice: int,
                          utilizador: Utilizador = Depends(dep_casos)) -> dict:
    """
    Remove uma análise do histórico do caso, pela sua posição.

    Serve para limpar análises falhadas ou de ensaio. O isolamento por
    utilizador é o mesmo das restantes rotas: cada um só apaga o que é seu.
    """
    if not casos_repo.remover_analise(str(utilizador.id), caso_id, indice):
        raise HTTPException(status_code=404, detail="Análise não encontrada")
    logger.info("caso.analise_removida.api",
                caso_id=caso_id, indice=indice, user_id=str(utilizador.id))
    return {"removida": True, "indice": indice}


@router.delete("/casos/{caso_id}/analises", tags=["Casos"])
async def limpar_analises(caso_id: str,
                          utilizador: Utilizador = Depends(dep_casos)) -> dict:
    """Remove todas as análises do caso, mantendo o caso e a ficha de factos."""
    caso = casos_repo.obter_caso(str(utilizador.id), caso_id)
    if not caso:
        raise HTTPException(status_code=404, detail="Caso não encontrado")
    n = casos_repo.limpar_analises(str(utilizador.id), caso_id)
    logger.info("caso.analises_limpas.api",
                caso_id=caso_id, removidas=n, user_id=str(utilizador.id))
    return {"removidas": n}
