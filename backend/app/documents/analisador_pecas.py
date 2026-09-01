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
import re as _re_mod
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
    num_palavras: int = 0
    citacoes: list[CitacaoVerificada] = field(default_factory=list)
    seccoes: list[SeccaoDetetada] = field(default_factory=list)
    prazos_desencadeados: list[str] = field(default_factory=list)
    resumo: str = ""
    objeto_provavel: str = ""   # pedido identificado na peça (CPC-596/LJP-60)
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
            "num_palavras": self.num_palavras,
            "num_caracteres": self.num_caracteres,
            "tipo_provavel": self.tipo_provavel,
            "objeto_provavel": self.objeto_provavel,
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

    # Fórmulas que anunciam o pedido — a formulação do objeto do litígio
    _PADRAO_PEDIDO = _re_mod.compile(
        r"(?:nestes\s+termos.{0,120}?)?"
        r"(?:requer(?:-se)?|pede(?:-se)?|termina\s+pedindo|conclui\s+pedindo)"
        r"\s*(?:a\s+v\.?\s*ex\.?[ªa]?\.?)?\s*,?\s*(?:que\s+)?",
        _re_mod.IGNORECASE | _re_mod.DOTALL,
    )
    _ABREVIATURAS = [
        ("V.", "V\x00"), ("Ex.", "Ex\x00"), ("art.", "art\x00"),
        ("arts.", "arts\x00"), ("n.º", "n\x00º"), ("Sr.", "Sr\x00"),
        ("Dr.", "Dr\x00"), ("Ld.", "Ld\x00"), ("Prof.", "Prof\x00"),
    ]

    def _extrair_objeto(self, texto: str) -> str:
        """Identifica o objeto provável da peça — a frase do pedido.
        Determinístico: localiza a ÚLTIMA fórmula consagrada ('nestes termos…
        requer… que', 'termina pedindo') e devolve o que se pede, cortado na
        primeira frase completa. É APOIO à identificação exigida pelo
        CPC-596/LJP-60 — o profissional confirma sempre."""
        ocorrencias = list(self._PADRAO_PEDIDO.finditer(texto))
        if not ocorrencias:
            return ""
        resto = texto[ocorrencias[-1].end():][:500]
        # proteger abreviaturas para o corte de frase não partir nelas
        for original, marcador in self._ABREVIATURAS:
            resto = resto.replace(original, marcador)
        m_fim = _re_mod.search(r"[.;]\s+(?=[A-ZÀ-Ú])|[.;]\s*$|\n\s*\n", resto)
        objeto = resto[: m_fim.start()] if m_fim else resto[:300]
        for original, marcador in self._ABREVIATURAS:
            objeto = objeto.replace(marcador, original)
        objeto = _re_mod.sub(r"\s+", " ", objeto).strip(" ,;:.")
        if len(objeto) < 15:
            return ""
        if len(objeto) > 300:
            objeto = objeto[:300].rstrip() + "…"
        return objeto[0].upper() + objeto[1:]

    def analisar(self, texto: str, nome_ficheiro: str = "",
                 num_paginas: int = 0) -> AnalisePeca:
        texto = texto or ""
        analise = AnalisePeca(
            nome_ficheiro=nome_ficheiro,
            num_paginas=num_paginas,
            num_palavras=len(texto.split()),
            num_caracteres=len(texto),
            tipo_provavel=self._detetar_tipo(texto),
        )
        analise.objeto_provavel = self._extrair_objeto(texto)
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

    # Indícios por tipo de peça, com peso. Contam-se todos e vence o tipo com
    # mais indícios — em vez de devolver o primeiro padrão que casa.
    #
    # Porquê: uma peça descreve frequentemente a tramitação anterior, e nessa
    # descrição aparecem palavras de outros tipos. Um recurso que relata "veio
    # o exequente contestar" era classificado como contestação, apenas porque
    # esse padrão era testado primeiro. Os termos que identificam a natureza
    # da própria peça (quem a subscreve e o que pede) pesam mais do que os que
    # podem surgir na narração do processado.
    _INDICIOS: list[tuple[str, list[tuple[str, int]]]] = [
        ("Recurso / Alegações", [
            (r"\binterp(?:or|oe|os)\w*\s+(?:o\s+)?(?:presente\s+)?recurso", 5),
            (r"\bconclui\w*\s+as\s+suas\s+alegacoes", 5),
            (r"\bora\s+recorrente\b", 4),
            (r"\brecorrente\b", 2),
            (r"\btribunal\s+a\s+quo\b", 3),
            (r"\bdeve\w*\s+ser\s+revogad", 3),
            (r"\balegacoes\s+de\s+recurso\b", 4),
            (r"\brecurso\b", 1),
        ]),
        ("Petição inicial", [
            (r"\bpeticao\s+inicial\b", 5),
            (r"\bvem\s+(?:o|a)\s+\w+\s+propor\b", 5),
            (r"\bpropor\s+(?:a\s+)?(?:presente\s+)?acao\b", 4),
            (r"\bintenta\w*\b", 3),
            (r"\bcita(?:cao|r)\s+d[oa]\s+re[u\b]", 2),
        ]),
        ("Contestação", [
            (r"\bvem\s+(?:o|a)\s+\w+\s+contestar\b", 4),
            (r"\bapresenta\w*\s+contestacao\b", 5),
            (r"\bdeduz\w*\s+oposicao\b", 4),
            (r"\bimpugna\w*\s+(?:especificadamente|os\s+factos)\b", 4),
            (r"\bcontestacao\b", 1),
        ]),
        ("Acusação", [
            (r"\bdeduz\w*\s+acusacao\b", 5),
            (r"\bacusa\s+o\s+arguido\b", 5),
            (r"\bministerio\s+publico\b.{0,60}\bacusa", 4),
        ]),
        ("Sentença / Decisão", [
            (r"\bjulgo\s+(?:a\s+)?(?:acao\s+)?(?:procedente|improcedente)", 5),
            (r"\b(?:condeno|absolvo)\b", 5),
            (r"\bnestes\s+termos.{0,40}\bdecid", 4),
            (r"\bsentenca\b", 1),
        ]),
        ("Requerimento", [
            (r"\brequer\s+a\s+v\.?\s*ex", 5),
            (r"\brequerimento\b", 2),
        ]),
    ]

    def _detetar_tipo(self, texto: str) -> str:
        import unicodedata
        t = unicodedata.normalize("NFKD", texto[:6000].lower())
        t = "".join(ch for ch in t if not unicodedata.combining(ch))

        pontuacao: dict[str, int] = {}
        for tipo, padroes in self._INDICIOS:
            total = 0
            for padrao, peso in padroes:
                if re.search(padrao, t):
                    total += peso
            if total:
                pontuacao[tipo] = total

        if not pontuacao:
            return "Peça processual (tipo não determinado)"
        melhor = max(pontuacao.items(), key=lambda x: x[1])
        # Empate ou indício demasiado ténue: não arriscar uma etiqueta errada.
        if melhor[1] < 3:
            return "Peça processual (tipo não determinado)"
        return melhor[0]

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
        from app.core.llm import obter_modelo
        msg = self._llm.messages.create(
            model=obter_modelo(),
            max_tokens=600,
            system=("És um jurista português. Resume a peça processual em 4-6 frases "
                    "objetivas: que tipo de peça é, o que pede/decide, os factos centrais "
                    "e os pontos jurídicos-chave. Não inventes; se algo não estiver claro, dá-o como incerto."),
            messages=[{"role": "user", "content": amostra}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "text", None)).strip()
