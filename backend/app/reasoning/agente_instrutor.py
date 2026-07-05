"""
AgenteInstrutor — SNAJI (Especificação V8, §1)
===============================================
Módulo de instrução do caso ("detective"): substitui a entrada de texto
livre por um diálogo estruturado ANTES da classificação final e do RAG.

Funcionamento (diagnóstico diferencial):
  1. O cidadão descreve o caso livremente.
  2. O agente classifica preliminarmente (ClassificadorJuridico multi-área).
  3. Identifica lacunas de facto (datas, contrato, valores, partes, provas).
  4. Faz UMA pergunta de cada vez — a que mais reduz a incerteza.
  5. Atualiza a classificação após cada resposta.
  6. Termina quando confiança >= limiar OU orçamento de perguntas esgotado.
  7. Produz uma Ficha de Factos estruturada + alertas prioritários.

Tipos de pergunta (versão mista):
  - "escolha": opções clicáveis (o LLM decide quando o espaço de respostas
               é fechado e enumerável). "Não sei" e "Outro / prefiro
               explicar" são acrescentados automaticamente pelo código.
  - "texto":   resposta livre (narrativa, nomes, descrições).
  - "data":    o frontend mostra calendário (normalização de datas).
  - "valor":   campo numérico em euros (alçada, valor da causa).

Salvaguardas:
  - JSON malformado, escolha sem opções ou com >5 opções → degrada para texto.
  - O sistema nunca bloqueia por pergunta mal construída.
  - Anti-corte de frases: verifica stop_reason e pede continuação até
    terminação natural (máx. 4 continuações).

Deontologia (codificada):
  - O agente INFORMA, nunca prescreve. Não diz "deve processar";
    diz "casos com estas características seguem tipicamente a via X".
  - Remete para profissional habilitado e apoio judiciário quando aplicável.

Integração:
  - Corre em modo stub (sem LLM) para testes, com sequência determinística.
  - Com LLM: perguntas geradas por compreensão do caso concreto.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, date, timezone, timedelta
from enum import Enum
from typing import Optional

import structlog

from app.reasoning.classificador_juridico import (
    ClassificadorJuridico,
    ClassificacaoJuridica,
    AreaJuridica,
)

logger = structlog.get_logger(__name__)


# ── Ressalva legal (apresentada no início de toda a instrução) ──────────────

RESSALVA_LEGAL = (
    "O SNAJI presta informação jurídica de carácter geral e apoio à "
    "preparação processual. Não presta consulta jurídica nem patrocínio, "
    "atos reservados por lei a advogados e solicitadores (Lei n.º 49/2004). "
    "Nenhum resultado deste sistema substitui o aconselhamento de um "
    "profissional habilitado nem constitui decisão judicial."
)


# ── Enumerações e dataclasses ───────────────────────────────────────────────

class TipoPergunta(str, Enum):
    ESCOLHA = "escolha"
    TEXTO   = "texto"
    DATA    = "data"
    VALOR   = "valor"


OPCAO_NAO_SEI = "Não sei"
OPCAO_OUTRO = "Outro / prefiro explicar"
MAX_OPCOES = 5


@dataclass
class Pergunta:
    id: str
    texto: str
    tipo: TipoPergunta
    objetivo: str = ""                      # porque é que esta pergunta importa
    opcoes: list[str] = field(default_factory=list)
    campo_ficha: str = ""                   # chave normalizada na Ficha de Factos

    def para_frontend(self) -> dict:
        """Formato limpo para o frontend fazer render por tipo."""
        return {
            "id": self.id,
            "texto": self.texto,
            "tipo": self.tipo.value,
            "opcoes": self.opcoes if self.tipo == TipoPergunta.ESCOLHA else [],
        }


@dataclass
class Resposta:
    pergunta_id: str
    valor: str                              # texto, opção escolhida, ISO-date ou número
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class TipoAlerta(str, Enum):
    PROTECAO_URGENTE = "protecao_urgente"
    PRAZO            = "prazo"
    VIA_NAO_JUDICIAL = "via_nao_judicial"
    APOIO_JUDICIARIO = "apoio_judiciario"


class GravidadeAlerta(str, Enum):
    INFORMATIVO = "informativo"
    ATENCAO     = "atencao"
    URGENTE     = "urgente"


@dataclass
class Alerta:
    tipo: TipoAlerta
    gravidade: GravidadeAlerta
    mensagem_tecnica: str                   # registo técnico (advogado/juiz)
    mensagem_cidada: str                    # linguagem clara (cidadão)
    norma_base: str = ""                    # ex.: "CT-387"
    subtipo: str = ""                       # prazos: "expirado" | "em_risco"


@dataclass
class FichaDeFactos:
    """
    Saída estruturada da instrução. É esta ficha — e não o desabafo
    original — que alimenta o RAG e a pipeline de reasoning.
    """
    caso_id: str
    relato_inicial: str
    partes: dict = field(default_factory=dict)          # {"autor": ..., "contraparte": ...}
    cronologia: list[dict] = field(default_factory=list) # [{"data": "2026-04-12", "evento": ...}]
    relacao_juridica: str = ""
    provas: list[str] = field(default_factory=list)
    valores: dict = field(default_factory=dict)          # {"dano_estimado": 1500.0}
    pedidos: list[str] = field(default_factory=list)
    respostas_normalizadas: dict = field(default_factory=dict)  # {"contrato_escrito": "nao"}
    resumo_instrucao: str = ""

    def para_dict(self) -> dict:
        return asdict(self)

    def para_texto_rag(self) -> str:
        """Representação textual da ficha para alimentar o RAG/pipeline."""
        linhas = [f"RELATO INICIAL: {self.relato_inicial}"]
        if self.resumo_instrucao:
            linhas.append(f"RESUMO DA INSTRUÇÃO: {self.resumo_instrucao}")
        for chave, valor in self.respostas_normalizadas.items():
            linhas.append(f"{chave.upper().replace('_', ' ')}: {valor}")
        for evento in self.cronologia:
            linhas.append(f"CRONOLOGIA {evento.get('data', '?')}: {evento.get('evento', '')}")
        if self.provas:
            linhas.append("PROVAS DISPONÍVEIS: " + "; ".join(self.provas))
        return "\n".join(linhas)


@dataclass
class EstadoInstrucao:
    """Estado de uma sessão de instrução (persistível entre pedidos HTTP)."""
    caso_id: str
    relato_inicial: str
    ficha: FichaDeFactos
    classificacao: Optional[ClassificacaoJuridica] = None
    perguntas_feitas: list[Pergunta] = field(default_factory=list)
    respostas: list[Resposta] = field(default_factory=list)
    alertas: list[Alerta] = field(default_factory=list)
    terminado: bool = False
    motivo_fim: str = ""
    via_llm: bool = False


# ── Prazos jurídicos conhecidos (verificação determinística) ────────────────
# NOTA: verificação indicativa. O alerta NUNCA afirma que o prazo expirou —
# informa que PODE ter expirado e remete para profissional. Regimes de
# suspensão/interrupção não são calculáveis automaticamente.

@dataclass
class RegraPrazo:
    area: AreaJuridica
    campo_data: str            # campo da ficha com a data de referência
    dias: int
    norma: str
    descricao_tecnica: str
    descricao_cidada: str
    lado: str = "ativo"        # "ativo" (quem inicia) | "passivo" (quem se defende)


REGRAS_PRAZO: list[RegraPrazo] = [
    RegraPrazo(
        area=AreaJuridica.LABORAL,
        campo_data="data_despedimento",
        dias=60,
        norma="CT-387",
        descricao_tecnica="Prazo de 60 dias para impugnação judicial da "
                          "regularidade e licitude do despedimento (art. 387.º CT).",
        descricao_cidada="Para contestar um despedimento em tribunal há, em regra, "
                         "um prazo de 60 dias a contar do despedimento.",
    ),
    RegraPrazo(
        area=AreaJuridica.PENAL,
        campo_data="data_dos_factos",
        dias=180,
        norma="CP-115",
        descricao_tecnica="Direito de queixa extingue-se, em regra, no prazo de "
                          "6 meses a contar do conhecimento do facto e do seu autor "
                          "(art. 115.º CP) — crimes semipúblicos/particulares.",
        descricao_cidada="Para alguns crimes, a queixa tem de ser apresentada no "
                         "prazo de 6 meses depois de saber o que aconteceu e quem foi.",
    ),
    RegraPrazo(
        area=AreaJuridica.CIVIL,
        campo_data="data_dos_factos",
        dias=3 * 365,
        norma="CC-498",
        descricao_tecnica="Prescrição do direito de indemnização por responsabilidade "
                          "civil extracontratual: 3 anos (art. 498.º CC).",
        descricao_cidada="O direito a pedir indemnização por danos pode prescrever "
                         "ao fim de 3 anos.",
    ),
]

REGRAS_PRAZO += [
    RegraPrazo(
        area=AreaJuridica.CIVIL,
        campo_data="data_citacao",
        dias=30,
        norma="CPC-569",
        descricao_tecnica="Prazo de contestação: 30 dias a contar da citação "
                          "(art. 569.º CPC). A falta de contestação pode conduzir "
                          "à confissão dos factos articulados (revelia).",
        descricao_cidada="Depois de receber a citação do tribunal, tem em regra "
                         "30 dias para contestar. Se não responder, o tribunal pode "
                         "dar como verdadeiros os factos alegados contra si — "
                         "perde-se pelo silêncio.",
        lado="passivo",
    ),
    RegraPrazo(
        area=AreaJuridica.LABORAL,
        campo_data="data_citacao",
        dias=30,
        norma="CPC-569",
        descricao_tecnica="Prazo de contestação após citação (regime subsidiário "
                          "do art. 569.º CPC), sob pena de revelia.",
        descricao_cidada="Depois de receber a citação, há um prazo para contestar "
                         "— não responder pode significar perder o processo pelo silêncio.",
        lado="passivo",
    ),
    RegraPrazo(
        area=AreaJuridica.PENAL,
        campo_data="data_notificacao_acusacao",
        dias=20,
        norma="CPP-287",
        descricao_tecnica="Prazo de 20 dias, a contar da notificação da acusação, "
                          "para requerer a abertura de instrução (art. 287.º, n.º 1, CPP).",
        descricao_cidada="Depois de ser notificado da acusação, tem 20 dias para "
                         "pedir a abertura de instrução — a fase em que pode "
                         "contestar a acusação antes do julgamento.",
        lado="passivo",
    ),
]

# Vias não judiciais por área (o destino do caso pode não ser o tribunal)
VIAS_NAO_JUDICIAIS: dict[AreaJuridica, tuple[str, str]] = {
    AreaJuridica.PENAL: (
        "Casos com indícios de crime seguem tipicamente pela apresentação de "
        "queixa/denúncia junto do Ministério Público ou de órgão de polícia "
        "criminal — não por ação intentada diretamente no tribunal.",
        "Se houve um crime, o caminho habitual é apresentar queixa ao "
        "Ministério Público ou numa esquadra — não é preciso 'pôr um processo "
        "em tribunal' diretamente.",
    ),
    AreaJuridica.CONSUMO: (
        "Litígios de consumo de valor reduzido seguem tipicamente pelos "
        "Centros de Arbitragem de Conflitos de Consumo (via célere e, em "
        "muitos casos, gratuita), sem prejuízo do recurso aos tribunais.",
        "Para problemas com compras e serviços, existe a arbitragem de "
        "consumo: é mais rápida e muitas vezes gratuita.",
    ),
    AreaJuridica.DADOS_PESSOAIS: (
        "Violações de dados pessoais seguem tipicamente por reclamação junto "
        "da CNPD, sem prejuízo da via judicial.",
        "Para problemas com os seus dados pessoais pode reclamar à CNPD "
        "(a autoridade de proteção de dados).",
    ),
}


_SINAIS_RISCO = (
    "bate-me", "bateu-me", "agride", "agrediu", "espanca", "violência doméstica",
    "violencia domestica", "ameaçou matar", "ameacou matar", "tenho medo dele",
    "tenho medo dela", "medo que me faça mal", "não me deixa sair", "nao me deixa sair",
    "persegue-me", "stalking", "abusa de mim", "abusou de mim",
)


def _detetar_risco_pessoal(texto: str) -> bool:
    t = texto.lower()
    return any(s in t for s in _SINAIS_RISCO)


# ── Prompts LLM ─────────────────────────────────────────────────────────────

_SYSTEM_INSTRUTOR = """És o Agente Instrutor de um sistema institucional português de informação jurídica.
O teu papel é fazer perguntas a um cidadão para esclarecer um caso — como um juiz de instrução: neutro, rigoroso, uma pergunta de cada vez.

REGRAS DEONTOLÓGICAS (invioláveis):
- Informas, nunca prescreves. Nunca dizes "deve processar" ou "deve fazer X".
- Não formulas juízos sobre culpa ou razão de qualquer das partes.
- Linguagem simples e respeitosa, acessível a qualquer cidadão.

REGRAS DE FORMULAÇÃO:
- Respondes EXCLUSIVAMENTE em JSON válido, sem markdown, sem texto fora do JSON.
- Uma única pergunta de cada vez — a que mais reduz a incerteza jurídica.
- Critério do tipo de pergunta:
  * espaço de respostas fechado e enumerável (existência, categoria com poucas opções) → "escolha" com 2 a 4 opções curtas;
  * narrativa, nomes, descrições → "texto";
  * datas → "data";
  * quantias em euros → "valor".
- Nunca repitas perguntas já respondidas.
- "campo_ficha" é um identificador snake_case do facto a apurar (ex.: "contrato_escrito", "data_despedimento", "valor_dano")."""

_PROMPT_PROXIMA_PERGUNTA = """CASO (relato inicial):
{relato}

CLASSIFICAÇÃO PRELIMINAR:
{classificacao}

FACTOS JÁ APURADOS (não voltar a perguntar):
{apurados}

LACUNAS TÍPICAS A CONSIDERAR: papel processual (a pessoa inicia o caso ou defende-se dele? se se defende, a data da citação/notificação é a pergunta mais urgente — perde-se pelo silêncio); datas relevantes (prazos/prescrição); existência e forma de contrato; valor do dano ou do pedido; identidade/qualidade das partes; provas disponíveis (documentos, testemunhas); local dos factos.

Se a informação já apurada for suficiente para uma análise jurídica sólida, devolve {{"suficiente": true, "resumo": "síntese do caso em 2-3 frases"}}.

Caso contrário, devolve EXCLUSIVAMENTE:
{{
  "suficiente": false,
  "pergunta": "texto da pergunta",
  "tipo": "escolha|texto|data|valor",
  "opcoes": ["opção 1", "opção 2"],
  "objetivo": "que facto jurídico esta pergunta apura e porquê",
  "campo_ficha": "identificador_snake_case"
}}"""


# ── Agente ──────────────────────────────────────────────────────────────────

class AgenteInstrutor:
    """
    Uso com LLM:
        agente = AgenteInstrutor(llm_client=cliente)
        estado = agente.iniciar("Fui despedido ontem sem explicação.")
        p = agente.proxima_pergunta(estado)
        agente.registar_resposta(estado, Resposta(p.id, "Não"))
        ...
        ficha, alertas = agente.concluir(estado)

    Uso sem LLM (testes): igual, com sequência determinística de perguntas.
    """

    def __init__(
        self,
        llm_client=None,
        max_perguntas: int = 7,
        limiar_confianca: float = 0.85,
        modelo: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4000,
        max_continuacoes: int = 4,
    ):
        self._llm = llm_client
        self._classificador = ClassificadorJuridico(llm_client=llm_client)
        self.max_perguntas = max_perguntas
        self.limiar_confianca = limiar_confianca
        self.modelo = modelo
        self.max_tokens = max_tokens
        self.max_continuacoes = max_continuacoes
        logger.info("instrutor.init", via_llm=(llm_client is not None))

    # ── Ciclo público ───────────────────────────────────────────────────

    def iniciar(self, relato: str) -> EstadoInstrucao:
        caso_id = str(uuid.uuid4())
        ficha = FichaDeFactos(caso_id=caso_id, relato_inicial=relato.strip())
        estado = EstadoInstrucao(
            caso_id=caso_id,
            relato_inicial=relato.strip(),
            ficha=ficha,
            via_llm=(self._llm is not None),
        )
        estado.classificacao = self._classificador.classificar(relato)
        if _detetar_risco_pessoal(relato):
            estado.alertas.append(Alerta(
                tipo=TipoAlerta.PROTECAO_URGENTE,
                gravidade=GravidadeAlerta.URGENTE,
                mensagem_tecnica=(
                    "Indícios de risco para a integridade pessoal. Prioridade à "
                    "proteção: 112 em perigo imediato; APAV 116 006 (gratuito); "
                    "estatuto de vítima (Lei n.º 130/2015) e, em crimes violentos, "
                    "indemnização pelo Estado (Lei n.º 104/2009, CPVC)."
                ),
                mensagem_cidada=(
                    "Antes de tudo: se estiver em perigo, ligue 112. Para apoio "
                    "gratuito e confidencial a vítimas, ligue 116 006 (APAV). "
                    "Tem direitos especiais como vítima e, em crimes violentos, "
                    "pode ter direito a uma indemnização paga pelo Estado. "
                    "A informação jurídica pode esperar; a sua segurança não."
                ),
            ))
        self._emitir_alertas_de_via(estado)
        logger.info(
            "instrutor.iniciado",
            caso_id=caso_id,
            areas=[a.value for a in estado.classificacao.todas_as_areas],
        )
        return estado

    def proxima_pergunta(self, estado: EstadoInstrucao) -> Optional[Pergunta]:
        """Devolve a próxima pergunta, ou None se a instrução terminou."""
        if estado.terminado:
            return None

        if len(estado.perguntas_feitas) >= self.max_perguntas:
            self._terminar(estado, "orcamento_de_perguntas_esgotado")
            return None

        if (
            estado.classificacao is not None
            and estado.classificacao.via_llm
            and estado.classificacao.confianca >= self.limiar_confianca
            and len(estado.perguntas_feitas) >= 3  # mínimo de instrução
        ):
            self._terminar(estado, "confianca_atingida")
            return None

        if self._llm is not None:
            pergunta = self._gerar_pergunta_llm(estado)
        else:
            pergunta = self._gerar_pergunta_stub(estado)

        if pergunta is None:
            self._terminar(estado, "informacao_suficiente")
            return None

        pergunta = self._validar_pergunta(pergunta)
        estado.perguntas_feitas.append(pergunta)
        return pergunta

    def registar_resposta(self, estado: EstadoInstrucao, resposta: Resposta) -> None:
        estado.respostas.append(resposta)
        pergunta = next(
            (p for p in estado.perguntas_feitas if p.id == resposta.pergunta_id),
            None,
        )
        if pergunta is None:
            logger.warning("instrutor.resposta_orfa", pergunta_id=resposta.pergunta_id)
            return

        campo = pergunta.campo_ficha or f"resposta_{len(estado.respostas)}"
        valor = resposta.valor.strip()

        estado.ficha.respostas_normalizadas[campo] = self._normalizar(pergunta, valor)

        if pergunta.tipo == TipoPergunta.DATA:
            data_iso = self._parse_data(valor)
            if data_iso:
                estado.ficha.cronologia.append(
                    {"data": data_iso, "evento": pergunta.objetivo or pergunta.texto}
                )
        elif pergunta.tipo == TipoPergunta.VALOR:
            numero = self._parse_valor(valor)
            if numero is not None:
                estado.ficha.valores[campo] = numero

        # Reclassifica com o contexto acumulado (a compreensão evolui)
        contexto = estado.ficha.para_texto_rag()
        estado.classificacao = self._classificador.classificar(contexto)

        # Reavalia alertas deterministas com os novos dados
        self._emitir_alertas_de_prazo(estado)
        self._emitir_alertas_de_via(estado)

    def concluir(self, estado: EstadoInstrucao) -> tuple[FichaDeFactos, list[Alerta]]:
        """Fecha a instrução (se ainda aberta) e devolve ficha + alertas."""
        if not estado.terminado:
            self._terminar(estado, "conclusao_pedida")
        return estado.ficha, estado.alertas

    # ── Geração de perguntas (LLM) ──────────────────────────────────────

    def _gerar_pergunta_llm(self, estado: EstadoInstrucao) -> Optional[Pergunta]:
        apurados = json.dumps(
            estado.ficha.respostas_normalizadas, ensure_ascii=False
        ) or "nenhum"
        classif = ""
        if estado.classificacao:
            classif = "; ".join(
                f"{a.area.value} (peso {a.peso})" for a in estado.classificacao.areas
            )

        prompt = _PROMPT_PROXIMA_PERGUNTA.format(
            relato=estado.relato_inicial,
            classificacao=classif or "por determinar",
            apurados=apurados,
        )

        try:
            raw = self._chamar_llm_completo(_SYSTEM_INSTRUTOR, prompt)
            dados = self._extrair_json(raw)
        except Exception as exc:
            logger.warning("instrutor.llm.fallback_stub", erro=str(exc))
            return self._gerar_pergunta_stub(estado)

        if dados.get("suficiente") is True:
            estado.ficha.resumo_instrucao = dados.get("resumo", "")
            return None

        try:
            tipo = TipoPergunta(dados.get("tipo", "texto"))
        except ValueError:
            tipo = TipoPergunta.TEXTO

        return Pergunta(
            id=str(uuid.uuid4()),
            texto=str(dados.get("pergunta", "")).strip(),
            tipo=tipo,
            opcoes=[str(o).strip() for o in dados.get("opcoes", []) if str(o).strip()],
            objetivo=str(dados.get("objetivo", "")).strip(),
            campo_ficha=self._sanear_campo(dados.get("campo_ficha", "")),
        )

    # ── Geração de perguntas (stub determinístico, sem LLM) ────────────

    def _gerar_pergunta_stub(self, estado: EstadoInstrucao) -> Optional[Pergunta]:
        """Sequência fixa que cobre as lacunas típicas — usada em testes."""
        ja = estado.ficha.respostas_normalizadas
        sequencia: list[Pergunta] = [
            Pergunta(
                id="", texto="Qual é a sua posição neste caso?",
                tipo=TipoPergunta.ESCOLHA,
                opcoes=["Quero apresentar uma queixa ou reclamação",
                        "Fui processado, acusado ou recebi carta do tribunal"],
                objetivo="Determinar o papel processual (os prazos e o caminho dependem disto)",
                campo_ficha="papel_no_caso",
            ),
        ]
        if ja.get("papel_no_caso") == "demandado":
            sequencia.append(Pergunta(
                id="", texto="Quando recebeu a citação ou a notificação do tribunal?",
                tipo=TipoPergunta.DATA,
                objetivo="Apurar o prazo de resposta (contestação/instrução) — perde-se pelo silêncio",
                campo_ficha="data_citacao",
            ))
        sequencia += [
            Pergunta(
                id="", texto="Quando ocorreram os factos principais?",
                tipo=TipoPergunta.DATA,
                objetivo="Apurar datas para verificação de prazos e prescrição",
                campo_ficha="data_dos_factos",
            ),
            Pergunta(
                id="", texto="Existe contrato escrito relacionado com esta situação?",
                tipo=TipoPergunta.ESCOLHA, opcoes=["Sim", "Não"],
                objetivo="Determinar a forma do contrato (prova e validade)",
                campo_ficha="contrato_escrito",
            ),
            Pergunta(
                id="", texto="Qual o valor aproximado do prejuízo ou do pedido, em euros?",
                tipo=TipoPergunta.VALOR,
                objetivo="Determinar alçada e competência",
                campo_ficha="valor_dano",
            ),
            Pergunta(
                id="", texto="Que provas tem disponíveis (documentos, mensagens, testemunhas)?",
                tipo=TipoPergunta.TEXTO,
                objetivo="Inventariar meios de prova",
                campo_ficha="provas_disponiveis",
            ),
            Pergunta(
                id="", texto="Descreva, por palavras suas, o que pretende obter.",
                tipo=TipoPergunta.TEXTO,
                objetivo="Apurar o pedido",
                campo_ficha="pedido",
            ),
        ]
        for p in sequencia:
            if p.campo_ficha not in ja:
                p.id = str(uuid.uuid4())
                return p
        return None

    # ── Validação e salvaguardas das perguntas ──────────────────────────

    def _validar_pergunta(self, p: Pergunta) -> Pergunta:
        """
        Salvaguardas da versão mista:
          - texto vazio → pergunta genérica de texto livre;
          - "escolha" sem opções → degrada para texto;
          - "escolha" com mais de MAX_OPCOES → degrada para texto
            (sinal de que o espaço de respostas afinal não era enumerável);
          - "escolha" válida → garante "Não sei" e "Outro / prefiro explicar".
        """
        if not p.texto:
            p.texto = "Pode descrever melhor a situação, por favor?"
            p.tipo = TipoPergunta.TEXTO
            p.opcoes = []
            return p

        if p.tipo == TipoPergunta.ESCOLHA:
            opcoes_reais = [
                o for o in p.opcoes if o not in (OPCAO_NAO_SEI, OPCAO_OUTRO)
            ]
            if not opcoes_reais or len(opcoes_reais) > MAX_OPCOES:
                logger.info(
                    "instrutor.pergunta.degradada_para_texto",
                    n_opcoes=len(opcoes_reais),
                )
                p.tipo = TipoPergunta.TEXTO
                p.opcoes = []
                return p
            if OPCAO_NAO_SEI not in p.opcoes:
                opcoes_reais.append(OPCAO_NAO_SEI)
            else:
                opcoes_reais.append(OPCAO_NAO_SEI)
            if OPCAO_OUTRO not in opcoes_reais:
                opcoes_reais.append(OPCAO_OUTRO)
            p.opcoes = opcoes_reais
        else:
            p.opcoes = []
        return p

    # ── Alertas deterministas ───────────────────────────────────────────

    def _emitir_alertas_de_prazo(self, estado: EstadoInstrucao) -> None:
        if estado.classificacao is None:
            return
        areas = set(estado.classificacao.todas_as_areas)
        hoje = date.today()

        papel = estado.ficha.respostas_normalizadas.get("papel_no_caso", "")
        for regra in REGRAS_PRAZO:
            if regra.area not in areas:
                continue
            # O lado processual determina que prazos importam a esta pessoa
            if regra.lado == "passivo" and papel != "demandado":
                continue
            if regra.lado == "ativo" and papel == "demandado":
                continue
            valor = estado.ficha.respostas_normalizadas.get(regra.campo_data)
            data_ref = self._parse_data(valor) if valor else None
            if not data_ref and regra.lado == "ativo":
                # procura na cronologia (apenas para o lado ativo — o passivo
                # exige a data exata da citação/notificação)
                for ev in estado.ficha.cronologia:
                    data_ref = ev.get("data")
                    if data_ref:
                        break
            if not data_ref:
                continue
            try:
                d = date.fromisoformat(data_ref)
            except ValueError:
                continue

            limite = d + timedelta(days=regra.dias)
            ja_emitido = any(a.norma_base == regra.norma for a in estado.alertas)
            if ja_emitido:
                continue

            if hoje > limite:
                estado.alertas.append(Alerta(
                    tipo=TipoAlerta.PRAZO,
                    gravidade=GravidadeAlerta.URGENTE,
                    norma_base=regra.norma,
                    subtipo="expirado",
                    mensagem_tecnica=(
                        f"{regra.descricao_tecnica} Face à data indicada "
                        f"({data_ref}), o prazo PODE ter-se esgotado em "
                        f"{limite.isoformat()}. Verificar causas de suspensão/"
                        f"interrupção com profissional habilitado."
                    ),
                    mensagem_cidada=(
                        f"Atenção: {regra.descricao_cidada} Pela data que indicou, "
                        f"esse prazo pode já ter passado. Isto não é certo — há "
                        f"situações que o alargam — por isso fale com um advogado "
                        f"o mais depressa possível."
                    ),
                ))
            elif (limite - hoje).days <= 15:
                estado.alertas.append(Alerta(
                    tipo=TipoAlerta.PRAZO,
                    gravidade=GravidadeAlerta.URGENTE,
                    norma_base=regra.norma,
                    subtipo="em_risco",
                    mensagem_tecnica=(
                        f"{regra.descricao_tecnica} Prazo em curso: termo "
                        f"indicativo em {limite.isoformat()} "
                        f"({(limite - hoje).days} dias)."
                    ),
                    mensagem_cidada=(
                        f"Atenção: {regra.descricao_cidada} Pela data que indicou, "
                        f"restam cerca de {(limite - hoje).days} dias. "
                        f"Procure ajuda profissional com urgência."
                    ),
                ))

    def _emitir_alertas_de_via(self, estado: EstadoInstrucao) -> None:
        if estado.classificacao is None:
            return
        for area in estado.classificacao.todas_as_areas:
            par = VIAS_NAO_JUDICIAIS.get(area)
            if not par:
                continue
            tecnica, cidada = par
            ja = any(
                a.tipo == TipoAlerta.VIA_NAO_JUDICIAL and a.mensagem_tecnica == tecnica
                for a in estado.alertas
            )
            if not ja:
                estado.alertas.append(Alerta(
                    tipo=TipoAlerta.VIA_NAO_JUDICIAL,
                    gravidade=GravidadeAlerta.INFORMATIVO,
                    mensagem_tecnica=tecnica,
                    mensagem_cidada=cidada,
                ))

    def emitir_alerta_apoio_judiciario(self, estado: EstadoInstrucao) -> None:
        """
        Chamado pela camada de API quando o utilizador indica insuficiência
        de meios económicos (pergunta padrão do frontend, fora do ciclo LLM).
        """
        estado.alertas.append(Alerta(
            tipo=TipoAlerta.APOIO_JUDICIARIO,
            gravidade=GravidadeAlerta.INFORMATIVO,
            mensagem_tecnica=(
                "Encaminhamento para proteção jurídica (apoio judiciário) junto "
                "da Segurança Social — Lei n.º 34/2004 (acesso ao direito e aos "
                "tribunais)."
            ),
            mensagem_cidada=(
                "Se tiver dificuldades económicas, pode pedir apoio judiciário "
                "na Segurança Social: o Estado pode pagar total ou parcialmente "
                "o advogado e as custas do processo."
            ),
        ))

    # ── LLM: chamada com anti-corte de frases ───────────────────────────

    def _chamar_llm_completo(self, system: str, prompt: str) -> str:
        """
        Chama o LLM e garante terminação natural da resposta.
        Se stop_reason == "max_tokens", pede continuação e concatena,
        até max_continuacoes. Nenhuma resposta cortada chega ao utilizador.
        """
        mensagens = [{"role": "user", "content": prompt}]
        partes: list[str] = []

        for i in range(self.max_continuacoes + 1):
            msg = self._llm.messages.create(
                model=self.modelo,
                max_tokens=self.max_tokens,
                system=system,
                messages=mensagens,
            )
            texto = "".join(
                bloco.text for bloco in msg.content if getattr(bloco, "text", None)
            )
            partes.append(texto)

            if getattr(msg, "stop_reason", "end_turn") != "max_tokens":
                break

            logger.info("instrutor.llm.continuacao", iteracao=i + 1)
            mensagens = mensagens + [
                {"role": "assistant", "content": texto},
                {"role": "user", "content": "Continua exatamente de onde paraste, sem repetir nada."},
            ]

        return "".join(partes).strip()

    # ── Utilitários ─────────────────────────────────────────────────────

    @staticmethod
    def _extrair_json(raw: str) -> dict:
        raw = re.sub(r"```json|```", "", raw).strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if not m:
                raise ValueError("LLM não devolveu JSON válido")
            return json.loads(m.group())

    @staticmethod
    def _sanear_campo(campo: str) -> str:
        campo = re.sub(r"[^a-z0-9_]", "_", str(campo).strip().lower())
        return re.sub(r"_+", "_", campo).strip("_")[:60]

    @staticmethod
    def _normalizar(pergunta: Pergunta, valor: str) -> str:
        if pergunta.campo_ficha == "papel_no_caso":
            v = valor.lower()
            if any(p in v for p in ("processado", "acusado", "carta", "citação", "citacao", "notifica")):
                return "demandado"
            if any(p in v for p in ("apresentar", "queixa", "reclama")):
                return "demandante"
            return "nao_sei"
        if pergunta.tipo == TipoPergunta.ESCOLHA:
            v = valor.strip().lower()
            if v in ("sim", "não", "nao"):
                return "sim" if v == "sim" else "nao"
            if valor == OPCAO_NAO_SEI:
                return "nao_sei"
            return valor
        return valor

    @staticmethod
    def _parse_data(valor: Optional[str]) -> Optional[str]:
        if not valor:
            return None
        valor = valor.strip()
        # ISO direto (do calendário do frontend)
        try:
            return date.fromisoformat(valor[:10]).isoformat()
        except ValueError:
            pass
        # dd/mm/aaaa e dd-mm-aaaa
        m = re.match(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})$", valor)
        if m:
            try:
                return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
            except ValueError:
                return None
        return None

    @staticmethod
    def _parse_valor(valor: str) -> Optional[float]:
        limpo = re.sub(r"[^\d,.\-]", "", valor).replace(".", "").replace(",", ".")
        try:
            return float(limpo)
        except ValueError:
            try:
                return float(re.sub(r"[^\d.\-]", "", valor))
            except ValueError:
                return None

    def _terminar(self, estado: EstadoInstrucao, motivo: str) -> None:
        estado.terminado = True
        estado.motivo_fim = motivo
        if not estado.ficha.resumo_instrucao and estado.classificacao:
            estado.ficha.resumo_instrucao = estado.classificacao.resumo
        logger.info(
            "instrutor.terminado",
            caso_id=estado.caso_id,
            motivo=motivo,
            perguntas=len(estado.perguntas_feitas),
            alertas=len(estado.alertas),
        )
