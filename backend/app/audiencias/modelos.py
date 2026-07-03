"""
Modelos de dados das Audiências do SNAJI — Fase 3 (V2).

Uma audiência é um debate estruturado entre agentes especializados
sobre um caso jurídico real, com base em normas verificadas.

Estrutura:
  Audiência → Rondas → Intervenções (por agente)
                    ↓
             Decisão final fundamentada (pelo Juiz)

V2 (Especificação V8, §7): novos intervenientes processuais —
arguido, testemunha, demandante/demandado civil (princípio da adesão),
escrivão (ata com cadeia de integridade), intérprete e defensor oficioso.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import hashlib
import uuid


class TipoAudiencia(str, Enum):
    JULGAMENTO           = "julgamento"            # Processo penal/civil completo
    AUDIENCIA_PRELIMINAR = "audiencia_preliminar"  # Antes do julgamento
    CONTRADITORIO        = "contraditorio"         # Debate de posições
    PREPARACAO           = "preparacao"            # Treino — advogado prepara-se
    SIMULACAO            = "simulacao"             # Demo/formação


class PapelAgente(str, Enum):
    # Papéis originais (V1)
    JUIZ       = "juiz"        # Modera, decide, aplica a lei
    ACUSACAO   = "acusacao"    # Ministério Público ou autor
    DEFESA     = "defesa"      # Advogado de defesa (mandatário ou defensor oficioso)
    PERITO     = "perito"      # Especialista em factos técnicos
    ASSISTENTE = "assistente"  # Ofendido constituído assistente (arts. 68.º-69.º CPP)
    # Papéis V2 (Especificação V8, §7.1)
    ARGUIDO           = "arguido"            # A pessoa acusada — declarações e últimas declarações (art. 361.º CPP)
    TESTEMUNHA        = "testemunha"         # Depõe na fase de prova, sob juramento
    DEMANDANTE_CIVIL  = "demandante_civil"   # Pedido de indemnização enxertado (art. 71.º CPP)
    DEMANDADO_CIVIL   = "demandado_civil"    # Responde ao pedido civil enxertado
    ESCRIVAO          = "escrivao"           # Lavra a ata — registo auditável de cada ato
    INTERPRETE        = "interprete"         # Interveniente transversal (art. 92.º CPP)


class EstadoAudiencia(str, Enum):
    PENDENTE  = "pendente"   # Criada, não iniciada
    EM_CURSO  = "em_curso"   # A decorrer
    PAUSADA   = "pausada"    # Pausada
    CONCLUIDA = "concluida"  # Terminada com decisão
    CANCELADA = "cancelada"


class TipoIntervencao(str, Enum):
    ABERTURA             = "abertura"
    ALEGACAO             = "alegacao"
    CONTRA_ALEGACAO      = "contra_alegacao"
    PERGUNTA             = "pergunta"
    RESPOSTA             = "resposta"
    PROVA                = "prova"
    OBJECAO              = "objecao"
    DECISAO_FINAL        = "decisao_final"
    ENCERRAMENTO         = "encerramento"
    # V2
    ATA                  = "ata"                   # Lavrada pelo escrivão a cada ato
    DEPOIMENTO           = "depoimento"            # Testemunha ou declarações de parte
    ULTIMAS_DECLARACOES  = "ultimas_declaracoes"   # Do arguido (art. 361.º CPP)


@dataclass
class ConfiguracaoAgente:
    """Configuração de um agente participante na audiência."""
    papel: PapelAgente
    nome: str
    instrucoes_sistema: str    # prompt de sistema para este agente
    activo: bool = True


@dataclass
class Intervencao:
    """
    Uma intervenção individual de um agente na audiência.
    Imutável após criação — hash garante integridade.
    """
    id: str
    audiencia_id: str
    ronda: int
    papel: PapelAgente
    tipo: TipoIntervencao
    conteudo: str
    timestamp: datetime
    normas_citadas: list[str]  # ["CRP-53", "CT-351"]
    hash_integridade: str      # SHA-256 do conteúdo

    @classmethod
    def criar(
        cls,
        audiencia_id: str,
        ronda: int,
        papel: PapelAgente,
        tipo: TipoIntervencao,
        conteudo: str,
        normas_citadas: list[str] | None = None,
    ) -> "Intervencao":
        ts = datetime.now(timezone.utc)
        iid = str(uuid.uuid4())
        hash_val = hashlib.sha256(
            f"{iid}|{audiencia_id}|{ronda}|{papel.value}|{conteudo}".encode()
        ).hexdigest()
        return cls(
            id=iid,
            audiencia_id=audiencia_id,
            ronda=ronda,
            papel=papel,
            tipo=tipo,
            conteudo=conteudo,
            timestamp=ts,
            normas_citadas=normas_citadas or [],
            hash_integridade=hash_val,
        )


@dataclass
class DecisaoFinal:
    """Decisão fundamentada do juiz no final da audiência."""
    sumario: str
    fundamentacao: str
    normas_aplicadas: list[str]
    dispositivo: str        # a decisão em si (condenatório/absolutório/etc.)
    recursos_possiveis: list[str]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # V2 — princípio da adesão (art. 71.º CPP): decisão do pedido civil enxertado
    dispositivo_civil: str = ""            # decisão sobre a indemnização (se houver adesão)
    factos_provados: list[str] = field(default_factory=list)      # matéria de facto
    factos_nao_provados: list[str] = field(default_factory=list)


@dataclass
class Audiencia:
    """
    Audiência completa — contém todas as rondas e intervenções.
    """
    id: str
    processo_id: Optional[str]
    tipo: TipoAudiencia
    descricao_caso: str
    tipo_processo: str          # laboral | penal | civil | etc.
    agentes: list[ConfiguracaoAgente]
    estado: EstadoAudiencia
    criada_em: datetime
    iniciada_em: Optional[datetime]
    concluida_em: Optional[datetime]
    intervencoes: list[Intervencao] = field(default_factory=list)
    decisao: Optional[DecisaoFinal] = None
    num_rondas_max: int = 3     # Máximo de rondas de debate
    ronda_actual: int = 0
    criada_por: str = ""

    def intervencoes_por_ronda(self, ronda: int) -> list[Intervencao]:
        return [i for i in self.intervencoes if i.ronda == ronda]

    def ultima_intervencao_de(self, papel: PapelAgente) -> Optional[Intervencao]:
        for i in reversed(self.intervencoes):
            if i.papel == papel:
                return i
        return None

    def resumo_para_contexto(self, max_intervencoes: int = 10) -> str:
        """Gera um resumo das últimas intervenções para contexto dos agentes."""
        ultimas = self.intervencoes[-max_intervencoes:]
        linhas = []
        for iv in ultimas:
            linhas.append(f"[{iv.papel.value.upper()}] {iv.conteudo[:300]}")
        return "\n\n".join(linhas)
