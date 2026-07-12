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
from fastapi.responses import HTMLResponse, PlainTextResponse
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


def _relatorio_html(obs: dict, gov: dict, dias: int) -> str:
    """Relatório consolidado do observatório, pronto a imprimir/PDF."""
    from datetime import datetime
    def kv(d: dict) -> str:
        return "".join(f"<tr><td>{k}</td><td style='text-align:right'>{v}</td></tr>" for k, v in d.items())
    funil = gov.get("funil", {})
    equidade = gov.get("equidade_de_acesso", {}).get("por_papel_processual", {})
    territorio = gov.get("territorio", {}).get("instrucoes_por_distrito", {})
    normas = gov.get("normas_mais_invocadas", {})
    return f"""<!DOCTYPE html><html lang="pt"><head><meta charset="utf-8">
<title>Relatório do Observatório SNAJI</title>
<style>
  body {{ font-family: Georgia, serif; max-width: 820px; margin: 32px auto; padding: 0 24px; color: #1a1a1a; line-height: 1.5; }}
  h1 {{ font-size: 23px; border-bottom: 2px solid #0a2342; padding-bottom: 8px; }}
  h2 {{ font-size: 16px; color: #0a2342; margin-top: 22px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 13px; }}
  td {{ padding: 4px 8px; border-bottom: 0.5px solid #e5e5e5; }}
  .meta {{ color: #555; font-size: 13px; }}
  @media print {{ .noprint {{ display: none; }} }}
</style></head><body>
<button class="noprint" onclick="window.print()" style="float:right;padding:8px 16px;background:#0a2342;color:#fff;border:none;border-radius:6px;cursor:pointer">🖨 Imprimir / PDF</button>
<h1>Observatório da Justiça — Relatório</h1>
<p class="meta">Período: últimos {dias} dias · Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
<h2>Funil de utilização</h2>
<table><tr><td>Instruções iniciadas</td><td style='text-align:right'>{funil.get('instrucoes_iniciadas','—')}</td></tr>
<tr><td>Instruções concluídas</td><td style='text-align:right'>{funil.get('instrucoes_concluidas','—')}</td></tr>
<tr><td>Taxa de conclusão</td><td style='text-align:right'>{round((funil.get('taxa_de_conclusao') or 0)*100)}%</td></tr></table>
<h2>Equidade de acesso (por papel processual)</h2>
<table>{kv(equidade)}</table>
<h2>Distribuição territorial</h2>
<table>{kv(territorio)}</table>
<h2>Artigos de lei mais invocados</h2>
<table>{kv(normas)}</table>
<p class="meta" style="margin-top:24px;border-top:1px solid #ddd;padding-top:10px">
Dados agregados e anonimizados (k-anonimato). Relatório gerado pelo SNAJI para apoio à decisão de política pública — sem valor oficial.</p>
</body></html>"""


@router.get("/analista/relatorio.html", response_class=HTMLResponse, tags=["Analista"])
async def relatorio_html(dias: int = Query(default=30, ge=1, le=365),
                         utilizador: Utilizador = Depends(dep_metricas)):
    """Relatório consolidado do observatório (imprimir / guardar PDF)."""
    m = MotorAnalista(dias=dias)
    return _relatorio_html(m.observatorio(), m.governacao(), dias)


@router.get("/analista/relatorio.csv", response_class=PlainTextResponse, tags=["Analista"])
async def relatorio_csv(dias: int = Query(default=30, ge=1, le=365),
                        utilizador: Utilizador = Depends(dep_metricas)):
    """Dados do observatório em CSV (para folha de cálculo)."""
    m = MotorAnalista(dias=dias)
    gov = m.governacao()
    linhas = ["categoria,item,valor"]
    for k, v in gov.get("funil", {}).items():
        linhas.append(f"funil,{k},{v}")
    for k, v in gov.get("equidade_de_acesso", {}).get("por_papel_processual", {}).items():
        linhas.append(f"equidade,{k},{v}")
    for k, v in gov.get("territorio", {}).get("instrucoes_por_distrito", {}).items():
        linhas.append(f"territorio,{k},{v}")
    for k, v in gov.get("normas_mais_invocadas", {}).items():
        linhas.append(f"norma_invocada,{k},{v}")
    return "\n".join(linhas)


@router.get("/analista/utilizacao", tags=["Analista"])
async def utilizacao(dias: int = Query(default=30, ge=1, le=365),
                     utilizador: Utilizador = Depends(dep_metricas)):
    """Métricas de utilização: logins, funcionalidades mais usadas (agregado)."""
    return MotorAnalista(dias=dias).utilizacao()


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
