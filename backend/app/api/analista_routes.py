"""
Rotas do Módulo Analista — SNAJI (Especificação V8, §8)

Perfil DGPJ/gestão. Todos os indicadores são agregados a partir do registo
analítico anonimizado (sem qualquer dado pessoal) e sujeitos a k-anonimato:
contagens inferiores a K (3) surgem mascaradas como "<3".

  GET /analista/observatorio     — conflitualidade: volumes, áreas, alertas, série temporal
  GET /analista/zonas-cinzentas  — índice de incerteza jurídica (divergência das lentes)
  GET /analista/qualidade        — groundedness, utilização de LLM, operação

Acesso: permissão VER_METRICAS (papéis analista, magistrado e admin, por RBAC).
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query
from app.db.utilizadores import Utilizador
from app.security.dependencias import requer_permissao
from app.security.rbac import Permissao
from app.analytics.analista import MotorAnalista

router = APIRouter()
logger = structlog.get_logger(__name__)

# Dependência em variável de módulo (permite override em testes)
dep_metricas = requer_permissao(Permissao.VER_METRICAS)


@router.get("/analista/observatorio", tags=["Analista"])
async def observatorio(
    dias: int = Query(default=30, ge=1, le=365),
    utilizador: Utilizador = Depends(dep_metricas),
) -> dict:
    """Observatório da conflitualidade: volumes por área, alertas, evolução."""
    logger.info("analista.observatorio", user_id=utilizador.id, dias=dias)
    return MotorAnalista(dias=dias).observatorio()


@router.get("/analista/zonas-cinzentas", tags=["Analista"])
async def zonas_cinzentas(
    dias: int = Query(default=30, ge=1, le=365),
    utilizador: Utilizador = Depends(dep_metricas),
) -> dict:
    """
    Zonas cinzentas da lei: fração de casos em que as três lentes
    interpretativas divergem — medida objetiva de incerteza jurídica.
    """
    logger.info("analista.zonas_cinzentas", user_id=utilizador.id, dias=dias)
    return MotorAnalista(dias=dias).zonas_cinzentas()


@router.get("/analista/qualidade", tags=["Analista"])
async def qualidade(
    dias: int = Query(default=30, ge=1, le=365),
    utilizador: Utilizador = Depends(dep_metricas),
) -> dict:
    """Qualidade e operação: groundedness, LLM vs. determinístico, instrução."""
    logger.info("analista.qualidade", user_id=utilizador.id, dias=dias)
    return MotorAnalista(dias=dias).qualidade()


@router.get("/analista/governacao", tags=["Analista"])
async def governacao(
    dias: int = Query(default=30, ge=1, le=365),
    utilizador: Utilizador = Depends(dep_metricas),
) -> dict:
    """
    Governação do sistema: funil de conclusão (abandono), equidade de acesso
    (papel processual), território, prazos salvos vs. expirados por norma, e
    artigos de lei mais invocados nas análises.
    """
    logger.info("analista.governacao", user_id=utilizador.id, dias=dias)
    return MotorAnalista(dias=dias).governacao()
