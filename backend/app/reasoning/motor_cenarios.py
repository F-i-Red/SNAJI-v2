"""
Motor de Cenários de Resolução — SNAJI (Especificação V8, §2 e §3)
===================================================================
Para cada caso analisado, gera ATÉ TRÊS cenários de resolução,
correspondentes a três lentes interpretativas reais da prática judiciária:

  GARANTISTA        — máxima proteção dos direitos fundamentais e das
                      garantias processuais ("qual a solução que melhor
                      protege a parte mais fraca?")
  LEGALISTA         — aplicação estrita da letra da lei, sem extensão
                      interpretativa ("o que diz exatamente a norma?")
  CONSEQUENCIALISTA — ponderação dos efeitos práticos; orientação da
                      jurisprudência maioritária ("como têm os tribunais
                      efetivamente decidido casos análogos?")

REGRAS DO MOTOR (§2):
  - Só são apresentados os cenários juridicamente viáveis (1, 2 ou 3).
  - Se as lentes convergem, apresenta-se UMA solução com a indicação
    expressa "as três abordagens convergem" — sinal de caso claro.
  - Cada cenário: fundamentação normativa VALIDADA contra o corpus
    (ValidadorCitacoes — nenhuma norma inventada sobrevive), riscos e
    contra-argumentos, e grau qualitativo de solidez (nunca percentagens).

SAÍDA DUPLA (§3):
  - Registo técnico e registo cidadão gerados a partir da MESMA
    fundamentação; o registo cidadão deriva do técnico (nunca é
    independente) e é sempre informativo, nunca prescritivo.

DEONTOLOGIA:
  - O motor informa ("casos com estas características seguem tipicamente
    a via X"); nunca prescreve ("deve processar Y").
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional

import structlog

from app.rag.motor import RAGJuridico, ValidadorCitacoes

logger = structlog.get_logger(__name__)


RESSALVA_CENARIOS = (
    "Os cenários apresentados são informação jurídica de carácter geral, "
    "gerados por três abordagens interpretativas distintas. Não constituem "
    "consulta jurídica (Lei n.º 49/2004) nem predizem o resultado de qualquer "
    "processo concreto. A avaliação do seu caso exige um profissional habilitado."
)


class Lente(str, Enum):
    GARANTISTA        = "garantista"
    LEGALISTA         = "legalista"
    CONSEQUENCIALISTA = "consequencialista"


DESCRICAO_LENTES: dict[Lente, tuple[str, str]] = {
    # (descrição técnica, descrição em linguagem clara)
    Lente.GARANTISTA: (
        "Máxima proteção dos direitos fundamentais e das garantias processuais; "
        "na dúvida, prevalece a posição da parte mais vulnerável.",
        "Uma leitura que protege ao máximo os direitos das pessoas, sobretudo da parte mais fraca.",
    ),
    Lente.LEGALISTA: (
        "Aplicação estrita da letra da lei, sem extensão interpretativa.",
        "Uma leitura à letra da lei: o que está escrito é o que conta.",
    ),
    Lente.CONSEQUENCIALISTA: (
        "Ponderação dos efeitos práticos da decisão; alinhamento com a "
        "orientação maioritária da jurisprudência.",
        "Uma leitura prática: como é que os tribunais têm decidido casos parecidos.",
    ),
}

SOLIDEZ_VALORES = ("elevada", "media", "baixa")


@dataclass
class Cenario:
    lente: Lente
    titulo: str
    sentido: str                  # ex.: "procedente" | "improcedente" | "condenacao" | "absolvicao" | "misto"
    solucao_tecnica: str          # registo técnico
    solucao_cidada: str = ""      # registo em linguagem clara (derivado do técnico)
    fundamentacao_normas: list[str] = field(default_factory=list)   # ["CT-387", "CC-483"] — validadas
    riscos: str = ""              # contra-argumentos e fragilidades
    riscos_cidadao: str = ""
    solidez: str = "media"        # elevada | media | baixa (nunca percentagens)
    viavel: bool = True
    normas_rejeitadas: list[str] = field(default_factory=list)      # citações que falharam a validação

    def para_dict(self) -> dict:
        d = asdict(self)
        d["lente"] = self.lente.value
        d["lente_descricao_tecnica"] = DESCRICAO_LENTES[self.lente][0]
        d["lente_descricao_cidada"] = DESCRICAO_LENTES[self.lente][1]
        return d


@dataclass
class ResultadoCenarios:
    cenarios: list[Cenario]
    convergencia: bool            # True se as lentes viáveis convergem no mesmo sentido
    sintese_tecnica: str
    sintese_cidada: str
    normas_rejeitadas_total: list[str]
    ressalva: str = RESSALVA_CENARIOS
    via_llm: bool = False

    def para_dict(self) -> dict:
        return {
            "cenarios": [c.para_dict() for c in self.cenarios],
            "convergencia": self.convergencia,
            "sintese_tecnica": self.sintese_tecnica,
            "sintese_cidada": self.sintese_cidada,
            "normas_rejeitadas_total": self.normas_rejeitadas_total,
            "ressalva": self.ressalva,
            "via_llm": self.via_llm,
        }


# ── Prompts ──────────────────────────────────────────────────────────────────

_SYSTEM_CENARIOS = """És um jurista português sénior num sistema institucional de informação jurídica.
Analisas o caso por TRÊS lentes interpretativas e devolves EXCLUSIVAMENTE JSON válido, sem markdown.

REGRAS INVIOLÁVEIS:
- Só marcas "viavel": true quando a lente produz uma solução juridicamente sustentável.
- Citas APENAS artigos que constem das normas fornecidas — nunca inventes citações.
- "solidez" é qualitativa: "elevada", "media" ou "baixa". Nunca uses percentagens.
- Linguagem informativa, nunca prescritiva: descreves o que "tipicamente sucede",
  nunca dizes o que a pessoa "deve fazer".
- "sentido" resume o desfecho: "procedente", "improcedente", "condenacao",
  "absolvicao", "misto" ou equivalente curto."""

_PROMPT_CENARIOS = """CASO:
{caso}

NORMAS RELEVANTES DO CORPUS PORTUGUÊS (cita apenas destas):
{normas}

Analisa o caso pelas três lentes e devolve:
{{
  "cenarios": [
    {{
      "lente": "garantista|legalista|consequencialista",
      "viavel": true,
      "titulo": "título curto do cenário",
      "sentido": "procedente|improcedente|condenacao|absolvicao|misto",
      "solucao_tecnica": "análise técnica: qualificação, normas com artigo e diploma, desfecho típico",
      "riscos": "contra-argumentos e fragilidades desta leitura"
    }}
  ],
  "sintese_tecnica": "síntese comparativa das lentes em 2-3 frases"
}}
Inclui as TRÊS lentes no array (com "viavel": false e justificação em "riscos" quando uma lente não sustenta solução)."""

_SYSTEM_TRADUCAO = """És um tradutor de linguagem jurídica para linguagem clara, num sistema institucional português.
Recebes textos técnicos e devolves EXCLUSIVAMENTE JSON com as versões em linguagem clara.

REGRAS INVIOLÁVEIS:
- NÃO acrescentas factos, normas nem conclusões: apenas reformulas o que está no texto técnico.
- Frases curtas; sem latinismos nem jargão ("exceção perentória" → "um argumento que, a provar-se, faz o pedido cair").
- Registo informativo, nunca prescritivo: "casos assim seguem tipicamente...", nunca "deve fazer...".
- Mantém os números de artigos quando citados, explicando-os ("artigo 387.º do Código do Trabalho — o prazo para contestar um despedimento")."""

_PROMPT_TRADUCAO = """Traduz para linguagem clara, sem acrescentar nada:

{blocos}

Devolve:
{{
  "traducoes": ["tradução do bloco 1", "tradução do bloco 2", ...]
}}
(uma tradução por bloco, pela mesma ordem)"""


# ── Motor ────────────────────────────────────────────────────────────────────

class MotorCenarios:
    MODELO = "claude-sonnet-4-20250514"
    MAX_TOKENS = 6000
    MAX_CONTINUACOES = 4

    def __init__(self, llm_client=None):
        self._llm = llm_client
        self._rag = RAGJuridico()
        self._validator = ValidadorCitacoes()
        logger.info("motor.cenarios.init", via_llm=(llm_client is not None))

    # ── API pública ─────────────────────────────────────────────────────

    def gerar(self, texto_caso: str, top_k_normas: int = 8) -> ResultadoCenarios:
        """
        Gera os cenários de resolução para um caso (texto livre ou Ficha
        de Factos do Instrutor). Cada cenário sai validado e nos dois registos.
        """
        normas = self._rag.search(texto_caso, top_k=top_k_normas)
        normas_txt = "\n".join(
            f"• Art. {c.artigo}.º {c.diploma} — {(c.epigrase + ': ') if getattr(c, 'epigrase', '') else ''}{c.texto[:180]}"
            for c in normas
        ) or "— sem normas recuperadas —"

        if self._llm is not None:
            cenarios, sintese_tec = self._gerar_llm(texto_caso, normas_txt)
            via_llm = True
        else:
            cenarios, sintese_tec = self._gerar_stub(texto_caso, normas)
            via_llm = False

        # 1) Validação anti-alucinação de cada cenário
        rejeitadas_total: list[str] = []
        for c in cenarios:
            validas, rejeitadas = self._validator.extrair_e_validar(c.solucao_tecnica)
            c.fundamentacao_normas = sorted({f"{v['diploma']}-{v['artigo']}" for v in validas})
            c.normas_rejeitadas = sorted({f"{r['diploma']}-{r['artigo']}" for r in rejeitadas})
            rejeitadas_total.extend(c.normas_rejeitadas)
            if c.normas_rejeitadas:
                c.solucao_tecnica += (
                    f" [AVISO DE VALIDAÇÃO: as citações {', '.join(c.normas_rejeitadas)} "
                    f"não constam do corpus e foram desconsideradas na fundamentação.]"
                )
                if c.solidez == "elevada":
                    c.solidez = "media"
            if c.solidez not in SOLIDEZ_VALORES:
                c.solidez = "media"

        # 2) Regra da viabilidade: apenas cenários viáveis são apresentados
        viaveis = [c for c in cenarios if c.viavel]
        if not viaveis:
            viaveis = cenarios[:1]  # nunca devolver vazio: mostra a leitura menos frágil
            if viaveis:
                viaveis[0].viavel = True
                viaveis[0].solidez = "baixa"

        # 3) Regra da convergência (§2): mesmas conclusões → uma só solução
        sentidos = {c.sentido for c in viaveis}
        convergencia = len(viaveis) >= 2 and len(sentidos) == 1
        if convergencia:
            base = max(viaveis, key=lambda c: SOLIDEZ_VALORES.index(c.solidez) * -1)
            base.titulo = "As três abordagens convergem: " + base.titulo
            base.solidez = "elevada"
            base.solucao_tecnica = (
                "CONVERGÊNCIA DAS LENTES (garantista, legalista e consequencialista) "
                "no mesmo sentido — indicador de caso juridicamente claro. " + base.solucao_tecnica
            )
            viaveis = [base]

        # 4) Saída dupla: o registo cidadão deriva do técnico (§3)
        self._gerar_registo_cidadao(viaveis, sintese_tec)
        sintese_cid = viaveis[0].__dict__.get("_sintese_cidada_tmp", "")
        for c in viaveis:
            c.__dict__.pop("_sintese_cidada_tmp", None)

        resultado = ResultadoCenarios(
            cenarios=viaveis,
            convergencia=convergencia,
            sintese_tecnica=sintese_tec,
            sintese_cidada=sintese_cid,
            normas_rejeitadas_total=sorted(set(rejeitadas_total)),
            via_llm=via_llm,
        )
        logger.info(
            "cenarios.gerados",
            n=len(viaveis), convergencia=convergencia,
            rejeitadas=len(resultado.normas_rejeitadas_total), via_llm=via_llm,
        )
        return resultado

    # ── Geração LLM ─────────────────────────────────────────────────────

    def _gerar_llm(self, caso: str, normas_txt: str) -> tuple[list[Cenario], str]:
        raw = self._chamar_llm_completo(
            _SYSTEM_CENARIOS,
            _PROMPT_CENARIOS.format(caso=caso, normas=normas_txt),
        )
        dados = self._extrair_json(raw)
        cenarios: list[Cenario] = []
        for item in dados.get("cenarios", []):
            try:
                lente = Lente(str(item.get("lente", "")).strip().lower())
            except ValueError:
                continue
            cenarios.append(Cenario(
                lente=lente,
                titulo=str(item.get("titulo", "")).strip() or lente.value.capitalize(),
                sentido=str(item.get("sentido", "misto")).strip().lower(),
                solucao_tecnica=str(item.get("solucao_tecnica", "")).strip(),
                riscos=str(item.get("riscos", "")).strip(),
                solidez=str(item.get("solidez", "media")).strip().lower(),
                viavel=bool(item.get("viavel", True)),
            ))
        # Garante no máximo uma entrada por lente
        vistos: set[Lente] = set()
        unicos = []
        for c in cenarios:
            if c.lente not in vistos:
                vistos.add(c.lente)
                unicos.append(c)
        return unicos[:3], str(dados.get("sintese_tecnica", "")).strip()

    def _gerar_registo_cidadao(self, cenarios: list[Cenario], sintese_tec: str) -> None:
        """Deriva o registo cidadão do técnico — nunca de forma independente (§3)."""
        blocos = []
        for c in cenarios:
            blocos.append(f"[CENÁRIO {c.lente.value}] {c.solucao_tecnica}")
            blocos.append(f"[RISCOS {c.lente.value}] {c.riscos or 'sem riscos assinalados'}")
        blocos.append(f"[SÍNTESE] {sintese_tec or 'sem síntese'}")

        if self._llm is not None:
            try:
                raw = self._chamar_llm_completo(
                    _SYSTEM_TRADUCAO,
                    _PROMPT_TRADUCAO.format(blocos="\n\n".join(
                        f"BLOCO {i+1}: {b}" for i, b in enumerate(blocos)
                    )),
                )
                trad = self._extrair_json(raw).get("traducoes", [])
            except Exception as exc:
                logger.warning("cenarios.traducao.fallback", erro=str(exc))
                trad = []
        else:
            trad = []

        if len(trad) != len(blocos):
            trad = [self._simplificar_stub(b) for b in blocos]

        i = 0
        for c in cenarios:
            c.solucao_cidada = trad[i]; i += 1
            c.riscos_cidadao = trad[i]; i += 1
        if cenarios:
            cenarios[0].__dict__["_sintese_cidada_tmp"] = trad[i]

    # ── Geração stub (sem LLM) ──────────────────────────────────────────

    def _gerar_stub(self, caso: str, normas) -> tuple[list[Cenario], str]:
        """Cenários deterministas para testes/demonstração sem LLM."""
        refs = [f"art. {c.artigo}.º {c.diploma}" for c in normas[:3]]
        cite = "; ".join(refs) if refs else "as normas aplicáveis"
        caso_l = caso.lower()

        if "despedimento" in caso_l and "justa causa" in caso_l:
            # Caso claro → as três lentes convergem
            base = Cenario(
                lente=Lente.LEGALISTA,
                titulo="Ilicitude do despedimento por falta de justa causa",
                sentido="procedente",
                solucao_tecnica=(
                    f"O despedimento sem invocação e prova de justa causa é ilícito; "
                    f"a ação de impugnação segue tipicamente com procedência, com as "
                    f"consequências indemnizatórias legais ({cite}). [modo stub]"
                ),
                riscos="A prova da inexistência de justa causa e o cumprimento do prazo de impugnação são determinantes.",
                solidez="elevada",
            )
            garant = Cenario(lente=Lente.GARANTISTA, titulo=base.titulo, sentido="procedente",
                             solucao_tecnica=base.solucao_tecnica, riscos=base.riscos, solidez="elevada")
            conseq = Cenario(lente=Lente.CONSEQUENCIALISTA, titulo=base.titulo, sentido="procedente",
                             solucao_tecnica=base.solucao_tecnica, riscos=base.riscos, solidez="elevada")
            return [garant, base, conseq], (
                "As três lentes convergem na ilicitude do despedimento sem justa causa; "
                "a divergência prática limita-se ao cálculo indemnizatório. [modo stub]"
            )

        return [
            Cenario(
                lente=Lente.GARANTISTA,
                titulo="Leitura protetora da parte mais vulnerável",
                sentido="procedente",
                solucao_tecnica=f"Numa leitura garantista, a tutela da parte mais fraca conduz tipicamente à procedência da pretensão, fundada em {cite}. [modo stub]",
                riscos="Pode exigir interpretação extensiva que nem todos os tribunais acompanham.",
                solidez="media",
            ),
            Cenario(
                lente=Lente.LEGALISTA,
                titulo="Aplicação estrita da letra da lei",
                sentido="misto",
                solucao_tecnica=f"Na letra estrita da lei, o desfecho depende do preenchimento literal dos pressupostos de {cite}; sem prova cabal, o resultado é incerto. [modo stub]",
                riscos="A rigidez literal pode desconsiderar circunstâncias relevantes do caso concreto.",
                solidez="media",
            ),
            Cenario(
                lente=Lente.CONSEQUENCIALISTA,
                titulo="Orientação da prática judiciária",
                sentido="misto",
                solucao_tecnica=f"A prática dos tribunais em casos análogos pondera os efeitos concretos; a orientação dominante aplica {cite} com juízos de proporcionalidade. [modo stub]",
                riscos="Sem jurisprudência carregada no corpus, esta lente tem base documental limitada.",
                solidez="baixa",
            ),
        ], "As lentes divergem no desfecho: caso com zonas de incerteza jurídica. [modo stub]"

    @staticmethod
    def _simplificar_stub(texto: str) -> str:
        """Tradução determinista mínima para linguagem clara (sem LLM)."""
        t = re.sub(r"^\[[^\]]+\]\s*", "", texto)
        substituicoes = {
            "procedência da pretensão": "dar razão a quem pede",
            "procedência": "dar razão a quem apresenta o caso",
            "ilícito": "contrário à lei",
            "ilicitude": "violação da lei",
            "pressupostos": "condições exigidas pela lei",
            "quantum indemnizatório": "valor da indemnização",
            "consequências indemnizatórias legais": "direito a uma indemnização prevista na lei",
            "interpretação extensiva": "uma leitura mais alargada da lei",
            "jurisprudência": "decisões anteriores dos tribunais",
            "tutela": "proteção",
        }
        for tecnico, claro in substituicoes.items():
            t = t.replace(tecnico, claro)
        return ("Em linguagem simples: " + t).strip()

    # ── LLM: chamada com anti-corte (§6) ────────────────────────────────

    def _chamar_llm_completo(self, system: str, prompt: str) -> str:
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
            logger.info("cenarios.llm.continuacao", iteracao=i + 1)
            mensagens = mensagens + [
                {"role": "assistant", "content": texto},
                {"role": "user", "content": "Continua exatamente de onde paraste, sem repetir nada."},
            ]
        return "".join(partes).strip()

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


# Instância partilhada
motor_cenarios = MotorCenarios(llm_client=None)
