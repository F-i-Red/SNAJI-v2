"""
Rotas da API do AgenteInstrutor — SNAJI (Especificação V8, §1)
===============================================================
Expõe o ciclo de instrução do caso ao frontend:

  POST /instrutor/iniciar              → inicia a instrução, devolve 1.ª pergunta
  POST /instrutor/{caso_id}/responder  → regista resposta, devolve pergunta seguinte
  POST /instrutor/{caso_id}/concluir   → fecha a instrução, devolve Ficha + alertas
  GET  /instrutor/{caso_id}/estado     → snapshot do estado (retomar sessão)

Notas de desenho:
  - As sessões de instrução vivem em memória com TTL (suficiente para o PoC;
    na versão institucional migram para a base de dados, como os processos).
  - Cada sessão pertence ao utilizador que a iniciou: mais ninguém lhe acede.
  - O LLM é opcional: sem ANTHROPIC_API_KEY o instrutor corre em modo stub
    (sequência determinística de perguntas) — a API é exatamente a mesma.
  - A ressalva legal (Lei n.º 49/2004) é devolvida no início de toda a
    instrução e deve ser exibida pelo frontend antes da primeira pergunta.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.db.utilizadores import Utilizador
from app.security.dependencias import requer_permissao
from app.security.rbac import Permissao
from app.analytics.registo import registar
from app.db import casos_repo
from app.reasoning.agente_instrutor import (
    AgenteInstrutor,
    EstadoInstrucao,
    Resposta,
    RESSALVA_LEGAL,
)

router = APIRouter()
logger = structlog.get_logger(__name__)

# Dependência em variável de módulo (permite override em testes)
dep_submeter_caso = requer_permissao(Permissao.SUBMETER_CASO)


# ── Instância do agente (lazy; LLM se disponível) ───────────────────────────

_agente: Optional[AgenteInstrutor] = None


def get_agente() -> AgenteInstrutor:
    """
    Cria o agente uma única vez. Usa LLM se ANTHROPIC_API_KEY estiver
    definida e o pacote 'anthropic' instalado; caso contrário, modo stub.
    """
    global _agente
    if _agente is None:
        llm = None
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if api_key:
            try:
                import anthropic
                llm = anthropic.Anthropic(api_key=api_key)
                logger.info("instrutor.llm.ativo")
            except Exception as exc:  # pacote em falta ou chave inválida
                logger.warning("instrutor.llm.indisponivel", erro=str(exc))
        else:
            logger.info("instrutor.llm.stub", motivo="ANTHROPIC_API_KEY ausente")
        _agente = AgenteInstrutor(llm_client=llm)
    return _agente


# ── Armazém de sessões em memória (PoC) ─────────────────────────────────────

_TTL = timedelta(hours=2)


class _Sessao:
    def __init__(self, estado: EstadoInstrucao, user_id: str):
        self.estado = estado
        self.user_id = user_id
        self.ultima_atividade = datetime.now(timezone.utc)

    def tocar(self) -> None:
        self.ultima_atividade = datetime.now(timezone.utc)

    @property
    def expirada(self) -> bool:
        return datetime.now(timezone.utc) - self.ultima_atividade > _TTL


_sessoes: dict[str, _Sessao] = {}


def _limpar_expiradas() -> None:
    mortas = [cid for cid, s in _sessoes.items() if s.expirada]
    for cid in mortas:
        del _sessoes[cid]
    if mortas:
        logger.info("instrutor.sessoes.limpeza", removidas=len(mortas))


def _obter_sessao(caso_id: str, utilizador: Utilizador) -> _Sessao:
    _limpar_expiradas()
    sessao = _sessoes.get(caso_id)
    if sessao is None:
        raise HTTPException(
            status_code=404,
            detail="Instrução não encontrada ou expirada. Inicie novamente.",
        )
    if sessao.user_id != str(utilizador.id):
        # Não revelar a existência da sessão de outrem
        raise HTTPException(status_code=404, detail="Instrução não encontrada.")
    sessao.tocar()
    return sessao


# ── Modelos de pedido/resposta ──────────────────────────────────────────────

class IniciarInstrucaoRequest(BaseModel):
    relato: str = Field(..., min_length=10, max_length=8000,
                        description="Descrição livre do caso pelo cidadão")
    dificuldades_economicas: bool = Field(
        default=False,
        description="Se True, emite o alerta de apoio judiciário (Seg. Social)",
    )
    distrito: str | None = Field(
        default=None, max_length=40,
        description="Distrito/região (opcional; apenas para estatística agregada anónima)",
    )
    numero_processo: str | None = Field(
        default=None, max_length=40,
        description="Número de processo existente (ex.: CITIUS 1234/25.6T8LSB) — o SNAJI adota-o em vez de inventar",
    )


class ResponderRequest(BaseModel):
    pergunta_id: str
    valor: str = Field(..., min_length=1, max_length=4000)


class AlertaOut(BaseModel):
    tipo: str
    gravidade: str
    mensagem_tecnica: str
    mensagem_cidada: str
    norma_base: str = ""


class PerguntaOut(BaseModel):
    id: str
    texto: str
    tipo: str            # "escolha" | "texto" | "data" | "valor"
    opcoes: list[str]


class EstadoOut(BaseModel):
    caso_id: str
    ressalva: str
    terminado: bool
    motivo_fim: str
    via_llm: bool
    perguntas_feitas: int
    areas_preliminares: list[str]
    confianca: float
    alertas: list[AlertaOut]
    pergunta: Optional[PerguntaOut] = None   # próxima pergunta (None se terminou)


class FichaOut(BaseModel):
    caso_guardado_id: str | None = None
    caso_id: str
    ficha: dict
    texto_para_analise: str
    alertas: list[AlertaOut]
    areas: list[str]
    resumo: str


# ── Conversores internos ────────────────────────────────────────────────────

def _alertas_out(estado: EstadoInstrucao) -> list[AlertaOut]:
    return [
        AlertaOut(
            tipo=a.tipo.value,
            gravidade=a.gravidade.value,
            mensagem_tecnica=a.mensagem_tecnica,
            mensagem_cidada=a.mensagem_cidada,
            norma_base=a.norma_base,
        )
        for a in estado.alertas
    ]


def _estado_out(estado: EstadoInstrucao, pergunta=None) -> EstadoOut:
    classif = estado.classificacao
    return EstadoOut(
        caso_id=estado.caso_id,
        ressalva=RESSALVA_LEGAL,
        terminado=estado.terminado,
        motivo_fim=estado.motivo_fim,
        via_llm=estado.via_llm,
        perguntas_feitas=len(estado.perguntas_feitas),
        areas_preliminares=[a.value for a in classif.todas_as_areas] if classif else [],
        confianca=classif.confianca if classif else 0.0,
        alertas=_alertas_out(estado),
        pergunta=PerguntaOut(**pergunta.para_frontend()) if pergunta else None,
    )


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/instrutor/iniciar", response_model=EstadoOut, tags=["Instrutor"])
async def iniciar_instrucao(
    request: IniciarInstrucaoRequest,
    utilizador: Utilizador = Depends(dep_submeter_caso),
    agente: AgenteInstrutor = Depends(get_agente),
) -> EstadoOut:
    """
    Inicia a instrução de um caso: classifica preliminarmente o relato,
    emite alertas imediatos (via não judicial, apoio judiciário) e devolve
    a primeira pergunta do Instrutor.
    """
    _limpar_expiradas()
    estado = agente.iniciar(request.relato)
    if request.dificuldades_economicas:
        agente.emitir_alerta_apoio_judiciario(estado)

    if request.distrito:
        estado.ficha.respostas_normalizadas["distrito"] = request.distrito.strip().lower()

    if request.numero_processo:
        estado.ficha.respostas_normalizadas["numero_processo"] = request.numero_processo.strip()

    # Funil: regista o INÍCIO (permite medir abandono — sem viés de sobrevivência)
    registar("instrucao_iniciada", {
        "areas": [a.value for a in estado.classificacao.todas_as_areas]
        if estado.classificacao else [],
        "distrito": request.distrito.strip().lower() if request.distrito else None,
    })

    _sessoes[estado.caso_id] = _Sessao(estado, user_id=str(utilizador.id))
    pergunta = agente.proxima_pergunta(estado)

    logger.info(
        "instrutor.api.iniciado",
        caso_id=estado.caso_id,
        user_id=utilizador.id,
        via_llm=estado.via_llm,
    )
    return _estado_out(estado, pergunta)


@router.post(
    "/instrutor/{caso_id}/responder",
    response_model=EstadoOut,
    tags=["Instrutor"],
)
async def responder(
    caso_id: str,
    request: ResponderRequest,
    utilizador: Utilizador = Depends(dep_submeter_caso),
    agente: AgenteInstrutor = Depends(get_agente),
) -> EstadoOut:
    """
    Regista a resposta do cidadão à pergunta atual e devolve a pergunta
    seguinte (ou o estado final, se a instrução tiver terminado).
    """
    sessao = _obter_sessao(caso_id, utilizador)
    estado = sessao.estado

    if estado.terminado:
        return _estado_out(estado, None)

    ids_validos = {p.id for p in estado.perguntas_feitas}
    if request.pergunta_id not in ids_validos:
        raise HTTPException(status_code=422, detail="pergunta_id desconhecido.")
    if any(r.pergunta_id == request.pergunta_id for r in estado.respostas):
        raise HTTPException(status_code=422, detail="Pergunta já respondida.")

    agente.registar_resposta(estado, Resposta(request.pergunta_id, request.valor))
    pergunta = agente.proxima_pergunta(estado)
    return _estado_out(estado, pergunta)


@router.post(
    "/instrutor/{caso_id}/concluir",
    response_model=FichaOut,
    tags=["Instrutor"],
)
async def concluir_instrucao(
    caso_id: str,
    utilizador: Utilizador = Depends(dep_submeter_caso),
    agente: AgenteInstrutor = Depends(get_agente),
) -> FichaOut:
    """
    Fecha a instrução e devolve a Ficha de Factos estruturada + alertas.
    O campo `texto_para_analise` é o que deve alimentar o endpoint /analysis
    (pipeline de reasoning) em vez do relato original.
    """
    sessao = _obter_sessao(caso_id, utilizador)
    estado = sessao.estado
    ficha, alertas = agente.concluir(estado)

    logger.info(
        "instrutor.api.concluido",
        caso_id=caso_id,
        perguntas=len(estado.perguntas_feitas),
        alertas=len(alertas),
    )
    # Persistência: o caso fica guardado no histórico do utilizador (rota /casos)
    caso_guardado_id = casos_repo.guardar_caso(str(utilizador.id), {
        "caso_id": caso_id,
        "relato": estado.relato_inicial,
        "areas": [a.value for a in estado.classificacao.todas_as_areas]
        if estado.classificacao else [],
        "papel": estado.ficha.respostas_normalizadas.get("papel_no_caso", ""),
        "numero_processo": estado.ficha.respostas_normalizadas.get("numero_processo", ""),
        "ficha": ficha.para_dict(),
        "alertas": [a.model_dump() for a in _alertas_out(estado)],
        "texto_para_analise": ficha.para_texto_rag(),
    })

    # Registo analítico anonimizado (Especificação V8, §8): sem dados pessoais
    registar("instrucao_concluida", {
        "areas": [a.value for a in estado.classificacao.todas_as_areas]
        if estado.classificacao else [],
        "n_perguntas": len(estado.perguntas_feitas),
        "via_llm": estado.via_llm,
        "papel": estado.ficha.respostas_normalizadas.get("papel_no_caso", "desconhecido"),
        "distrito": estado.ficha.respostas_normalizadas.get("distrito"),
        "alertas": [{"tipo": a.tipo.value, "gravidade": a.gravidade.value,
                     "norma": a.norma_base, "subtipo": a.subtipo}
                    for a in estado.alertas],
    })
    return FichaOut(
        caso_guardado_id=caso_guardado_id,
        caso_id=caso_id,
        ficha=ficha.para_dict(),
        texto_para_analise=ficha.para_texto_rag(),
        alertas=_alertas_out(estado),
        areas=[a.value for a in estado.classificacao.todas_as_areas]
        if estado.classificacao else [],
        resumo=ficha.resumo_instrucao,
    )


@router.get(
    "/instrutor/{caso_id}/estado",
    response_model=EstadoOut,
    tags=["Instrutor"],
)
async def obter_estado(
    caso_id: str,
    utilizador: Utilizador = Depends(dep_submeter_caso),
) -> EstadoOut:
    """Snapshot do estado da instrução (permite retomar uma sessão aberta)."""
    sessao = _obter_sessao(caso_id, utilizador)
    estado = sessao.estado
    pendente = None
    respondidas = {r.pergunta_id for r in estado.respostas}
    for p in estado.perguntas_feitas:
        if p.id not in respondidas:
            pendente = p
            break
    return _estado_out(estado, pendente)
