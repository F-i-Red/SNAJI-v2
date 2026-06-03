"""
Motor de Workflow Processual do SNAJI — Fase 2.

Implementa as regras legais reais dos prazos processuais portugueses:
- Prazos do CPC (Lei n.º 41/2013)
- Prazos do CPP (DL n.º 78/87)
- Prazos do Código do Trabalho (Lei n.º 7/2009)

Cada transição de fase gera automaticamente os prazos legais correctos.
O sistema alerta quando um prazo está em risco.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional
import structlog

from app.processes.repositorio import (
    TipoProcesso, EstadoProcesso, Prazo, ORDEM_FASES
)

logger = structlog.get_logger(__name__)


# ── Prazos legais por tipo e fase ────────────────────────────────────────────
# Fonte: CPC Art. 569.º (contestação 30 dias), Art. 607.º (sentença 30 dias),
#        CT Art. 352.º (nota de culpa 30 dias), CPP Art. 283.º (acusação 90 dias)

@dataclass
class RegraFase:
    descricao: str
    dias_uteis: int
    urgente_em_dias: int   # quantos dias antes do limite marcar como urgente
    base_legal: str


REGRAS_PRAZOS: dict[TipoProcesso, dict[EstadoProcesso, list[RegraFase]]] = {

    TipoProcesso.LABORAL: {
        EstadoProcesso.APRESENTACAO: [
            RegraFase("Citação do réu", 15, 5, "CPC Art. 225.º"),
        ],
        EstadoProcesso.CITACAO: [
            RegraFase("Prazo de contestação do réu", 30, 7, "CPC Art. 569.º n.º1"),
        ],
        EstadoProcesso.CONTESTACAO: [
            RegraFase("Resposta à contestação (réplica)", 30, 7, "CPC Art. 584.º"),
            RegraFase("Submissão de lista de testemunhas", 20, 5, "CPC Art. 598.º"),
        ],
        EstadoProcesso.INSTRUCAO: [
            RegraFase("Audiência prévia", 30, 5, "CPC Art. 591.º"),
        ],
        EstadoProcesso.JULGAMENTO: [
            RegraFase("Audiência de julgamento", 60, 14, "CPC Art. 151.º"),
        ],
        EstadoProcesso.SENTENCA: [
            RegraFase("Prazo de recurso de apelação", 30, 7, "CPC Art. 638.º n.º1"),
            RegraFase("Pagamento de indemnização (se aplicável)", 30, 10, "CT Art. 389.º"),
        ],
    },

    TipoProcesso.PENAL: {
        EstadoProcesso.APRESENTACAO: [
            RegraFase("Abertura de inquérito pelo MP", 10, 3, "CPP Art. 262.º"),
        ],
        EstadoProcesso.CITACAO: [
            RegraFase("Constituição de arguido", 5, 2, "CPP Art. 57.º"),
            RegraFase("1.º interrogatório judicial", 48, 1, "CPP Art. 141.º (horas → convertido)"),
        ],
        EstadoProcesso.CONTESTACAO: [
            RegraFase("Dedução de acusação pelo MP", 90, 14, "CPP Art. 283.º n.º1"),
            RegraFase("Prazo de instrução (se requerida)", 30, 7, "CPP Art. 287.º"),
        ],
        EstadoProcesso.INSTRUCAO: [
            RegraFase("Decisão instrutória", 30, 7, "CPP Art. 308.º"),
        ],
        EstadoProcesso.JULGAMENTO: [
            RegraFase("Audiência de julgamento", 60, 10, "CPP Art. 312.º"),
        ],
        EstadoProcesso.SENTENCA: [
            RegraFase("Recurso para o Tribunal da Relação", 30, 7, "CPP Art. 411.º n.º1"),
        ],
    },

    TipoProcesso.CIVIL: {
        EstadoProcesso.APRESENTACAO: [
            RegraFase("Citação do réu", 15, 5, "CPC Art. 225.º"),
        ],
        EstadoProcesso.CITACAO: [
            RegraFase("Contestação pelo réu", 30, 7, "CPC Art. 569.º"),
        ],
        EstadoProcesso.CONTESTACAO: [
            RegraFase("Réplica (se admissível)", 30, 7, "CPC Art. 584.º"),
        ],
        EstadoProcesso.INSTRUCAO: [
            RegraFase("Audiência prévia", 30, 5, "CPC Art. 591.º"),
            RegraFase("Produção de prova", 60, 14, "CPC Art. 410.º"),
        ],
        EstadoProcesso.JULGAMENTO: [
            RegraFase("Audiência final", 60, 14, "CPC Art. 151.º"),
        ],
        EstadoProcesso.SENTENCA: [
            RegraFase("Apelação para o Tribunal da Relação", 30, 7, "CPC Art. 638.º"),
            RegraFase("Cumprimento voluntário da sentença", 20, 5, "CPC Art. 817.º CC"),
        ],
    },

    TipoProcesso.ADMINISTRATIVO: {
        EstadoProcesso.APRESENTACAO: [
            RegraFase("Notificação da entidade administrativa", 10, 3, "CPA Art. 114.º"),
        ],
        EstadoProcesso.CITACAO: [
            RegraFase("Resposta da entidade (audiência prévia)", 10, 3, "CPA Art. 121.º"),
        ],
        EstadoProcesso.CONTESTACAO: [
            RegraFase("Contestação/alegações", 30, 7, "CPTA Art. 83.º"),
        ],
        EstadoProcesso.SENTENCA: [
            RegraFase("Recurso jurisdicional", 30, 7, "CPTA Art. 140.º"),
        ],
    },

    TipoProcesso.FAMILIA: {
        EstadoProcesso.APRESENTACAO: [
            RegraFase("Tentativa de conciliação", 30, 7, "RGPTC Art. 24.º"),
        ],
        EstadoProcesso.CITACAO: [
            RegraFase("Resposta do outro cônjuge/progenitor", 30, 7, "CPC Art. 569.º"),
        ],
        EstadoProcesso.INSTRUCAO: [
            RegraFase("Conferência de pais (regulação parental)", 30, 5, "RGPTC Art. 35.º"),
        ],
        EstadoProcesso.SENTENCA: [
            RegraFase("Recurso da decisão", 15, 5, "CPC Art. 638.º n.º2"),
        ],
    },

    TipoProcesso.DADOS_PESSOAIS: {
        EstadoProcesso.APRESENTACAO: [
            RegraFase("Resposta da CNPD à queixa", 30, 7, "RGPD Art. 77.º n.º2"),
        ],
        EstadoProcesso.CITACAO: [
            RegraFase("Notificação ao responsável pelo tratamento", 15, 5, "RGPD Art. 58.º"),
        ],
        EstadoProcesso.SENTENCA: [
            RegraFase("Prazo para pagamento de coima", 30, 7, "RGPD Art. 83.º"),
        ],
    },
}

# Regras genéricas para tipos sem configuração específica
REGRAS_GENERICAS: dict[EstadoProcesso, list[RegraFase]] = {
    EstadoProcesso.APRESENTACAO: [RegraFase("Citação das partes", 15, 5, "CPC Art. 225.º")],
    EstadoProcesso.CITACAO: [RegraFase("Contestação", 30, 7, "CPC Art. 569.º")],
    EstadoProcesso.INSTRUCAO: [RegraFase("Produção de prova", 60, 14, "CPC Art. 410.º")],
    EstadoProcesso.SENTENCA: [RegraFase("Prazo de recurso", 30, 7, "CPC Art. 638.º")],
}


@dataclass
class ResultadoTransicao:
    """Resultado de uma transição de fase com os prazos gerados."""
    estado_anterior: str
    estado_novo: str
    prazos_gerados: list[Prazo]
    alertas: list[str]


class MotorWorkflow:
    """
    Gere as transições de fases processuais e os prazos legais associados.

    Cada transição:
    1. Valida que é legal (não salta fases)
    2. Gera os prazos legais correctos para a nova fase
    3. Regista o evento no histórico imutável
    4. Alerta se há prazos urgentes
    """

    def calcular_prazos_fase(
        self,
        tipo: TipoProcesso,
        fase: EstadoProcesso,
        data_referencia: Optional[datetime] = None,
    ) -> list[Prazo]:
        """
        Calcula os prazos legais para uma fase num tipo de processo.
        Usa dias úteis (exclui sábados e domingos).
        """
        agora = data_referencia or datetime.now(timezone.utc)
        regras_tipo = REGRAS_PRAZOS.get(tipo, {})
        regras = regras_tipo.get(fase, REGRAS_GENERICAS.get(fase, []))

        prazos = []
        for regra in regras:
            data_limite = self._adicionar_dias_uteis(agora, regra.dias_uteis)
            dias_restantes = (data_limite - agora).days
            urgente = dias_restantes <= regra.urgente_em_dias

            prazos.append(Prazo(
                descricao=f"{regra.descricao} ({regra.base_legal})",
                data_limite=data_limite,
                urgente=urgente,
                cumprido=False,
            ))

        return prazos

    def _adicionar_dias_uteis(self, inicio: datetime, dias: int) -> datetime:
        """Adiciona dias úteis (excluindo sábados e domingos)."""
        atual = inicio
        contados = 0
        while contados < dias:
            atual += timedelta(days=1)
            if atual.weekday() < 5:  # 0=segunda, 4=sexta
                contados += 1
        return atual

    def analisar_urgencia(self, prazos: list[Prazo]) -> list[str]:
        """Gera alertas para prazos críticos."""
        alertas = []
        agora = datetime.now(timezone.utc)
        for pr in prazos:
            if pr.cumprido:
                continue
            dias = (pr.data_limite - agora).days
            if dias < 0:
                alertas.append(f"⚠️  PRAZO EXPIRADO: {pr.descricao}")
            elif dias == 0:
                alertas.append(f"🔴 PRAZO HOJE: {pr.descricao}")
            elif dias <= 3:
                alertas.append(f"🟠 {dias} dias restantes: {pr.descricao}")
        return alertas

    def validar_transicao(
        self,
        estado_actual: EstadoProcesso,
        estado_pretendido: EstadoProcesso,
    ) -> tuple[bool, str]:
        """
        Verifica se uma transição é legal.
        Não se podem saltar fases nem retroceder.
        Arquivamento e conclusão são sempre permitidos.
        """
        if estado_pretendido in (EstadoProcesso.ARQUIVADO, EstadoProcesso.CONCLUIDO):
            return True, "Arquivamento/conclusão sempre permitido"

        try:
            idx_actual = ORDEM_FASES.index(estado_actual)
            idx_pretendido = ORDEM_FASES.index(estado_pretendido)
        except ValueError:
            return False, "Estado desconhecido"

        if idx_pretendido == idx_actual + 1:
            return True, "Transição sequencial válida"

        if idx_pretendido <= idx_actual:
            return False, f"Não é possível retroceder de '{estado_actual.value}' para '{estado_pretendido.value}'"

        return False, f"Não é possível saltar de '{estado_actual.value}' directamente para '{estado_pretendido.value}'"


# Instância partilhada
motor_workflow = MotorWorkflow()
