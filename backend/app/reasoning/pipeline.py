"""
Pipeline de Reasoning Jurídico do SNAJI.

Em linguagem simples:
  1. Recebe um caso descrito em português
  2. Classifica juridicamente via LLM (pode ser multi-área)   ← NOVO
  3. Recupera artigos relevantes (RAG, ponderado por área)    ← MELHORADO
  4. Extrai os factos do caso
  5. Qualifica juridicamente com contexto multi-área
  6. Analisa normas aplicáveis
  7. Produz argumentos de defesa E de acusação (contraditório)
  8. Valida todas as citações (anti-alucinação)
  9. Devolve resultado estruturado e auditável

O LLM é usado nas etapas 2, 4, 5, 6 e 7.
Tudo o resto é código determinístico.

ALTERAÇÃO PRINCIPAL (v2):
  A classificação do tipo de processo é agora feita por LLM
  (ClassificadorJuridico) em vez de heurística por palavras-chave.
  Suporta casos com múltiplas áreas jurídicas em simultâneo.
  A heurística anterior mantém-se como fallback e em modo stub.
"""

from __future__ import annotations
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import structlog

from app.rag.motor import RAGJuridico, ValidadorCitacoes, Chunk
from app.reasoning.classificador_juridico import (
    ClassificadorJuridico,
    ClassificacaoJuridica,
    AreaJuridica,
    AreaDetectada,
    _classificar_heuristico,
)

logger = structlog.get_logger(__name__)


# ── TipoProcesso mantido para compatibilidade com código existente ─────────

class TipoProcesso(str, Enum):
    LABORAL        = "laboral"
    CIVIL          = "civil"
    PENAL          = "penal"
    ADMINISTRATIVO = "administrativo"
    FAMILIA        = "familia"
    CONSUMO        = "consumo"
    DADOS_PESSOAIS = "dados_pessoais"
    OUTRO          = "outro"


def _area_para_tipo_processo(area: AreaJuridica) -> TipoProcesso:
    """Converte AreaJuridica para TipoProcesso (compatibilidade)."""
    try:
        return TipoProcesso(area.value)
    except ValueError:
        return TipoProcesso.OUTRO


# ── Dataclasses de resultado ───────────────────────────────────────────────

@dataclass
class Facto:
    descricao: str
    relevancia: str  # "alta" | "media" | "baixa"


@dataclass
class NormaAplicada:
    diploma: str
    artigo: str
    epigrase: str
    excerto: str
    relevancia: float
    fonte: str


@dataclass
class ArgumentoJuridico:
    posicao: str        # "acusacao" | "defesa" | "neutro"
    argumento: str
    normas_base: list[str]  # ["CRP-53", "CT-351"]


@dataclass
class ResultadoReasoning:
    caso_id: str
    tipo_processo: TipoProcesso          # área principal (compatibilidade)
    classificacao: ClassificacaoJuridica  # classificação completa multi-área (NOVO)
    factos: list[Facto]
    qualificacao: str
    normas: list[NormaAplicada]
    analise: str
    argumentos_acusacao: list[ArgumentoJuridico]
    argumentos_defesa: list[ArgumentoJuridico]
    vias_processuais: list[str]
    conclusao: str
    grounded: bool
    citacoes_suspeitas: list[dict]
    timestamp: datetime
    tokens_usados: int = 0


# ── Prompts estruturados ────────────────────────────────────────────────────

_SYSTEM = """És um sistema jurídico institucional português especializado em análise processual.
Respondes SEMPRE em JSON válido, sem markdown, sem texto exterior ao JSON.
Citas APENAS artigos que existam nas NORMAS fornecidas.
Quando não tens certeza, dizes explicitamente na conclusão.
A tua análise deve ser equilibrada: apresentas argumentos de ambas as partes."""

_PROMPT_ANALISE = """
CLASSIFICAÇÃO JURÍDICA DO CASO:
{classificacao_resumo}

NORMAS RECUPERADAS (usa APENAS estas, com diploma e artigo exactos):
{normas_rag}

CASO:
{caso}

Responde EXCLUSIVAMENTE com este JSON:
{{
  "factos": [
    {{"descricao": "facto relevante 1", "relevancia": "alta"}},
    {{"descricao": "facto relevante 2", "relevancia": "media"}}
  ],
  "qualificacao": "qualificação jurídica do problema em 1-2 frases, referindo todas as áreas do direito envolvidas",
  "analise": "análise jurídica detalhada citando os artigos exactos das normas acima",
  "argumentos_acusacao": [
    {{"argumento": "argumento 1 da parte autora/acusação", "normas_base": ["DIPLOMA-ARTIGO"]}}
  ],
  "argumentos_defesa": [
    {{"argumento": "argumento 1 da defesa/réu", "normas_base": ["DIPLOMA-ARTIGO"]}}
  ],
  "vias_processuais": ["via processual 1", "via processual 2"],
  "conclusao": "conclusão fundamentada, indicando qual a posição juridicamente mais sólida e porquê"
}}
"""


# ── Função legada (mantida para compatibilidade com testes existentes) ─────

_KEYWORDS_TIPO = {
    TipoProcesso.LABORAL:       ["despedimento","trabalho","salário","férias","trabalhador","empregador","contrato de trabalho","justa causa","indemnização laboral"],
    TipoProcesso.PENAL:         ["suborno","corrupção","crime","furto","roubo","homicídio","ofensa","ameaça","corrupção","burla","coação","arguido","pena","prisão","detenção"],
    TipoProcesso.DADOS_PESSOAIS:["dados pessoais","rgpd","privacidade","consentimento","tratamento de dados","apagamento","portabilidade"],
    TipoProcesso.FAMILIA:       ["divórcio","filhos","alimentos","custódia","casamento","adoção","família","menores","separação"],
    TipoProcesso.CONSUMO:       ["consumidor","produto","garantia","devolução","compra","venda","defeito","fornecedor"],
    TipoProcesso.CIVIL:         ["contrato","propriedade","indemnização","danos","responsabilidade","arrendamento","herança","divida"],
    TipoProcesso.ADMINISTRATIVO:["Estado","administração","município","licença","imposto","multa","recurso administrativo","funcionário público"],
}


def classificar_tipo_processo(texto: str) -> TipoProcesso:
    """
    MANTIDA PARA COMPATIBILIDADE COM TESTES EXISTENTES.
    Usa heurística por palavras-chave — devolve um único TipoProcesso.
    Para classificação completa (multi-área, via LLM), usa ClassificadorJuridico.
    """
    texto_lower = texto.lower()
    PESO_ALTO = {"suborno", "corrupção", "crime", "arguido", "prisão", "pena", "homicídio", "furto", "roubo"}
    pontuacao: dict[TipoProcesso, int] = {t: 0 for t in TipoProcesso}
    for tipo, keywords in _KEYWORDS_TIPO.items():
        for kw in keywords:
            if kw in texto_lower:
                pontuacao[tipo] += 3 if kw in PESO_ALTO else 1
    melhor = max(pontuacao, key=lambda t: pontuacao[t])
    return melhor if pontuacao[melhor] > 0 else TipoProcesso.OUTRO


# ── Helpers ────────────────────────────────────────────────────────────────

def _formatar_classificacao_para_prompt(clf: ClassificacaoJuridica) -> str:
    """Formata a classificação multi-área para incluir no prompt de análise."""
    linhas = [f"Resumo: {clf.resumo}"]
    for area in clf.areas:
        principal_tag = " [ÁREA PRINCIPAL]" if area.principal else ""
        instancias = ", ".join(i.value for i in area.instancias)
        linhas.append(
            f"• {area.area.value.upper()}{principal_tag} (peso {area.peso:.1f})"
            f" — Instância(s): {instancias}"
        )
        if area.justificacao:
            linhas.append(f"  Justificação: {area.justificacao}")
    return "\n".join(linhas)


def _formatar_normas_para_prompt(chunks: list[Chunk]) -> str:
    if not chunks:
        return "Nenhuma norma específica recuperada. Indica isso na conclusão."
    linhas = []
    for c in chunks:
        epigrase = f" ({c.epigrase})" if c.epigrase else ""
        excerto = c.texto[:300] + "..." if len(c.texto) > 300 else c.texto
        linhas.append(f"• Art. {c.artigo}.º {c.diploma}{epigrase}: {excerto}")
    return "\n".join(linhas)


def _parse_argumentos(raw: list[dict], posicao: str) -> list[ArgumentoJuridico]:
    resultado = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        resultado.append(ArgumentoJuridico(
            posicao=posicao,
            argumento=item.get("argumento", ""),
            normas_base=item.get("normas_base", []),
        ))
    return resultado


def _rag_ponderado(rag: RAGJuridico, texto: str, clf: ClassificacaoJuridica, top_k: int = 10) -> list[Chunk]:
    """
    Faz RAG paralelo por área jurídica e combina resultados ponderados.
    Para casos multi-área, garante cobertura de todas as áreas relevantes.
    """
    # Calcula quantos chunks pedir por área
    total_peso = sum(a.peso for a in clf.areas)
    chunks_por_area: dict[str, list[Chunk]] = {}

    for area in clf.areas:
        k_area = max(2, round(top_k * area.peso / total_peso))
        # Enriquece a query com o nome da área para guiar o RAG
        query_area = f"{texto} [{area.area.value}]"
        chunks_area = rag.search(query_area, top_k=k_area)
        chunks_por_area[area.area.value] = chunks_area

    # Merge: dedup por (diploma, artigo), mantendo score mais alto
    seen: dict[tuple, Chunk] = {}
    for area_str, chunks in chunks_por_area.items():
        area_peso = clf.peso_de(AreaJuridica(area_str))
        for chunk in chunks:
            key = (chunk.diploma, chunk.artigo)
            # Pondera o score pelo peso da área
            chunk_ponderado = Chunk(
                diploma=chunk.diploma,
                artigo=chunk.artigo,
                epigrase=chunk.epigrase,
                texto=chunk.texto,
                score=chunk.score * area_peso,
                fonte=chunk.fonte,
            ) if hasattr(chunk, '__dataclass_fields__') else chunk
            if key not in seen or chunk.score > seen[key].score:
                seen[key] = chunk

    # Ordena por score e devolve top_k
    resultado = sorted(seen.values(), key=lambda c: c.score, reverse=True)
    return resultado[:top_k]


# ── Pipeline principal ─────────────────────────────────────────────────────

class ReasoningPipeline:
    """
    Pipeline determinístico de análise jurídica.
    Pode correr sem LLM (modo stub) para testes.
    Liga ao LLM quando a chave API estiver configurada.

    NOVIDADE v2: classificação via LLM multi-área antes do RAG.
    """

    def __init__(self, llm_client=None):
        self._rag = RAGJuridico()
        self._validator = ValidadorCitacoes()
        self._llm = llm_client
        self._classificador = ClassificadorJuridico(llm_client=llm_client)
        logger.info("reasoning.pipeline.init", artigos=self._rag.total_artigos, llm=llm_client is not None)

    def analisar(self, texto: str, fontes: list[str] | None = None) -> ResultadoReasoning:
        caso_id = str(uuid.uuid4())
        log = logger.bind(caso_id=caso_id)
        log.info("reasoning.start", texto_len=len(texto))

        # Etapa 1: Classificação via LLM (ou heurística em modo stub)
        classificacao = self._classificador.classificar(texto)
        tipo = _area_para_tipo_processo(classificacao.area_principal)
        log.info(
            "reasoning.classificado",
            areas=[a.area.value for a in classificacao.areas],
            via_llm=classificacao.via_llm,
        )

        # Etapa 2: RAG ponderado por área
        chunks = _rag_ponderado(self._rag, texto, classificacao, top_k=8)
        log.info("reasoning.rag.done", chunks=len(chunks))

        normas_prompt = _formatar_normas_para_prompt(chunks)
        classificacao_prompt = _formatar_classificacao_para_prompt(classificacao)

        # Etapa 3: LLM ou stub — com degradação graciosa: uma falha do LLM
        # (chave inválida, rede, saldo) NUNCA nega a resposta ao utilizador
        if self._llm is not None:
            try:
                dados = self._chamar_llm(texto, classificacao_prompt, normas_prompt, log)
                tokens = dados.pop("_tokens", 0)
            except Exception as exc:
                log.warning("reasoning.llm_falhou_a_degradar_para_stub", erro=str(exc)[:200])
                dados = self._stub_sem_llm(texto, chunks, classificacao)
                tokens = 0
        else:
            dados = self._stub_sem_llm(texto, chunks, classificacao)
            tokens = 0

        # Etapa 4: Anti-alucinação
        texto_para_validar = dados.get("analise", "") + " " + dados.get("conclusao", "")
        validas, suspeitas = self._validator.extrair_e_validar(texto_para_validar)
        if suspeitas:
            log.warning("reasoning.hallucination", suspeitas=suspeitas)

        # Etapa 5: Construir normas estruturadas
        normas = []
        for c in chunks[:6]:
            normas.append(NormaAplicada(
                diploma=c.diploma,
                artigo=c.artigo,
                epigrase=c.epigrase,
                excerto=c.texto[:200] + "..." if len(c.texto) > 200 else c.texto,
                relevancia=min(c.score / 10.0, 1.0),
                fonte=c.fonte,
            ))

        resultado = ResultadoReasoning(
            caso_id=caso_id,
            tipo_processo=tipo,
            classificacao=classificacao,
            factos=[Facto(**f) for f in dados.get("factos", []) if isinstance(f, dict)],
            qualificacao=dados.get("qualificacao", ""),
            normas=normas,
            analise=dados.get("analise", ""),
            argumentos_acusacao=_parse_argumentos(dados.get("argumentos_acusacao", []), "acusacao"),
            argumentos_defesa=_parse_argumentos(dados.get("argumentos_defesa", []), "defesa"),
            vias_processuais=dados.get("vias_processuais", []),
            conclusao=dados.get("conclusao", ""),
            grounded=len(suspeitas) == 0,
            citacoes_suspeitas=suspeitas,
            timestamp=datetime.now(timezone.utc),
            tokens_usados=tokens,
        )

        log.info("reasoning.done", grounded=resultado.grounded, normas=len(normas))
        return resultado

    def _chamar_llm(self, texto: str, classificacao_prompt: str, normas_prompt: str, log) -> dict:
        """Chama o LLM com o prompt estruturado."""
        prompt = _PROMPT_ANALISE.format(
            classificacao_resumo=classificacao_prompt,
            normas_rag=normas_prompt,
            caso=texto,
        )
        log.info("reasoning.llm.call")
        msg = self._llm.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2500,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text
        tokens = msg.usage.input_tokens + msg.usage.output_tokens
        try:
            dados = json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            dados = json.loads(m.group()) if m else {}
        dados["_tokens"] = tokens
        log.info("reasoning.llm.done", tokens=tokens)
        return dados

    def _stub_sem_llm(self, texto: str, chunks: list[Chunk], clf: ClassificacaoJuridica) -> dict:
        """
        Modo sem LLM — para testes e desenvolvimento.
        Produz uma resposta estruturada baseada apenas no RAG e classificação.
        Não inventa artigos. Não alucina.
        """
        normas_txt = ", ".join(f"Art. {c.artigo}.º {c.diploma}" for c in chunks[:3])
        areas_txt = " + ".join(a.area.value for a in clf.areas)
        return {
            "factos": [
                {"descricao": "Caso submetido para análise jurídica", "relevancia": "alta"},
                {"descricao": "Normas relevantes identificadas pelo motor RAG", "relevancia": "media"},
            ],
            "qualificacao": (
                f"Caso classificado com múltiplas dimensões jurídicas: {areas_txt}. "
                f"Aguarda análise LLM para qualificação detalhada."
            ),
            "analise": (
                f"Com base nas normas recuperadas ({normas_txt}), o caso envolve "
                f"as seguintes áreas: {areas_txt}. "
                f"Active o motor LLM para obter análise completa com citações verificadas."
            ),
            "argumentos_acusacao": [
                {"argumento": "Argumentos da parte autora — requer LLM para análise completa.", "normas_base": []},
            ],
            "argumentos_defesa": [
                {"argumento": "Argumentos da defesa — requer LLM para análise completa.", "normas_base": []},
            ],
            "vias_processuais": ["Consulte um advogado para determinar a via processual adequada."],
            "conclusao": "Análise preliminar com base em RAG e classificação LLM. Para análise completa, active o motor LLM.",
        }
