"""
ClassificadorJuridico — SNAJI
==============================
Substitui a heurística de palavras-chave por uma classificação via LLM.

Funcionalidades:
  - Detecta MÚLTIPLAS áreas jurídicas num mesmo caso (ex: penal + laboral)
  - Atribui peso/relevância a cada área (principal vs. secundária)
  - Identifica a(s) instância(s) judicial(ais) adequada(s)
  - Corre em modo stub (sem LLM) para testes — devolve resultado heurístico
  - Resultado é um dataclass estruturado, não uma string

Integração:
  - Este módulo é chamado pela ReasoningPipeline ANTES do RAG
  - O resultado ClassificacaoJuridica substitui o antigo TipoProcesso único
  - A pipeline usa todas as áreas para fazer RAG paralelo e merge ponderado
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


# ── Enumerações ────────────────────────────────────────────────────────────

class AreaJuridica(str, Enum):
    LABORAL         = "laboral"
    CIVIL           = "civil"
    PENAL           = "penal"
    ADMINISTRATIVO  = "administrativo"
    FAMILIA         = "familia"
    CONSUMO         = "consumo"
    DADOS_PESSOAIS  = "dados_pessoais"
    OUTRO           = "outro"


class Instancia(str, Enum):
    TRIBUNAL_TRABALHO       = "Tribunal do Trabalho"
    TRIBUNAL_CIVIL          = "Tribunal Cível"
    TRIBUNAL_CRIMINAL       = "Tribunal Criminal"
    TRIBUNAL_FAMILIA        = "Tribunal de Família e Menores"
    TRIBUNAL_ADMINISTRATIVO = "Tribunal Administrativo"
    TRIBUNAL_COMERCIAL      = "Tribunal do Comércio"
    MINISTERIO_PUBLICO      = "Ministério Público"
    CNPD                    = "CNPD (dados pessoais)"
    ARBITRAGEM_CONSUMO      = "Centro de Arbitragem de Conflitos de Consumo"
    DESCONHECIDA            = "A determinar"


# ── Dataclasses de resultado ───────────────────────────────────────────────

@dataclass
class AreaDetectada:
    area: AreaJuridica
    peso: float          # 0.0 – 1.0 (soma das áreas não precisa de ser 1.0)
    principal: bool      # True = área dominante do caso
    instancias: list[Instancia] = field(default_factory=list)
    justificacao: str = ""


@dataclass
class ClassificacaoJuridica:
    """
    Resultado da classificação de um caso.
    Pode conter múltiplas áreas para casos mistos.
    """
    areas: list[AreaDetectada]
    resumo: str                      # frase curta que descreve o caso
    via_llm: bool                    # True = classificação feita por LLM
    confianca: float = 1.0           # 0.0–1.0 (só relevante quando via_llm=True)

    @property
    def area_principal(self) -> AreaJuridica:
        """Área com maior peso."""
        if not self.areas:
            return AreaJuridica.OUTRO
        return max(self.areas, key=lambda a: a.peso).area

    @property
    def todas_as_areas(self) -> list[AreaJuridica]:
        return [a.area for a in self.areas]

    def peso_de(self, area: AreaJuridica) -> float:
        for a in self.areas:
            if a.area == area:
                return a.peso
        return 0.0


# ── Mapeamentos para fallback heurístico ──────────────────────────────────

_KEYWORDS: dict[AreaJuridica, list[str]] = {
    AreaJuridica.LABORAL: [
        "despedimento", "trabalho", "salário", "férias", "trabalhador",
        "empregador", "contrato de trabalho", "justa causa", "indemnização laboral",
        "horas extraordinárias", "baixa médica", "subsídio de desemprego",
    ],
    AreaJuridica.PENAL: [
        "suborno", "corrupção", "crime", "furto", "roubo", "homicídio",
        "ofensa", "ameaça", "burla", "coação", "arguido", "pena",
        "prisão", "detenção", "queixa-crime", "denúncia criminal",
    ],
    AreaJuridica.DADOS_PESSOAIS: [
        "dados pessoais", "rgpd", "privacidade", "consentimento",
        "tratamento de dados", "apagamento", "portabilidade", "cnpd",
    ],
    AreaJuridica.FAMILIA: [
        "divórcio", "filhos", "alimentos", "custódia", "casamento",
        "adoção", "família", "menores", "separação", "regulação parental",
    ],
    AreaJuridica.CONSUMO: [
        "consumidor", "produto", "garantia", "devolução", "compra",
        "venda", "defeito", "fornecedor", "livro de reclamações",
    ],
    AreaJuridica.CIVIL: [
        "contrato", "propriedade", "indemnização", "danos", "responsabilidade",
        "arrendamento", "herança", "dívida", "hipoteca", "escritura",
    ],
    AreaJuridica.ADMINISTRATIVO: [
        "estado", "administração", "município", "licença", "imposto",
        "multa", "recurso administrativo", "funcionário público", "câmara",
    ],
}

_INSTANCIAS_POR_AREA: dict[AreaJuridica, list[Instancia]] = {
    AreaJuridica.LABORAL:        [Instancia.TRIBUNAL_TRABALHO],
    AreaJuridica.PENAL:          [Instancia.TRIBUNAL_CRIMINAL, Instancia.MINISTERIO_PUBLICO],
    AreaJuridica.DADOS_PESSOAIS: [Instancia.CNPD, Instancia.TRIBUNAL_ADMINISTRATIVO],
    AreaJuridica.FAMILIA:        [Instancia.TRIBUNAL_FAMILIA],
    AreaJuridica.CONSUMO:        [Instancia.ARBITRAGEM_CONSUMO, Instancia.TRIBUNAL_CIVIL],
    AreaJuridica.CIVIL:          [Instancia.TRIBUNAL_CIVIL],
    AreaJuridica.ADMINISTRATIVO: [Instancia.TRIBUNAL_ADMINISTRATIVO],
    AreaJuridica.OUTRO:          [Instancia.DESCONHECIDA],
}

_PESO_ALTO = {
    "suborno", "corrupção", "crime", "arguido", "prisão",
    "pena", "homicídio", "furto", "roubo",
}


# ── Prompt para classificação via LLM ─────────────────────────────────────

_SYSTEM_CLASSIFICADOR = """És um classificador jurídico institucional português.
Recebes a descrição de um caso e devolves EXCLUSIVAMENTE JSON válido, sem markdown.
Podes identificar MÚLTIPLAS áreas jurídicas se o caso as envolver simultaneamente.
Sê rigoroso: só inclui uma área se houver evidência clara no texto.
"""

_PROMPT_CLASSIFICACAO = """
Analisa este caso e classifica-o juridicamente.

ÁREAS POSSÍVEIS (podes usar várias):
- laboral: conflitos laborais, despedimentos, salários, contratos de trabalho
- civil: contratos civis, propriedade, danos, arrendamento, dívidas
- penal: crimes, arguidos, queixas criminais, prisão, coação
- administrativo: Estado, municípios, licenças, impostos, funcionários públicos
- familia: divórcio, filhos, alimentos, custódia, casamento
- consumo: relações consumidor-fornecedor, garantias, defeitos
- dados_pessoais: RGPD, privacidade, tratamento de dados
- outro: não se enquadra nas categorias acima

CASO:
{caso}

Responde EXCLUSIVAMENTE com este JSON:
{{
  "areas": [
    {{
      "area": "nome_da_area",
      "peso": 0.8,
      "principal": true,
      "instancias": ["Tribunal do Trabalho"],
      "justificacao": "porque se aplica"
    }},
    {{
      "area": "nome_da_area_secundaria",
      "peso": 0.3,
      "principal": false,
      "instancias": ["Tribunal Criminal"],
      "justificacao": "porque se aplica secundariamente"
    }}
  ],
  "resumo": "frase curta que descreve o caso",
  "confianca": 0.9
}}

REGRAS:
- peso entre 0.1 e 1.0 (área principal >= 0.5)
- instancias: lista de strings com o nome do tribunal ou entidade competente
- inclui SEMPRE pelo menos uma área
- se o caso for misto, inclui todas as áreas relevantes
"""


# ── Função heurística de fallback ─────────────────────────────────────────

def _classificar_heuristico(texto: str) -> ClassificacaoJuridica:
    """
    Fallback sem LLM.
    Mantém compatibilidade com os testes existentes.
    Pode detectar múltiplas áreas mas com menor precisão.
    """
    texto_lower = texto.lower()
    pontuacao: dict[AreaJuridica, int] = {a: 0 for a in AreaJuridica}

    for area, keywords in _KEYWORDS.items():
        for kw in keywords:
            if kw in texto_lower:
                pontuacao[area] += 3 if kw in _PESO_ALTO else 1

    # Remove áreas sem pontuação
    areas_com_pontos = [(a, p) for a, p in pontuacao.items() if p > 0]

    if not areas_com_pontos:
        return ClassificacaoJuridica(
            areas=[AreaDetectada(
                area=AreaJuridica.OUTRO,
                peso=1.0,
                principal=True,
                instancias=_INSTANCIAS_POR_AREA[AreaJuridica.OUTRO],
            )],
            resumo="Caso não classificado automaticamente.",
            via_llm=False,
            confianca=0.3,
        )

    # Normaliza pesos
    max_pts = max(p for _, p in areas_com_pontos)
    areas_detectadas = []
    for area, pts in sorted(areas_com_pontos, key=lambda x: -x[1]):
        peso = pts / max_pts
        if peso >= 0.2:  # Só inclui áreas com pelo menos 20% do peso máximo
            areas_detectadas.append(AreaDetectada(
                area=area,
                peso=round(peso, 2),
                principal=(area == areas_com_pontos[0][0]),
                instancias=_INSTANCIAS_POR_AREA.get(area, [Instancia.DESCONHECIDA]),
            ))

    return ClassificacaoJuridica(
        areas=areas_detectadas,
        resumo=f"Caso classificado heuristicamente. Área principal: {areas_detectadas[0].area.value}.",
        via_llm=False,
        confianca=0.6,
    )


# ── Classe principal ───────────────────────────────────────────────────────

class ClassificadorJuridico:
    """
    Classificador de casos jurídicos via LLM.

    Uso com LLM:
        clf = ClassificadorJuridico(llm_client=anthropic_client)
        resultado = clf.classificar("Fui despedido e recebi ameaças do chefe")

    Uso sem LLM (testes):
        clf = ClassificadorJuridico()
        resultado = clf.classificar("Fui despedido e recebi ameaças do chefe")
    """

    def __init__(self, llm_client=None):
        self._llm = llm_client
        logger.info("classificador.init", via_llm=(llm_client is not None))

    def classificar(self, texto: str) -> ClassificacaoJuridica:
        """
        Classifica o caso. Usa LLM se disponível, heurística caso contrário.
        Nunca falha — em caso de erro do LLM, cai para heurística.
        """
        if self._llm is not None:
            try:
                return self._classificar_via_llm(texto)
            except Exception as exc:
                logger.warning("classificador.llm.fallback", erro=str(exc))
                resultado = _classificar_heuristico(texto)
                resultado.via_llm = False
                return resultado
        return _classificar_heuristico(texto)

    def _classificar_via_llm(self, texto: str) -> ClassificacaoJuridica:
        prompt = _PROMPT_CLASSIFICACAO.format(caso=texto)
        msg = self._llm.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            system=_SYSTEM_CLASSIFICADOR,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()

        # Remove markdown se vier por acidente
        raw = re.sub(r"```json|```", "", raw).strip()

        try:
            dados = json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if not m:
                raise ValueError("LLM não devolveu JSON válido")
            dados = json.loads(m.group())

        areas = []
        for item in dados.get("areas", []):
            try:
                area_enum = AreaJuridica(item["area"])
            except ValueError:
                area_enum = AreaJuridica.OUTRO

            # Mapeia strings de instâncias para enum (best-effort)
            instancias_raw = item.get("instancias", [])
            instancias = []
            for inst_str in instancias_raw:
                matched = False
                for inst_enum in Instancia:
                    if inst_str.lower() in inst_enum.value.lower() or inst_enum.value.lower() in inst_str.lower():
                        instancias.append(inst_enum)
                        matched = True
                        break
                if not matched:
                    instancias.append(Instancia.DESCONHECIDA)

            areas.append(AreaDetectada(
                area=area_enum,
                peso=float(item.get("peso", 0.5)),
                principal=bool(item.get("principal", False)),
                instancias=instancias or _INSTANCIAS_POR_AREA.get(area_enum, [Instancia.DESCONHECIDA]),
                justificacao=item.get("justificacao", ""),
            ))

        if not areas:
            raise ValueError("LLM devolveu lista de áreas vazia")

        logger.info("classificador.llm.done", areas=[a.area.value for a in areas])

        return ClassificacaoJuridica(
            areas=areas,
            resumo=dados.get("resumo", ""),
            via_llm=True,
            confianca=float(dados.get("confianca", 0.8)),
        )


# ── Compatibilidade retroativa ─────────────────────────────────────────────
# Mantém a função original para não quebrar testes existentes que a importem
# diretamente de pipeline.py (onde ainda existe).
# Esta função NÃO deve ser usada em código novo.

def classificar_tipo_processo_legado(texto: str):
    """
    Wrapper de compatibilidade.
    Usa a heurística e devolve a área principal como TipoProcesso.
    Apenas para compatibilidade com código legado.
    """
    from app.reasoning.pipeline import TipoProcesso
    resultado = _classificar_heuristico(texto)
    area = resultado.area_principal.value
    try:
        return TipoProcesso(area)
    except ValueError:
        return TipoProcesso.OUTRO
