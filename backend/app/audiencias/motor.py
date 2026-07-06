"""
Motor de Audiências do SNAJI — Fase 3 (V2, Especificação V8 §7).

MODELO PROCESSUAL:
─────────────────
Qualquer pessoa pode iniciar (vítima, lesado, advogado, MP).
O processo tem fases ordenadas com loop de contraditório.
Cada fase tem participantes definidos; o juiz só decide quando
TODAS as partes tiveram oportunidade de falar.

FASES (sequência penal — a civil não tem a fase 8):
───────────────────────────────────────────────────
1. ABERTURA              — Juiz abre; escrivão lavra ata; intérprete ajuramentado
2. ACUSAÇÃO/PEDIDO       — MP/autor; assistente pode aderir; pedido civil enxertado
3. DEFESA                — A defesa nunca está ausente (defensor oficioso)
4. RÉPLICA               — Uma vez
5. PRODUÇÃO DE PROVA     — Testemunhas da ACUSAÇÃO primeiro, depois da DEFESA;
                           peritos; declarações do arguido (se as quiser prestar)
6. PERGUNTAS DO JUIZ     — Loop de contraditório até esclarecimento
7. ALEGAÇÕES FINAIS      — ORDEM LEGAL: MP → Assistente → Demandante civil → Defesa
                           (a defesa fala SEMPRE em último)
8. ÚLTIMAS DECLARAÇÕES   — Art. 361.º CPP: o arguido tem sempre a última palavra
9. DELIBERAÇÃO           — Juiz (interno)
10. DECISÃO              — Sentença: matéria de facto separada da matéria de direito;
                           em regime de adesão, decisão penal + indemnizatória

REGIMES DE CASOS MISTOS (§7.4):
- adesao: pedido civil dentro do processo penal (art. 71.º CPP)
- paralelo / prejudicial: geridos ao nível do processo (workflow)

O escrivão lavra ata de cada ato — cada ata inclui o hash da ata anterior,
formando uma cadeia de integridade verificável.
"""

from __future__ import annotations
import uuid
import hashlib
import json as _json
import re as _re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import structlog

from app.audiencias.modelos import (
    Audiencia, TipoAudiencia, EstadoAudiencia, PapelAgente,
    TipoIntervencao, Intervencao, DecisaoFinal, ConfiguracaoAgente
)
from app.agents.agentes import (
    AgenteFabrica, gerar_argumento_stub, extrair_normas_citadas,
    INSTRUCOES_AGENTES
)
from app.rag.motor import RAGJuridico, ValidadorCitacoes

logger = structlog.get_logger(__name__)


class FaseAudiencia(str, Enum):
    """Fases reais de uma audiência portuguesa."""
    ABERTURA             = "abertura"
    ACUSACAO_PEDIDO      = "acusacao_pedido"
    DEFESA               = "defesa"
    REPLICA              = "replica"
    PROVA                = "prova"
    PERGUNTAS_JUIZ       = "perguntas_juiz"
    ALEGACOES_FINAIS     = "alegacoes_finais"
    ULTIMAS_DECLARACOES  = "ultimas_declaracoes"   # V2 — art. 361.º CPP (só penal)
    DELIBERACAO          = "deliberacao"
    DECISAO              = "decisao"


# Ordem legal das fases — civil (retrocompatível com a V1)
ORDEM_FASES_AUDIENCIA = [
    FaseAudiencia.ABERTURA,
    FaseAudiencia.ACUSACAO_PEDIDO,
    FaseAudiencia.DEFESA,
    FaseAudiencia.REPLICA,
    FaseAudiencia.PROVA,
    FaseAudiencia.PERGUNTAS_JUIZ,
    FaseAudiencia.ALEGACOES_FINAIS,
    FaseAudiencia.DELIBERACAO,
    FaseAudiencia.DECISAO,
]

# Ordem legal das fases — penal (inclui as últimas declarações do arguido)
ORDEM_FASES_PENAL = [
    FaseAudiencia.ABERTURA,
    FaseAudiencia.ACUSACAO_PEDIDO,
    FaseAudiencia.DEFESA,
    FaseAudiencia.REPLICA,
    FaseAudiencia.PROVA,
    FaseAudiencia.PERGUNTAS_JUIZ,
    FaseAudiencia.ALEGACOES_FINAIS,
    FaseAudiencia.ULTIMAS_DECLARACOES,
    FaseAudiencia.DELIBERACAO,
    FaseAudiencia.DECISAO,
]

# Quais papéis podem falar em cada fase (o escrivão nunca argumenta;
# o intérprete é transversal e tratado à parte)
PAPEIS_POR_FASE: dict[FaseAudiencia, list[PapelAgente]] = {
    FaseAudiencia.ABERTURA:            [PapelAgente.JUIZ],
    FaseAudiencia.ACUSACAO_PEDIDO:     [PapelAgente.ACUSACAO, PapelAgente.ASSISTENTE,
                                        PapelAgente.DEMANDANTE_CIVIL],
    FaseAudiencia.DEFESA:              [PapelAgente.DEFESA, PapelAgente.DEMANDADO_CIVIL],
    FaseAudiencia.REPLICA:             [PapelAgente.ACUSACAO, PapelAgente.ASSISTENTE],
    FaseAudiencia.PROVA:               [PapelAgente.ACUSACAO, PapelAgente.DEFESA,
                                        PapelAgente.PERITO, PapelAgente.TESTEMUNHA,
                                        PapelAgente.ARGUIDO, PapelAgente.JUIZ,
                                        PapelAgente.DEMANDANTE_CIVIL, PapelAgente.DEMANDADO_CIVIL],
    FaseAudiencia.PERGUNTAS_JUIZ:      [PapelAgente.JUIZ, PapelAgente.ACUSACAO,
                                        PapelAgente.DEFESA, PapelAgente.PERITO,
                                        PapelAgente.TESTEMUNHA, PapelAgente.ARGUIDO],
    FaseAudiencia.ALEGACOES_FINAIS:    [PapelAgente.ACUSACAO, PapelAgente.DEFESA,
                                        PapelAgente.ASSISTENTE, PapelAgente.DEMANDANTE_CIVIL],
    FaseAudiencia.ULTIMAS_DECLARACOES: [PapelAgente.ARGUIDO],
    FaseAudiencia.DELIBERACAO:         [PapelAgente.JUIZ],
    FaseAudiencia.DECISAO:             [PapelAgente.JUIZ],
}

DESCRICAO_FASES: dict[FaseAudiencia, str] = {
    FaseAudiencia.ABERTURA:            "O juiz abre a audiência, identifica as partes e define o objecto do litígio. O escrivão lavra a ata; havendo intérprete, é ajuramentado.",
    FaseAudiencia.ACUSACAO_PEDIDO:     "A parte que iniciou o processo apresenta os factos e os pedidos. O assistente pode aderir à acusação; o pedido de indemnização civil é deduzido aqui (art. 71.º CPP).",
    FaseAudiencia.DEFESA:              "A parte contrária responde e apresenta a sua versão. A defesa nunca está ausente — na falta de mandatário, intervém defensor oficioso.",
    FaseAudiencia.REPLICA:             "A parte autora pode responder aos argumentos da defesa (uma única vez).",
    FaseAudiencia.PROVA:               "Produção de prova: depõem primeiro as testemunhas da acusação, depois as da defesa; peritos esclarecem; o arguido pode prestar declarações (direito ao silêncio, sem desfavor).",
    FaseAudiencia.PERGUNTAS_JUIZ:      "O juiz esclarece dúvidas. Pode dirigir questões a qualquer parte, testemunha, perito ou ao arguido.",
    FaseAudiencia.ALEGACOES_FINAIS:    "Alegações finais pela ordem legal: acusação → assistente → demandante civil → defesa. A defesa fala sempre em último.",
    FaseAudiencia.ULTIMAS_DECLARACOES: "Art. 361.º do CPP: antes da deliberação, o juiz pergunta ao arguido se tem mais alguma coisa a alegar em sua defesa. O arguido tem sempre a última palavra (pode prescindir).",
    FaseAudiencia.DELIBERACAO:         "O juiz delibera internamente sobre os factos provados e o direito aplicável.",
    FaseAudiencia.DECISAO:             "Sentença fundamentada: matéria de facto (provados/não provados) separada da matéria de direito. Em regime de adesão, decide também o pedido de indemnização civil.",
}

# Ordem legal das alegações finais (a defesa fala sempre em último)
ORDEM_ALEGACOES_FINAIS = [
    PapelAgente.ACUSACAO,
    PapelAgente.ASSISTENTE,
    PapelAgente.DEMANDANTE_CIVIL,
    PapelAgente.DEFESA,
]

# Instruções de sistema dos novos papéis (fundidas nas existentes)
_INSTRUCOES_V2: dict[PapelAgente, str] = {
    PapelAgente.ARGUIDO: (
        "És o arguido nesta audiência do Tribunal Português. Falas na primeira pessoa, "
        "com linguagem simples e humana. Tens direito ao silêncio — o seu exercício "
        "nunca te pode desfavorecer. Nas últimas declarações (art. 361.º CPP), diriges-te "
        "diretamente ao tribunal. Nunca inventes factos que não estejam no processo."
    ),
    PapelAgente.TESTEMUNHA: (
        "És uma testemunha ajuramentada nesta audiência. Depões apenas sobre factos de que "
        "tenhas conhecimento direto — o que viste, ouviste ou presenciaste. Não emites opiniões "
        "jurídicas nem conclusões. Se não sabes, dizes que não sabes. Falas na primeira pessoa, "
        "de forma factual e concreta."
    ),
    PapelAgente.DEMANDANTE_CIVIL: (
        "És o mandatário do demandante civil — o lesado que deduziu pedido de indemnização "
        "enxertado no processo penal (art. 71.º CPP). Fundamentas o pedido nos danos patrimoniais "
        "e não patrimoniais (arts. 483.º, 496.º e 562.º e ss. do CC), quantificando-os com base "
        "na prova produzida. Citas sempre os artigos exactos."
    ),
    PapelAgente.DEMANDADO_CIVIL: (
        "És o mandatário do demandado civil no pedido de indemnização enxertado. Contestas os "
        "pressupostos da responsabilidade civil (facto, ilicitude, culpa, dano, nexo de causalidade — "
        "art. 483.º CC) e o quantum indemnizatório. Citas sempre os artigos exactos."
    ),
    PapelAgente.ESCRIVAO: (
        "És o escrivão/oficial de justiça. Lavras a ata de cada ato processual de forma neutra, "
        "factual e sucinta: quem interveio, em que fase, com que objeto. Nunca argumentas nem "
        "opinas. A ata é o registo oficial e auditável da audiência."
    ),
    PapelAgente.INTERPRETE: (
        "És o intérprete ajuramentado (art. 92.º CPP). Traduzes fielmente, sem acrescentar, "
        "omitir ou comentar. Assinalas quando um termo não tem tradução direta."
    ),
}
INSTRUCOES_AGENTES.update(_INSTRUCOES_V2)


@dataclass
class Prova:
    """Uma prova apresentada por uma das partes."""
    id: str
    audiencia_id: str
    apresentada_por: PapelAgente
    tipo: str           # "documento" | "pericia" | "testemunho" | "video" | "imagem"
    descricao: str
    conteudo_texto: str  # texto extraído ou descrição
    nome_ficheiro: Optional[str]
    timestamp: datetime
    hash_integridade: str

    @classmethod
    def criar(
        cls,
        audiencia_id: str,
        apresentada_por: PapelAgente,
        tipo: str,
        descricao: str,
        conteudo_texto: str,
        nome_ficheiro: Optional[str] = None,
    ) -> "Prova":
        pid = str(uuid.uuid4())
        ts = datetime.now(timezone.utc)
        h = hashlib.sha256(f"{pid}|{conteudo_texto}".encode()).hexdigest()
        return cls(
            id=pid, audiencia_id=audiencia_id,
            apresentada_por=apresentada_por, tipo=tipo,
            descricao=descricao, conteudo_texto=conteudo_texto,
            nome_ficheiro=nome_ficheiro, timestamp=ts, hash_integridade=h,
        )


@dataclass
class AudienciaCompleta:
    """
    Audiência completa com fases, provas e loop contraditório.
    Estrutura central da Fase 3 (V2).
    """
    id: str
    processo_id: Optional[str]
    tipo: TipoAudiencia
    descricao_caso: str
    tipo_processo: str
    estado: EstadoAudiencia
    fase_actual: FaseAudiencia
    criada_por: str            # user_id de quem criou
    papel_criador: PapelAgente # papel processual de quem criou
    criada_em: datetime
    iniciada_em: Optional[datetime]
    concluida_em: Optional[datetime]
    participantes: list[ConfiguracaoAgente]
    intervencoes: list[Intervencao]
    provas: list[Prova]
    decisao: Optional[DecisaoFinal]
    num_loops_contraditorio: int
    max_loops_contraditorio: int
    aguarda_intervencao_de: Optional[PapelAgente]
    notas_juiz: list[str]
    # ── Campos V2 (com defaults — retrocompatível) ──
    areas: list[str] = field(default_factory=list)       # ["penal", "civil"] em casos mistos
    regime: str = ""                                     # "adesao" | "" (§7.4)
    ordem_fases: list[FaseAudiencia] = field(default_factory=lambda: list(ORDEM_FASES_AUDIENCIA))
    alegacoes_pendentes: list[PapelAgente] = field(default_factory=list)
    hash_ultima_ata: str = ""                            # cadeia de integridade das atas

    def papeis_activos(self) -> list[PapelAgente]:
        return [p.papel for p in self.participantes if p.activo]

    def tem_papel(self, papel: PapelAgente) -> bool:
        return papel in self.papeis_activos()

    # Papéis que nunca APRESENTAM provas: o juiz ordena diligências (não é parte),
    # o escrivão documenta e o intérprete traduz — igualdade de armas é entre as partes.
    PAPEIS_SEM_PROVA = (PapelAgente.JUIZ, PapelAgente.ESCRIVAO, PapelAgente.INTERPRETE)

    def pode_apresentar_prova(self, papel: PapelAgente) -> bool:
        return (
            self.fase_actual in (FaseAudiencia.PROVA, FaseAudiencia.PERGUNTAS_JUIZ)
            and papel in self.papeis_activos()
            and papel not in self.PAPEIS_SEM_PROVA
        )

    def provas_de(self, papel: PapelAgente) -> list[Prova]:
        return [p for p in self.provas if p.apresentada_por == papel]

    def resumo_provas(self) -> str:
        if not self.provas:
            return "Nenhuma prova apresentada até ao momento."
        linhas = []
        for p in self.provas:
            linhas.append(f"[PROVA — {p.apresentada_por.value.upper()}] {p.tipo}: {p.descricao}")
        return "\n".join(linhas)

    def atas(self) -> list[Intervencao]:
        return [iv for iv in self.intervencoes if iv.tipo == TipoIntervencao.ATA]

    def verificar_cadeia_atas(self) -> bool:
        """Verifica a cadeia de integridade das atas (cada ata cita o hash da anterior)."""
        anterior = ""
        for ata in self.atas():
            marca = f"[hash da ata anterior: {anterior or 'genesis'}]"
            if marca not in ata.conteudo:
                return False
            anterior = ata.hash_integridade
        return True

    def contexto_completo(self) -> str:
        """Gera contexto completo da audiência para os agentes."""
        partes = []
        partes.append(f"CASO: {self.descricao_caso}")
        partes.append(f"TIPO: {self.tipo_processo}"
                      + (f" (áreas: {', '.join(self.areas)}; regime: {self.regime})" if self.regime else ""))
        partes.append(f"FASE ACTUAL: {DESCRICAO_FASES.get(self.fase_actual, '')}")
        if self.provas:
            partes.append(f"\nPROVAS APRESENTADAS:\n{self.resumo_provas()}")
        if self.intervencoes:
            ultimas = [iv for iv in self.intervencoes if iv.tipo != TipoIntervencao.ATA][-8:]
            partes.append("\nÚLTIMAS INTERVENÇÕES:")
            for iv in ultimas:
                partes.append(f"[{iv.papel.value.upper()}] {iv.conteudo[:250]}")
        return "\n\n".join(partes)


class MotorAudiencias:
    """
    Gere o ciclo de vida completo de uma audiência (V2).

    Responsabilidades:
    - Criar audiências com os participantes processuais corretos
      (incluindo escrivão sempre, arguido no penal, partes civis na adesão,
      defensor oficioso quando a defesa falte, intérprete quando pedido)
    - Gerir as transições entre fases pela ordem legal (penal vs. civil)
    - Impor a ordem legal das alegações finais (defesa em último)
    - Garantir a fase das últimas declarações do arguido (art. 361.º CPP)
    - Lavrar ata de cada ato com cadeia de integridade
    - Gerar a decisão final fundamentada (facto e direito separados;
      dispositivo civil em regime de adesão)
    """

    MODELO = "claude-sonnet-4-20250514"
    MAX_TOKENS = 4000
    MAX_CONTINUACOES = 4

    def __init__(self, llm_client=None):
        self._audiencias: dict[str, AudienciaCompleta] = {}
        self._llm = llm_client
        self._rag = RAGJuridico()
        self._validator = ValidadorCitacoes()
        logger.info("motor.audiencias.init", llm=llm_client is not None, versao="v2")

    # ── Criação ─────────────────────────────────────────────────────────────

    def criar_audiencia(
        self,
        descricao_caso: str,
        tipo_processo: str,
        tipo_audiencia: TipoAudiencia,
        criado_por: str,
        papel_criador: PapelAgente,
        processo_id: Optional[str] = None,
        com_perito: bool = False,
        max_loops: int = 3,
        areas: Optional[list[str]] = None,
        com_interprete: bool = False,
        com_testemunhas: bool = True,
    ) -> AudienciaCompleta:
        """
        Cria uma audiência. Qualquer papel pode iniciar.

        V2:
        - `areas`: lista de áreas do caso (ex.: ["penal", "civil"]). Se penal+civil,
          ativa o regime de adesão (art. 71.º CPP) com demandante/demandado civil.
        - Escrivão é sempre constituído (lavra as atas).
        - No penal, o arguido é sempre participante (últimas declarações).
        - Se a defesa não existir, é nomeado defensor oficioso — a defesa nunca falta.
        """
        aid = str(uuid.uuid4())
        areas = [a.lower() for a in (areas or [tipo_processo])]
        eh_penal = "penal" in areas or tipo_processo == "penal"
        regime = "adesao" if (eh_penal and any(a in areas for a in ("civil", "consumo", "laboral")) and len(set(areas)) > 1) else ""

        # Participantes base conforme o tipo (V1, preservado)
        if tipo_audiencia in (TipoAudiencia.JULGAMENTO, TipoAudiencia.AUDIENCIA_PRELIMINAR):
            participantes = AgenteFabrica.criar_agentes_julgamento(
                tipo_processo, com_perito=com_perito
            )
        else:
            participantes = AgenteFabrica.criar_agentes_contraditorio(tipo_processo)
            participantes.insert(0, ConfiguracaoAgente(
                papel=PapelAgente.JUIZ, nome="Juiz Presidente",
                instrucoes_sistema=INSTRUCOES_AGENTES[PapelAgente.JUIZ],
            ))

        # ── Participantes V2 ──
        papeis = {p.papel for p in participantes if p.activo}

        # Defensor oficioso: a defesa NUNCA está ausente
        if PapelAgente.DEFESA not in papeis:
            participantes.append(ConfiguracaoAgente(
                papel=PapelAgente.DEFESA, nome="Defensor Oficioso (nomeado)",
                instrucoes_sistema=INSTRUCOES_AGENTES[PapelAgente.DEFESA],
            ))
            logger.info("audiencia.defensor_oficioso_nomeado", id=aid)

        # Escrivão: sempre presente (nunca argumenta; lavra as atas)
        participantes.append(ConfiguracaoAgente(
            papel=PapelAgente.ESCRIVAO, nome="Escrivão de Direito",
            instrucoes_sistema=INSTRUCOES_AGENTES[PapelAgente.ESCRIVAO],
        ))

        if eh_penal:
            participantes.append(ConfiguracaoAgente(
                papel=PapelAgente.ARGUIDO, nome="Arguido",
                instrucoes_sistema=INSTRUCOES_AGENTES[PapelAgente.ARGUIDO],
            ))

        if com_testemunhas:
            participantes.append(ConfiguracaoAgente(
                papel=PapelAgente.TESTEMUNHA, nome="Testemunhas arroladas",
                instrucoes_sistema=INSTRUCOES_AGENTES[PapelAgente.TESTEMUNHA],
            ))

        if regime == "adesao":
            participantes.append(ConfiguracaoAgente(
                papel=PapelAgente.DEMANDANTE_CIVIL, nome="Demandante Civil (lesado)",
                instrucoes_sistema=INSTRUCOES_AGENTES[PapelAgente.DEMANDANTE_CIVIL],
            ))
            participantes.append(ConfiguracaoAgente(
                papel=PapelAgente.DEMANDADO_CIVIL, nome="Demandado Civil",
                instrucoes_sistema=INSTRUCOES_AGENTES[PapelAgente.DEMANDADO_CIVIL],
            ))

        if com_interprete:
            participantes.append(ConfiguracaoAgente(
                papel=PapelAgente.INTERPRETE, nome="Intérprete ajuramentado",
                instrucoes_sistema=INSTRUCOES_AGENTES[PapelAgente.INTERPRETE],
            ))

        a = AudienciaCompleta(
            id=aid, processo_id=processo_id,
            tipo=tipo_audiencia, descricao_caso=descricao_caso,
            tipo_processo=tipo_processo,
            estado=EstadoAudiencia.PENDENTE,
            fase_actual=FaseAudiencia.ABERTURA,
            criada_por=criado_por, papel_criador=papel_criador,
            criada_em=datetime.now(timezone.utc),
            iniciada_em=None, concluida_em=None,
            participantes=participantes,
            intervencoes=[], provas=[],
            decisao=None,
            num_loops_contraditorio=0,
            max_loops_contraditorio=max_loops,
            aguarda_intervencao_de=PapelAgente.JUIZ,
            notas_juiz=[],
            areas=areas,
            regime=regime,
            ordem_fases=list(ORDEM_FASES_PENAL if eh_penal else ORDEM_FASES_AUDIENCIA),
        )
        self._audiencias[aid] = a
        logger.info(
            "audiencia.criada", id=aid, tipo=tipo_audiencia.value,
            papel_criador=papel_criador.value, regime=regime or "simples",
            areas=areas, fases=len(a.ordem_fases),
        )
        return a

    # ── Ata (escrivão) ───────────────────────────────────────────────────────

    def _lavrar_ata(self, a: AudienciaCompleta, resumo: str) -> Intervencao:
        """
        O escrivão lavra a ata do ato. Cada ata inclui o hash da ata anterior,
        formando uma cadeia de integridade verificável (Especificação V8 §7.1).
        """
        conteudo = (
            f"ATA — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} — "
            f"fase '{a.fase_actual.value}': {resumo} "
            f"[hash da ata anterior: {a.hash_ultima_ata or 'genesis'}]"
        )
        ata = Intervencao.criar(
            audiencia_id=a.id,
            ronda=a.num_loops_contraditorio,
            papel=PapelAgente.ESCRIVAO,
            tipo=TipoIntervencao.ATA,
            conteudo=conteudo,
        )
        a.intervencoes.append(ata)
        a.hash_ultima_ata = ata.hash_integridade
        return ata

    # ── Intervenções ─────────────────────────────────────────────────────────

    def papel_sugerido(self, a) -> str:
        """Quem deve falar a seguir, segundo a marcha legal da audiência —
        permite ao ecrã pré-selecionar o papel (o utilizador pode alterar)."""
        f = a.fase_actual
        F, P = FaseAudiencia, PapelAgente
        estaticos = {
            F.ABERTURA: P.JUIZ, F.ACUSACAO_PEDIDO: P.ACUSACAO, F.DEFESA: P.DEFESA,
            F.REPLICA: P.ACUSACAO, F.PROVA: P.ACUSACAO, F.PERGUNTAS_JUIZ: P.JUIZ,
            F.ULTIMAS_DECLARACOES: P.ARGUIDO, F.DECISAO: P.JUIZ,
        }
        if f == F.ALEGACOES_FINAIS:
            # a lista de pendentes já respeita a ordem legal (defesa em último)
            if a.alegacoes_pendentes:
                return a.alegacoes_pendentes[0].value
            return P.JUIZ.value
        papel = estaticos.get(f, P.JUIZ)
        # garantir que o sugerido participa nesta audiência
        if papel not in a.papeis_activos():
            permitidos = [p for p in PAPEIS_POR_FASE.get(f, []) if p in a.papeis_activos()]
            return permitidos[0].value if permitidos else P.JUIZ.value
        return papel.value

    def processar_intervencao(
        self,
        audiencia_id: str,
        papel: PapelAgente,
        conteudo: str,
        tipo: TipoIntervencao = TipoIntervencao.ALEGACAO,
    ) -> tuple[Intervencao, Optional[str]]:
        """
        Processa uma intervenção de um participante.
        Retorna a intervenção registada e a orientação para o próximo passo.
        """
        a = self._get_audiencia(audiencia_id)

        # O escrivão nunca intervém argumentativamente — as atas são automáticas
        if papel == PapelAgente.ESCRIVAO:
            raise ValueError(
                "O escrivão não produz intervenções argumentativas: as atas são "
                "lavradas automaticamente pelo sistema a cada ato processual."
            )

        # O intérprete é transversal: pode traduzir em qualquer fase, sem avançar fases
        if papel == PapelAgente.INTERPRETE:
            if not a.tem_papel(PapelAgente.INTERPRETE):
                raise ValueError("Não foi constituído intérprete nesta audiência.")
            iv = Intervencao.criar(
                audiencia_id=audiencia_id, ronda=a.num_loops_contraditorio,
                papel=papel, tipo=TipoIntervencao.RESPOSTA, conteudo=conteudo,
            )
            a.intervencoes.append(iv)
            return iv, "Tradução registada. A audiência prossegue na mesma fase."

        # Valida que este papel pode falar nesta fase
        papeis_permitidos = PAPEIS_POR_FASE.get(a.fase_actual, [])
        if papel not in papeis_permitidos:
            raise ValueError(
                f"O papel '{papel.value}' não pode intervir na fase '{a.fase_actual.value}'. "
                f"Papéis permitidos nesta fase: {[p.value for p in papeis_permitidos]}"
            )

        # Ordem legal das alegações finais: a defesa fala sempre em último
        if a.fase_actual == FaseAudiencia.ALEGACOES_FINAIS:
            if not a.alegacoes_pendentes:
                a.alegacoes_pendentes = [
                    p for p in ORDEM_ALEGACOES_FINAIS if a.tem_papel(p)
                ]
            proximo = a.alegacoes_pendentes[0]
            if papel != proximo:
                raise ValueError(
                    f"Ordem legal das alegações finais: fala agora '{proximo.value}'. "
                    f"A defesa fala sempre em último. "
                    f"Sequência restante: {[p.value for p in a.alegacoes_pendentes]}"
                )

        # Tipos coerentes com a fase
        if a.fase_actual == FaseAudiencia.ULTIMAS_DECLARACOES:
            tipo = TipoIntervencao.ULTIMAS_DECLARACOES
        elif papel in (PapelAgente.TESTEMUNHA, PapelAgente.ARGUIDO) and a.fase_actual == FaseAudiencia.PROVA:
            tipo = TipoIntervencao.DEPOIMENTO

        normas = extrair_normas_citadas(conteudo)
        iv = Intervencao.criar(
            audiencia_id=audiencia_id,
            ronda=a.num_loops_contraditorio,
            papel=papel,
            tipo=tipo,
            conteudo=conteudo,
            normas_citadas=normas,
        )
        a.intervencoes.append(iv)

        if a.estado == EstadoAudiencia.PENDENTE:
            a.estado = EstadoAudiencia.EM_CURSO
            a.iniciada_em = datetime.now(timezone.utc)

        orientacao = self._determinar_proximo_passo(a, papel, tipo)
        logger.info("intervencao.processada", audiencia_id=audiencia_id,
                    papel=papel.value, fase=a.fase_actual.value)
        return iv, orientacao

    # ── Máquina de fases ─────────────────────────────────────────────────────

    def _avancar_para(self, a: AudienciaCompleta, fase: FaseAudiencia, resumo_ata: str) -> None:
        self._lavrar_ata(a, resumo_ata)
        a.fase_actual = fase

    def _determinar_proximo_passo(
        self, a: AudienciaCompleta, ultimo_papel: PapelAgente, tipo: TipoIntervencao
    ) -> str:
        """
        Decide quem fala a seguir e se a fase avança, pela ordem legal
        da audiência (penal ou civil). Implementa o loop contraditório.
        """
        fase = a.fase_actual
        eh_penal = FaseAudiencia.ULTIMAS_DECLARACOES in a.ordem_fases

        if fase == FaseAudiencia.ABERTURA:
            nota_interprete = (
                " O intérprete foi ajuramentado (art. 92.º CPP)."
                if a.tem_papel(PapelAgente.INTERPRETE) else ""
            )
            self._avancar_para(a, FaseAudiencia.ACUSACAO_PEDIDO,
                               "abertura da audiência; identificação das partes." + nota_interprete)
            a.aguarda_intervencao_de = PapelAgente.ACUSACAO
            extra = (" O pedido de indemnização civil pode ser deduzido nesta fase "
                     "(princípio da adesão, art. 71.º CPP)." if a.regime == "adesao" else "")
            return ("O juiz abriu a audiência. A acusação/parte autora apresenta agora "
                    "os factos e pedidos." + extra + nota_interprete)

        if fase == FaseAudiencia.ACUSACAO_PEDIDO:
            # O assistente e o demandante civil podem ainda intervir nesta fase;
            # a fase avança quando a ACUSAÇÃO (titular) já falou.
            if ultimo_papel in (PapelAgente.ASSISTENTE, PapelAgente.DEMANDANTE_CIVIL):
                return ("Intervenção registada. A acusação conclui a apresentação "
                        "para a fase seguir para a defesa.")
            self._avancar_para(a, FaseAudiencia.DEFESA, "apresentação da acusação/pedido.")
            a.aguarda_intervencao_de = PapelAgente.DEFESA
            return "A acusação apresentou o seu caso. A defesa pode agora responder."

        if fase == FaseAudiencia.DEFESA:
            if ultimo_papel == PapelAgente.DEMANDADO_CIVIL:
                return "Contestação civil registada. A defesa conclui para a fase avançar."
            self._avancar_para(a, FaseAudiencia.REPLICA, "contestação da defesa.")
            a.aguarda_intervencao_de = PapelAgente.ACUSACAO
            return "A defesa respondeu. A acusação pode apresentar réplica (uma vez)."

        if fase == FaseAudiencia.REPLICA:
            self._avancar_para(a, FaseAudiencia.PROVA, "réplica da acusação.")
            a.aguarda_intervencao_de = None
            return ("Fase de produção de prova. Depõem primeiro as testemunhas da "
                    "acusação, depois as da defesa; seguem-se peritos e, querendo, "
                    "as declarações do arguido (direito ao silêncio, sem desfavor).")

        if fase == FaseAudiencia.PROVA:
            # Depoimentos e perícias não fecham a prova — pode haver vários.
            if ultimo_papel in (PapelAgente.TESTEMUNHA, PapelAgente.PERITO, PapelAgente.ARGUIDO):
                return ("Depoimento registado. Podem seguir-se mais depoimentos ou provas; "
                        "quando qualquer das partes ou o juiz encerrar a produção de prova, "
                        "passa-se às perguntas do juiz.")
            self._avancar_para(a, FaseAudiencia.PERGUNTAS_JUIZ, "encerramento da produção de prova.")
            a.aguarda_intervencao_de = PapelAgente.JUIZ
            return "O juiz pode agora colocar questões para esclarecimento."

        if fase == FaseAudiencia.PERGUNTAS_JUIZ:
            if a.num_loops_contraditorio < a.max_loops_contraditorio and ultimo_papel == PapelAgente.JUIZ:
                a.num_loops_contraditorio += 1
                self._avancar_para(a, FaseAudiencia.DEFESA,
                                   f"o juiz determinou novo contraditório (ronda {a.num_loops_contraditorio}).")
                a.aguarda_intervencao_de = PapelAgente.DEFESA
                return (f"O juiz solicitou mais esclarecimentos "
                        f"(loop {a.num_loops_contraditorio}/{a.max_loops_contraditorio}). "
                        f"A defesa pode complementar os seus argumentos.")
            a.alegacoes_pendentes = [p for p in ORDEM_ALEGACOES_FINAIS if a.tem_papel(p)]
            self._avancar_para(a, FaseAudiencia.ALEGACOES_FINAIS, "esclarecimentos concluídos.")
            a.aguarda_intervencao_de = a.alegacoes_pendentes[0] if a.alegacoes_pendentes else PapelAgente.ACUSACAO
            ordem = " → ".join(p.value for p in a.alegacoes_pendentes)
            return f"Alegações finais pela ordem legal: {ordem}. A defesa fala sempre em último."

        if fase == FaseAudiencia.ALEGACOES_FINAIS:
            if a.alegacoes_pendentes and a.alegacoes_pendentes[0] == ultimo_papel:
                a.alegacoes_pendentes.pop(0)
            if a.alegacoes_pendentes:
                proximo = a.alegacoes_pendentes[0]
                a.aguarda_intervencao_de = proximo
                return f"Alegações de '{ultimo_papel.value}' registadas. Fala agora '{proximo.value}'."
            if eh_penal and a.tem_papel(PapelAgente.ARGUIDO):
                self._avancar_para(a, FaseAudiencia.ULTIMAS_DECLARACOES, "alegações finais concluídas.")
                a.aguarda_intervencao_de = PapelAgente.ARGUIDO
                return ("Nos termos do art. 361.º do CPP, o tribunal pergunta ao arguido "
                        "se tem mais alguma coisa a alegar em sua defesa. O arguido tem "
                        "a última palavra (pode prescindir).")
            self._avancar_para(a, FaseAudiencia.DELIBERACAO, "alegações finais concluídas.")
            a.aguarda_intervencao_de = PapelAgente.JUIZ
            return "Todas as partes falaram. O juiz vai deliberar. Aguarde a decisão."

        if fase == FaseAudiencia.ULTIMAS_DECLARACOES:
            self._avancar_para(a, FaseAudiencia.DELIBERACAO,
                               "últimas declarações do arguido (art. 361.º CPP).")
            a.aguarda_intervencao_de = PapelAgente.JUIZ
            return "O arguido foi ouvido em último lugar. O juiz vai deliberar."

        if fase == FaseAudiencia.DELIBERACAO:
            self._avancar_para(a, FaseAudiencia.DECISAO, "deliberação concluída.")
            a.aguarda_intervencao_de = PapelAgente.JUIZ
            return "O juiz está pronto para proferir a decisão."

        return "Audiência em curso."

    # ── Geração automática de intervenções (modo IA) ─────────────────────────

    def gerar_intervencao_automatica(
        self,
        audiencia_id: str,
        papel: PapelAgente,
    ) -> Intervencao:
        """Gera automaticamente uma intervenção (LLM se disponível, stub senão)."""
        a = self._get_audiencia(audiencia_id)
        contexto = a.contexto_completo()

        if self._llm is not None:
            conteudo = self._gerar_com_llm(a, papel, contexto)
        else:
            conteudo = self._stub_intervencao(a, papel)

        iv, _ = self.processar_intervencao(audiencia_id, papel, conteudo)
        return iv

    def _stub_intervencao(self, a: AudienciaCompleta, papel: PapelAgente) -> str:
        stubs_v2 = {
            PapelAgente.ARGUIDO: (
                "Senhor Doutor Juiz, mantenho o que declarei. Lamento a situação e "
                "peço que seja tida em conta a minha colaboração com o tribunal. "
                "Nada mais tenho a alegar."
            ),
            PapelAgente.TESTEMUNHA: (
                "Sob juramento: presenciei os factos descritos. Confirmo o que consta "
                "da descrição do caso, de conhecimento direto, sem opinar sobre o direito."
            ),
            PapelAgente.DEMANDANTE_CIVIL: (
                "Deduz-se pedido de indemnização civil pelos danos patrimoniais e não "
                "patrimoniais sofridos, nos termos dos arts. 483.º e 496.º do CC e do "
                "art. 71.º do CPP, em montante a fixar segundo a prova produzida."
            ),
            PapelAgente.DEMANDADO_CIVIL: (
                "Contesta-se o pedido cível: não se verificam preenchidos os pressupostos "
                "do art. 483.º do CC, impugnando-se ainda o quantum indemnizatório peticionado."
            ),
        }
        if papel in stubs_v2:
            return stubs_v2[papel]
        return gerar_argumento_stub(a.tipo_processo, papel, a.num_loops_contraditorio)

    def _chamar_llm_completo(self, system: str, prompt: str) -> str:
        """Chamada LLM com anti-corte: continua até terminação natural (V8 §6)."""
        mensagens = [{"role": "user", "content": prompt}]
        partes: list[str] = []
        for i in range(self.MAX_CONTINUACOES + 1):
            msg = self._llm.messages.create(
                model=self.MODELO, max_tokens=self.MAX_TOKENS,
                system=system, messages=mensagens,
            )
            texto = "".join(b.text for b in msg.content if getattr(b, "text", None))
            partes.append(texto)
            if getattr(msg, "stop_reason", "end_turn") != "max_tokens":
                break
            logger.info("audiencias.llm.continuacao", iteracao=i + 1)
            mensagens = mensagens + [
                {"role": "assistant", "content": texto},
                {"role": "user", "content": "Continua exatamente de onde paraste, sem repetir nada."},
            ]
        return "".join(partes).strip()

    def _gerar_com_llm(self, a: AudienciaCompleta, papel: PapelAgente, contexto: str) -> str:
        normas_rag = self._rag.search(a.descricao_caso, top_k=5)
        normas_txt = "\n".join(
            f"• Art. {c.artigo}.º {c.diploma} — {c.texto[:150]}"
            for c in normas_rag
        )
        prompt = f"""CONTEXTO DA AUDIÊNCIA:
{contexto}

NORMAS RELEVANTES DO CORPUS JURÍDICO PORTUGUÊS:
{normas_txt}

FASE ACTUAL: {DESCRICAO_FASES.get(a.fase_actual, a.fase_actual.value)}

Produz a tua intervenção como {papel.value}. Sê conciso (máx. 300 palavras).
Cita sempre os artigos exactos das normas fornecidas acima."""
        return self._chamar_llm_completo(INSTRUCOES_AGENTES.get(papel, ""), prompt)

    # ── Provas ───────────────────────────────────────────────────────────────

    def apresentar_prova(
        self,
        audiencia_id: str,
        papel: PapelAgente,
        tipo_prova: str,
        descricao: str,
        conteudo_texto: str,
        nome_ficheiro: Optional[str] = None,
    ) -> Prova:
        """Regista uma prova. Testemunhos da acusação antes dos da defesa."""
        a = self._get_audiencia(audiencia_id)

        if not a.pode_apresentar_prova(papel):
            raise ValueError(
                f"Provas só podem ser apresentadas nas fases de Produção de Prova "
                f"ou Perguntas do Juiz. Fase actual: {a.fase_actual.value}"
            )

        # Ordem legal dos depoimentos: acusação primeiro (aviso, não bloqueio,
        # porque a acusação pode legitimamente não arrolar testemunhas)
        nota = ""
        if tipo_prova == "testemunho" and papel == PapelAgente.DEFESA:
            acusacao_tem = any(
                p.tipo == "testemunho" and p.apresentada_por in
                (PapelAgente.ACUSACAO, PapelAgente.ASSISTENTE)
                for p in a.provas
            )
            if not acusacao_tem:
                nota = (" [NOTA DE ORDEM: em regra, depõem primeiro as testemunhas "
                        "da acusação — registado que a acusação não arrolou ou prescindiu.]")

        prova = Prova.criar(
            audiencia_id=audiencia_id,
            apresentada_por=papel,
            tipo=tipo_prova,
            descricao=descricao + nota,
            conteudo_texto=conteudo_texto,
            nome_ficheiro=nome_ficheiro,
        )
        a.provas.append(prova)

        iv = Intervencao.criar(
            audiencia_id=audiencia_id,
            ronda=a.num_loops_contraditorio,
            papel=papel,
            tipo=TipoIntervencao.PROVA,
            conteudo=f"[PROVA APRESENTADA] {tipo_prova}: {descricao}{nota}",
            normas_citadas=[],
        )
        a.intervencoes.append(iv)
        self._lavrar_ata(a, f"junção de prova ({tipo_prova}) por {papel.value}.")

        logger.info("prova.apresentada", audiencia_id=audiencia_id,
                    papel=papel.value, tipo=tipo_prova)
        return prova

    # ── Decisão final ────────────────────────────────────────────────────────

    def proferir_decisao(self, audiencia_id: str) -> DecisaoFinal:
        """O juiz profere a decisão final, fundamentada em facto e direito."""
        a = self._get_audiencia(audiencia_id)

        if a.fase_actual != FaseAudiencia.DECISAO:
            raise ValueError(
                f"A decisão só pode ser proferida na fase de Decisão. "
                f"Fase actual: {a.fase_actual.value}"
            )

        if self._llm is not None:
            decisao = self._gerar_decisao_llm(a)
        else:
            decisao = self._gerar_decisao_stub(a)

        a.decisao = decisao
        a.estado = EstadoAudiencia.CONCLUIDA
        a.concluida_em = datetime.now(timezone.utc)

        conteudo_iv = decisao.dispositivo + (
            f"\n\nPEDIDO CIVIL (adesão, art. 71.º CPP): {decisao.dispositivo_civil}"
            if decisao.dispositivo_civil else ""
        )
        iv = Intervencao.criar(
            audiencia_id=audiencia_id,
            ronda=a.num_loops_contraditorio,
            papel=PapelAgente.JUIZ,
            tipo=TipoIntervencao.DECISAO_FINAL,
            conteudo=conteudo_iv,
            normas_citadas=decisao.normas_aplicadas,
        )
        a.intervencoes.append(iv)
        self._lavrar_ata(a, "leitura da sentença; depósito na secretaria.")

        logger.info("decisao.proferida", audiencia_id=audiencia_id, estado="concluida",
                    com_civil=bool(decisao.dispositivo_civil))
        return decisao

    def _gerar_decisao_llm(self, a: AudienciaCompleta) -> DecisaoFinal:
        normas_rag = self._rag.search(a.descricao_caso, top_k=6)
        normas_txt = "\n".join(f"• Art. {c.artigo}.º {c.diploma} — {c.texto[:200]}" for c in normas_rag)
        pede_civil = (
            '\n  "dispositivo_civil": "decisão sobre o pedido de indemnização civil enxertado",'
            if a.regime == "adesao" else ""
        )
        prompt = f"""AUDIÊNCIA COMPLETA:
{a.contexto_completo()}

PROVAS APRESENTADAS:
{a.resumo_provas()}

NORMAS APLICÁVEIS:
{normas_txt}

Profere a SENTENÇA final, separando matéria de facto e matéria de direito. Responde em JSON:
{{
  "factos_provados": ["facto 1", "facto 2"],
  "factos_nao_provados": ["facto x"],
  "sumario": "sumário da decisão em 1 frase",
  "fundamentacao": "fundamentação jurídica completa com citações",
  "normas_aplicadas": ["CRP-53", "CT-351"],
  "dispositivo": "texto exacto do dispositivo (condenatório/absolutório/procedente/improcedente)",{pede_civil}
  "recursos_possiveis": ["recurso de apelação", "revista"]
}}"""
        raw = self._chamar_llm_completo(INSTRUCOES_AGENTES[PapelAgente.JUIZ], prompt)
        try:
            dados = _json.loads(_re.sub(r"```json|```", "", raw).strip())
        except Exception:
            m = _re.search(r"\{.*\}", raw, _re.DOTALL)
            dados = _json.loads(m.group()) if m else {}
        return DecisaoFinal(
            sumario=dados.get("sumario", ""),
            fundamentacao=dados.get("fundamentacao", ""),
            normas_aplicadas=dados.get("normas_aplicadas", []),
            dispositivo=dados.get("dispositivo", ""),
            recursos_possiveis=dados.get("recursos_possiveis", []),
            dispositivo_civil=dados.get("dispositivo_civil", ""),
            factos_provados=dados.get("factos_provados", []),
            factos_nao_provados=dados.get("factos_nao_provados", []),
        )

    def _gerar_decisao_stub(self, a: AudienciaCompleta) -> DecisaoFinal:
        """Decisão stub quando o LLM não está disponível."""
        normas_rag = self._rag.search(a.descricao_caso, top_k=3)
        normas_citadas = [f"{c.diploma}-{c.artigo}" for c in normas_rag]
        tipo = a.tipo_processo

        dispositivos = {
            "laboral": "O tribunal julga a acção PROCEDENTE. O despedimento é declarado ilícito por ausência de justa causa (Art. 351.º CT). A entidade empregadora é condenada a pagar indemnização nos termos do Art. 391.º CT. [NOTA: Decisão gerada em modo stub — activar LLM para análise real dos factos provados]",
            "penal": "O tribunal, após análise da prova produzida e ouvido o arguido em últimas declarações (art. 361.º CPP), delibera sobre a responsabilidade criminal com base nos factos provados e nas normas do Código Penal. [NOTA: Decisão gerada em modo stub — activar LLM para análise real]",
            "civil": "O tribunal julga a acção conforme os factos provados e o direito aplicável, nos termos dos artigos invocados do Código Civil e do Código de Processo Civil. [NOTA: Decisão gerada em modo stub]",
        }
        dispositivo_civil = ""
        if a.regime == "adesao":
            dispositivo_civil = (
                "Quanto ao pedido de indemnização civil enxertado (art. 71.º CPP): "
                "o tribunal decide segundo os pressupostos da responsabilidade civil "
                "(art. 483.º CC) e os danos provados (arts. 496.º e 562.º e ss. CC). "
                "[Modo stub — activar LLM para quantificação real]"
            )

        return DecisaoFinal(
            sumario=f"Decisão na audiência de {tipo} — modo demonstração",
            fundamentacao=(
                f"MATÉRIA DE FACTO: com base nas intervenções produzidas "
                f"({len([i for i in a.intervencoes if i.tipo != TipoIntervencao.ATA])} no total), "
                f"nas {len(a.provas)} prova(s) apresentada(s). "
                f"MATÉRIA DE DIREITO: normas identificadas pelo motor RAG "
                f"({len(normas_rag)} normas relevantes). "
                f"[Para fundamentação completa, activar motor LLM]"
            ),
            normas_aplicadas=normas_citadas,
            dispositivo=dispositivos.get(tipo, dispositivos["civil"]),
            recursos_possiveis=["Recurso de apelação (Art. 638.º CPC)", "Recurso de revista (Art. 671.º CPC)"],
            dispositivo_civil=dispositivo_civil,
            factos_provados=["[modo stub — factos a fixar pelo LLM a partir da prova produzida]"],
            factos_nao_provados=[],
        )

    # ── Consultas ────────────────────────────────────────────────────────────

    def obter_audiencia(self, audiencia_id: str) -> AudienciaCompleta:
        return self._get_audiencia(audiencia_id)

    def listar_audiencias(self, criado_por: Optional[str] = None) -> list[AudienciaCompleta]:
        todas = list(self._audiencias.values())
        if criado_por:
            todas = [a for a in todas if a.criada_por == criado_por]  # fix V1: era a.criado_por
        return sorted(todas, key=lambda a: a.criada_em, reverse=True)

    def _get_audiencia(self, aid: str) -> AudienciaCompleta:
        a = self._audiencias.get(aid)
        if not a:
            raise ValueError(f"Audiência {aid} não encontrada")
        return a


# Instância partilhada
motor_audiencias = MotorAudiencias(llm_client=None)
