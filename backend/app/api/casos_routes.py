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
