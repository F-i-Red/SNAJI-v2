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
from pydantic import BaseModel, Field

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


# Esta rota vem antes de /casos/{caso_id}: caso contrário o FastAPI leria
# "motivos-descarte" como identificador de um caso e devolveria 404.
@router.get("/casos/motivos-descarte", tags=["Casos"])
async def motivos_descarte(_: Utilizador = Depends(dep_casos)) -> dict:
    """Motivos disponíveis para descartar uma análise."""
    return casos_repo.MOTIVOS_DESCARTE

@router.get("/casos/{caso_id}", tags=["Casos"])
async def obter_caso(caso_id: str, utilizador: Utilizador = Depends(dep_casos)) -> dict:
    """Devolve o caso completo, incluindo o histórico de análises."""
    caso = casos_repo.obter_caso(str(utilizador.id), caso_id, partilhado=True)
    if not caso:
        raise HTTPException(status_code=404, detail="Caso não encontrado")
    return caso


class DescarteRequest(BaseModel):
    motivo: str = Field(default="outro", description="Chave de casos_repo.MOTIVOS_DESCARTE")
    nota: str = Field(default="", max_length=400)




@router.post("/casos/{caso_id}/analises/{indice}/descartar", tags=["Casos"])
async def descartar_analise(caso_id: str, indice: int, dados: DescarteRequest,
                            utilizador: Utilizador = Depends(dep_casos)) -> dict:
    """
    Retira uma análise da vista principal, arquivando-a com data e motivo.

    Não destrói: a análise continua no processo, assinalada como descartada.
    """
    ok = casos_repo.descartar_analise(
        casos_repo.dono_do_caso(caso_id) or str(utilizador.id),
        caso_id, indice, dados.motivo, dados.nota)
    if not ok:
        # Distingue os dois motivos: uma análise fixada como definitiva integra
        # o processo e a recusa é deliberada, não um erro de identificação.
        caso = casos_repo.obter_caso(str(utilizador.id), caso_id, partilhado=True)
        lista = (caso or {}).get("analises_cenarios", [])
        if 0 <= indice < len(lista) and lista[indice].get("definitiva"):
            raise HTTPException(
                status_code=409,
                detail="Análise fixada como definitiva: integra o processo e "
                       "não pode ser descartada.")
        raise HTTPException(status_code=404, detail="Análise não encontrada")
    logger.info("caso.analise_descartada.api", caso_id=caso_id,
                indice=indice, motivo=dados.motivo, user_id=str(utilizador.id))
    return {"descartada": True, "indice": indice, "motivo": dados.motivo}


@router.post("/casos/{caso_id}/analises/descartar-todas", tags=["Casos"])
async def descartar_todas(caso_id: str, dados: DescarteRequest,
                          utilizador: Utilizador = Depends(dep_casos)) -> dict:
    """Descarta todas as análises do caso, arquivando-as."""
    if not casos_repo.obter_caso(str(utilizador.id), caso_id, partilhado=True):
        raise HTTPException(status_code=404, detail="Caso não encontrado")
    n = casos_repo.descartar_todas(
        casos_repo.dono_do_caso(caso_id) or str(utilizador.id),
        caso_id, dados.motivo, dados.nota)
    logger.info("caso.analises_descartadas.api", caso_id=caso_id,
                descartadas=n, motivo=dados.motivo, user_id=str(utilizador.id))
    return {"descartadas": n, "motivo": dados.motivo}


@router.post("/casos/{caso_id}/analises/{indice}/activar", tags=["Casos"])
async def activar_analise(caso_id: str, indice: int,
                          utilizador: Utilizador = Depends(dep_casos)) -> dict:
    """Marca a análise como a apreciação corrente do caso."""
    if not casos_repo.activar_analise(
            casos_repo.dono_do_caso(caso_id) or str(utilizador.id), caso_id, indice):
        raise HTTPException(status_code=404, detail="Análise não encontrada")
    return {"activa": indice}


@router.post("/casos/{caso_id}/arquivo/{indice}/restaurar", tags=["Casos"])
async def restaurar_analise(caso_id: str, indice: int,
                            utilizador: Utilizador = Depends(dep_casos)) -> dict:
    """Traz uma análise do arquivo de volta à lista."""
    if not casos_repo.restaurar_analise(
            casos_repo.dono_do_caso(caso_id) or str(utilizador.id), caso_id, indice):
        raise HTTPException(status_code=404, detail="Análise não encontrada no arquivo")
    return {"restaurada": indice}


@router.post("/casos/{caso_id}/analises/{indice}/definitiva", tags=["Casos"])
async def definir_definitiva(caso_id: str, indice: int,
                             utilizador: Utilizador = Depends(dep_casos)) -> dict:
    """
    Fixa a análise como apreciação definitiva do processo.

    Deixa de poder ser descartada — é o equivalente a proferir. As restantes
    mantêm-se disponíveis para consulta e comparação.
    """
    dono = casos_repo.dono_do_caso(caso_id) or str(utilizador.id)
    if not casos_repo.definir_definitiva(dono, caso_id, indice):
        raise HTTPException(status_code=404, detail="Análise não encontrada")
    logger.info("caso.analise_definitiva.api", caso_id=caso_id,
                indice=indice, user_id=str(utilizador.id))
    return {"definitiva": indice}
