"""
Analisador de Peças Processuais — SNAJI
========================================
O assistente de litígio: recebe uma peça real (petição, contestação, sentença,
requerimento…) com dezenas de páginas e devolve ao advogado ou magistrado uma
análise acionável.

O que faz, sem depender de LLM (100% determinístico contra o corpus):
  1. VERIFICAÇÃO DE CITAÇÕES — extrai todas as referências a normas e verifica,
     uma a uma, contra o corpus de 6.602 artigos. As citações inexistentes
     ("art. 999.º CT") são sinalizadas A VERMELHO — é o maior valor para o
     advogado que enfrenta a peça da outra parte, e para o magistrado que
     confere a fundamentação.
  2. ESTRUTURA — deteta as secções típicas (factos, direito, pedido) e mede a
     dimensão de cada uma, para navegar as "80 páginas" sem as reler.
  3. NORMAS INVOCADAS — o índice de todos os diplomas e artigos citados.
  4. PRAZOS DESENCADEADOS — se a peça é uma citação/notificação, que prazos de
     resposta faz correr (contestação, instrução…).

Com LLM disponível, acrescenta um resumo dos factos e dos pontos fracos da
argumentação — mas a verificação, que é o que salva o profissional de um erro,
nunca depende dele.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import structlog

from app.rag.motor import ValidadorCitacoes, NORMAS_VALIDAS, RAGJuridico

logger = structlog.get_logger(__name__)


# Diplomas reconhecidos na extração (nome corrente → sigla do corpus)
_DIPLOMAS = {
    "código do trabalho": "CT", "cod. do trabalho": "CT", "ct": "CT",
    "código civil": "CC", "cod. civil": "CC", "cc": "CC",
    "código penal": "CP", "cod. penal": "CP", "cp": "CP",
    "código de processo civil": "CPC", "cpc": "CPC",
    "código de processo penal": "CPP", "cpp": "CPP",
    "constituição": "CRP", "crp": "CRP",
    "código de procedimento administrativo": "CPA", "cpa": "CPA",
    "cire": "CIRE", "código das sociedades comerciais": "CSC", "csc": "CSC",
    "rgpd": "RGPD",
}

# Padrão abrangente: "art. 483.º do Código Civil", "artigo 9999 CT", "art. 71 CPP"
_PADRAO_NORMA = re.compile(
    r"art(?:igo|\.)?\s*(\d+[\-\-]?[A-Z]?)\.?\s*[°ºoO\.]?\s*"
    r"(?:,?\s*n\.?[°º]?\s*\d+)?\s*"
    r"(?:e\s*(?:seguintes|ss\.?)\s*)?"
    r"(?:do|da|dos|das)?\s*"
    r"(Código do Trabalho|Código Civil|Código Penal|Código de Processo Civil|"
    r"Código de Processo Penal|Código de Procedimento Administrativo|"
    r"Código das Sociedades Comerciais|Constituição|CIRE|RGPD|"
    r"CT|CC|CPP|CPC|CPA|CSC|CRP|CP)\b",
    re.IGNORECASE | re.UNICODE,
)

# Secções típicas de uma peça processual
_SECCOES = {
    "factos": re.compile(r"\b(?:dos\s+)?factos?\b|matéria\s+de\s+facto", re.IGNORECASE),
    "direito": re.compile(r"\bdo\s+direito\b|enquadramento\s+jurídico|do\s+mérito", re.IGNORECASE),
    "pedido": re.compile(r"\b(?:do\s+)?pedido\b|nestes\s+termos|termina\s+pedindo|requer(?:\s+a\s+v\.?\s*ex)?", re.IGNORECASE),
    "prova": re.compile(r"\b(?:da\s+)?prova\b|rol\s+de\s+testemunhas|prova\s+documental", re.IGNORECASE),
}

# Sinais de que a peça faz correr prazos ao destinatário
_SINAIS_PRAZO = {
    "citacao": (re.compile(r"\bcita(?:do|ção|r-se)\b|fica\s+citad", re.IGNORECASE),
                "Se recebeu esta citação, corre o prazo de contestação — em regra 30 dias (art. 569.º CPC). A falta de contestação pode levar à confissão dos factos (revelia)."),
    "acusacao": (re.compile(r"\bacusaç(?:ão|ao)\b|deduz(?:-se)?\s+acusação", re.IGNORECASE),
                 "Notificada a acusação, corre o prazo de 20 dias para requerer a abertura de instrução (art. 287.º CPP)."),
    "sentenca": (re.compile(r"\bsentença\b|decisão\s+final|condeno|absolvo", re.IGNORECASE),
                 "Proferida a sentença, corre o prazo de recurso — em regra 30 dias (art. 638.º CPC / art. 411.º CPP)."),
}


@dataclass
class CitacaoVerificada:
    diploma: str
    artigo: str
    valida: bool
    contexto: str          # trecho onde aparece


@dataclass
class SeccaoDetetada:
    nome: str
    presente: bool
    posicao_aprox: int     # % do documento onde surge


@dataclass
class AnalisePeca:
    nome_ficheiro: str
    num_paginas: int
    num_caracteres: int
    tipo_provavel: str
    citacoes: list[CitacaoVerificada] = field(default_factory=list)
    seccoes: list[SeccaoDetetada] = field(default_factory=list)
    prazos_desencadeados: list[str] = field(default_factory=list)
    resumo: str = ""
    avisos: list[str] = field(default_factory=list)

    @property
    def citacoes_validas(self) -> list[CitacaoVerificada]:
        return [c for c in self.citacoes if c.valida]

    @property
    def citacoes_invalidas(self) -> list[CitacaoVerificada]:
        return [c for c in self.citacoes if not c.valida]

    def para_dict(self) -> dict:
        return {
            "nome_ficheiro": self.nome_ficheiro,
            "num_paginas": self.num_paginas,
            "num_caracteres": self.num_caracteres,
            "tipo_provavel": self.tipo_provavel,
            "resumo": self.resumo,
            "total_citacoes": len(self.citacoes),
            "citacoes_validas": [
                {"norma": f"{c.diploma}-{c.artigo}", "diploma": c.diploma,
                 "artigo": c.artigo, "contexto": c.contexto}
                for c in self.citacoes_validas
            ],
            "citacoes_invalidas": [
                {"norma": f"{c.diploma}-{c.artigo}", "diploma": c.diploma,
                 "artigo": c.artigo, "contexto": c.contexto}
                for c in self.citacoes_invalidas
            ],
            "seccoes": [
                {"nome": s.nome, "presente": s.presente, "posicao": s.posicao_aprox}
                for s in self.seccoes
            ],
            "prazos_desencadeados": self.prazos_desencadeados,
            "avisos": self.avisos,
        }


class AnalisadorPecas:
    """Analisa uma peça processual inteira, sem truncar."""

    def __init__(self, llm_client=None, rag=None):
        # Garante que o corpus de normas válidas está carregado (o validador
        # depende de NORMAS_VALIDAS, preenchido ao instanciar o RAG).
        if not NORMAS_VALIDAS:
            self._rag = rag or RAGJuridico()   # popula NORMAS_VALIDAS
        self._validador = ValidadorCitacoes()
        self._llm = llm_client

    def analisar(self, texto: str, nome_ficheiro: str = "",
                 num_paginas: int = 0) -> AnalisePeca:
        texto = texto or ""
        analise = AnalisePeca(
            nome_ficheiro=nome_ficheiro,
            num_paginas=num_paginas,
            num_caracteres=len(texto),
            tipo_provavel=self._detetar_tipo(texto),
        )
        if not texto.strip():
            analise.avisos.append("O documento não continha texto legível (pode ser um PDF digitalizado sem OCR).")
            return analise

        analise.citacoes = self._verificar_citacoes(texto)
        analise.seccoes = self._detetar_seccoes(texto)
        analise.prazos_desencadeados = self._detetar_prazos(texto)
        analise.resumo = self._resumir(texto, analise)

        if analise.citacoes_invalidas:
            analise.avisos.append(
                f"{len(analise.citacoes_invalidas)} citação(ões) não corresponde(m) a "
                "normas do corpus — verificar (pode ser erro de citação ou norma fora do corpus atual)."
            )
        return analise

    # ── Verificação de citações (o núcleo) ──────────────────────────────

    def _verificar_citacoes(self, texto: str) -> list[CitacaoVerificada]:
        resultado, vistos = [], set()
        for m in _PADRAO_NORMA.finditer(texto):
            artigo = m.group(1).upper().replace("--", "-")
            raw = m.group(2).strip().lower()
            diploma = _DIPLOMAS.get(raw, raw.upper())
            chave = f"{diploma}-{artigo}"
            if chave in vistos:
                continue
            vistos.add(chave)
            ini = max(0, m.start() - 45)
            fim = min(len(texto), m.end() + 45)
            contexto = "…" + texto[ini:fim].replace("\n", " ").strip() + "…"
            valida = self._validador.validar(diploma, artigo)
            resultado.append(CitacaoVerificada(diploma, artigo, valida, contexto))
        return resultado

    # ── Estrutura ───────────────────────────────────────────────────────

    def _detetar_seccoes(self, texto: str) -> list[SeccaoDetetada]:
        total = max(1, len(texto))
        out = []
        for nome, padrao in _SECCOES.items():
            m = padrao.search(texto)
            out.append(SeccaoDetetada(
                nome=nome,
                presente=m is not None,
                posicao_aprox=round((m.start() / total) * 100) if m else 0,
            ))
        return out

    # ── Prazos desencadeados ────────────────────────────────────────────

    def _detetar_prazos(self, texto: str) -> list[str]:
        # Só olha o início e o fim (onde a natureza da peça se revela)
        amostra = texto[:4000] + "\n" + texto[-2000:]
        prazos = []
        for _, (padrao, aviso) in _SINAIS_PRAZO.items():
            if padrao.search(amostra):
                prazos.append(aviso)
        return prazos

    # ── Tipo e resumo ───────────────────────────────────────────────────

    def _detetar_tipo(self, texto: str) -> str:
        import unicodedata
        t = unicodedata.normalize("NFKD", texto[:3000].lower())
        t = "".join(ch for ch in t if not unicodedata.combining(ch))
        # padrões SEM acentos (o texto foi normalizado acima)
        if re.search(r"peticao\s+inicial|vem\s+(?:o\s+autor\s+)?propor|intenta|propor\s+(?:a\s+)?(?:presente\s+)?acao", t):
            return "Petição inicial"
        if re.search(r"acusa(?:cao|-se)|deduz(?:-se)?\s+acusacao", t):
            return "Acusação"
        if re.search(r"contesta(?:cao|r)|impugna|deduz.*oposicao", t):
            return "Contestação"
        if re.search(r"sentenca|decisao\s+final|condeno|absolvo|julgo\s+(?:a\s+)?(?:acao|procedente|improcedente)", t):
            return "Sentença / Decisão"
        if re.search(r"recurso|recorre|alega(?:coes|r)", t):
            return "Recurso / Alegações"
        if re.search(r"requer(?:imento|-se|\s+a\s+v)", t):
            return "Requerimento"
        return "Peça processual (tipo não determinado)"

    def _resumir(self, texto: str, analise: AnalisePeca) -> str:
        if self._llm is not None:
            try:
                return self._resumir_llm(texto)
            except Exception as exc:
                logger.warning("pecas.resumo_llm_falhou", erro=str(exc)[:150])
        # Resumo determinístico: as primeiras frases substantivas
        frases = re.split(r"(?<=[.;])\s+", texto[:1500])
        frases = [f.strip() for f in frases if len(f.strip()) > 40][:3]
        base = " ".join(frases)
        return (base[:400] + "…") if base else "Documento sem resumo automático disponível."

    def _resumir_llm(self, texto: str) -> str:
        # Envia até ~12k caracteres (o essencial de peças longas cabe no início/fim)
        amostra = texto[:9000] + "\n\n[...]\n\n" + texto[-3000:] if len(texto) > 12000 else texto
        msg = self._llm.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            system=("És um jurista português. Resume a peça processual em 4-6 frases "
                    "objetivas: que tipo de peça é, o que pede/decide, os factos centrais "
                    "e os pontos jurídicos-chave. Não inventes; se algo não estiver claro, dá-o como incerto."),
            messages=[{"role": "user", "content": amostra}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "text", None)).strip()
