"""
Motor de Cenários de Resolução — SNAJI (Especificação V8, §2 e §3)
===================================================================
Para cada caso analisado, gera ATÉ TRÊS cenários de resolução,
correspondentes a três lentes interpretativas reais da prática judiciária:

Apresentadas pela ordem do raciocínio jurídico — primeiro o que a lei diz,
depois os princípios, por fim as consequências:

  LEGALISTA         — aplicação estrita da letra da lei, sem extensão
                      interpretativa ("o que diz exatamente a norma?")
  GARANTISTA        — máxima proteção dos direitos fundamentais e das
                      garantias processuais ("qual a solução que melhor
                      protege a parte mais fraca?")
  CONSEQUENCIALISTA — ponderação dos efeitos práticos da decisão para as
                      partes ("que consequências concretas resultam de cada
                      solução?"). NÃO afirma tendências jurisprudenciais que
                      não estejam sustentadas em acórdãos fornecidos.

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


# Ordem de apresentação, que reproduz a sequência do raciocínio jurídico:
# primeiro a qualificação e a subsunção (que diz a letra da lei), depois a
# interpretação à luz dos princípios e garantias, por fim a ponderação dos
# efeitos práticos da solução. Apresentar o garantismo à cabeça sugeriria
# que o sistema toma partido antes de qualificar os factos.
ORDEM_LENTES = [Lente.LEGALISTA, Lente.GARANTISTA, Lente.CONSEQUENCIALISTA]

# Caracteres de cada norma enviados ao modelo. Ajustável em .env com
# SNAJI_MAX_CARACTERES_NORMA para casos com muitos artigos extensos.
import os as _os
try:
    _MAX_CARACTERES_NORMA = int(_os.getenv("SNAJI_MAX_CARACTERES_NORMA", "2500"))
except ValueError:
    _MAX_CARACTERES_NORMA = 2500


DESCRICAO_LENTES: dict[Lente, tuple[str, str]] = {
    # (descrição técnica, descrição em linguagem clara)
    Lente.GARANTISTA: (
        "Máxima proteção dos direitos fundamentais e das garantias processuais; "
        "na dúvida, prevalece a posição da parte mais vulnerável — e, no processo "
        "penal, as garantias de defesa do arguido (in dubio pro reo; art. 32.º CRP).",
        "Uma leitura que protege ao máximo os direitos das pessoas — a parte mais "
        "fraca nos conflitos entre particulares e, num processo-crime, quem é acusado.",
    ),
    Lente.LEGALISTA: (
        "Aplicação estrita da letra da lei, sem extensão interpretativa.",
        "Uma leitura à letra da lei: o que está escrito é o que conta.",
    ),
    Lente.CONSEQUENCIALISTA: (
        "Ponderação dos efeitos práticos de cada solução para as partes. Só "
        "invoca orientação jurisprudencial quando há acórdãos que a sustentem.",
        "Uma leitura prática: que consequências concretas tem cada caminho.",
    ),
}

SOLIDEZ_VALORES = ("elevada", "media", "baixa")

# Sentidos equivalentes, para a regra de convergência.
#
# A convergência exigia que as três lentes devolvessem exactamente a mesma
# palavra. Como o modelo produz por vezes variantes fora da lista pedida
# ("favoravel" em vez de "procedente", "incerto" em vez de "misto"), casos
# em que as três leituras concordavam podiam não ser reconhecidos como
# convergentes — por diferença de vocabulário, não de conteúdo.
# Sentidos reduzidos a três direcções. O modelo não usa sempre a mesma
# palavra — escreve "tendência condenatória" onde antes escrevia "condenação",
# e "tipicamente favorável" onde escrevia "procedente". Sem cobrir estas
# variantes, duas lentes que concordam eram contadas como divergentes e a
# convergência nunca era declarada.
_SENTIDOS_EQUIVALENTES = {
    # Favorável a quem expõe o caso / procedência da pretensão
    "procedente": "favoravel", "favoravel": "favoravel",
    "condenacao": "favoravel", "condenatoria": "favoravel",
    "tipicamente favoravel": "favoravel",
    "tendencia condenatoria": "favoravel",
    "tendencialmente favoravel": "favoravel",
    "tendencia favoravel": "favoravel",
    "provavelmente procedente": "favoravel",

    # Desfavorável / improcedência
    "improcedente": "desfavoravel", "desfavoravel": "desfavoravel",
    "absolvicao": "desfavoravel", "absolutoria": "desfavoravel",
    "tipicamente desfavoravel": "desfavoravel",
    "tendencia absolutoria": "desfavoravel",
    "tendencialmente desfavoravel": "desfavoravel",
    "tendencia desfavoravel": "desfavoravel",
    "provavelmente improcedente": "desfavoravel",

    # Sem direcção
    "misto": "incerto", "incerto": "incerto", "indeterminado": "incerto",
    "desfecho incerto": "incerto", "resultado incerto": "incerto",
    "inviavel": "incerto", "nao aplicavel": "incerto",
}


def _sentido_normalizado(valor: str) -> str:
    """Reduz o sentido a uma de três direcções, ignorando o vocabulário."""
    import unicodedata
    v = unicodedata.normalize("NFKD", (valor or "").strip().lower())
    v = "".join(c for c in v if not unicodedata.combining(c))
    return _SENTIDOS_EQUIVALENTES.get(v, v)


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
    # Lentes que se declararam sem solução sustentável neste caso. Não são
    # apresentadas como cenário, mas são declaradas: uma lente que
    # simplesmente desaparecia levantava a dúvida de ter falhado, quando na
    # verdade se absteve por não ter fundamento honesto a oferecer.
    lentes_omitidas: list[dict] = field(default_factory=list)
    # Lentes que convergiram com a principal e não são apresentadas em
    # destaque. Mantidas para consulta e para a versão impressa.
    cenarios_convergentes: list["Cenario"] = field(default_factory=list)
    ressalva: str = RESSALVA_CENARIOS
    via_llm: bool = False
    percurso: list[dict] = field(default_factory=list)   # explicabilidade (V8.1)
    perspetiva: str = "propria"        # "propria" | "contraparte" (contraditório)

    def para_dict(self) -> dict:
        return {
            "cenarios": [c.para_dict() for c in self.cenarios],
            "lentes_omitidas": self.lentes_omitidas,
            "cenarios_convergentes": [c.para_dict() for c in self.cenarios_convergentes],
            "convergencia": self.convergencia,
            "sintese_tecnica": self.sintese_tecnica,
            "sintese_cidada": self.sintese_cidada,
            "normas_rejeitadas_total": self.normas_rejeitadas_total,
            "ressalva": self.ressalva,
            "via_llm": self.via_llm,
            "perspetiva": self.perspetiva,
            "percurso": self.percurso,
        }


# ── Prompts ──────────────────────────────────────────────────────────────────

_SYSTEM_CENARIOS = """És um jurista português sénior num sistema institucional de informação jurídica.
Analisas o caso por TRÊS lentes interpretativas e devolves EXCLUSIVAMENTE JSON válido, sem markdown.

REGRAS INVIOLÁVEIS:
- Só marcas "viavel": true quando a lente produz uma solução juridicamente sustentável.
- Citas APENAS artigos que constem das normas fornecidas — nunca inventes citações.
- NUNCA afirmes qual é a "jurisprudência dominante", "maioritária" ou "constante",
  nem que "os tribunais tendem a decidir" num sentido, SALVO se te forem
  fornecidos acórdãos que o sustentem. Sem essa base, escreve que a questão é
  controvertida ou que a orientação dos tribunais não pôde ser verificada. Uma
  tendência jurisprudencial inventada é tão grave como uma norma inventada — e
  mais difícil de detectar, porque nenhum validador a apanha.
- NUNCA uses aspas duplas dentro dos valores do JSON. Para citar uma expressão
  do caso, usa aspas angulares «assim» — aspas duplas partem o JSON.
- As normas fornecidas são uma SELECÇÃO feita para este caso, não a totalidade da
  legislação disponível. Se precisares de uma norma que não te foi entregue, escreve
  "não consta das normas seleccionadas para esta análise" — NUNCA "não consta do
  corpus" nem "não existe", porque o corpus é muito mais vasto do que esta selecção
  e afirmá-lo seria falso.
- ANTES de declarares que algo não consta das normas seleccionadas, PERCORRE a lista
  fornecida e confirma. Declarar em falta uma norma que te foi entregue é um erro
  grave: baixa injustamente a solidez da tua leitura e faz o sistema parecer mais
  limitado do que é.
- USA todas as normas fornecidas que sejam pertinentes ao caso, não apenas as duas
  ou três mais evidentes. Se a lista contém a norma que fundamenta o efeito, o prazo
  ou a consequência de que estás a falar, cita-a.
- Atribui "solidez": elevada quando as normas fornecidas sustentam a conclusão sem
  lacunas; média quando falta efectivamente alguma norma para fechar o raciocínio;
  baixa quando a base é insuficiente. Não declares "média" por hábito: se a lista
  cobre o que precisas, a solidez é elevada.
- "solidez" é qualitativa: "elevada", "media" ou "baixa". Nunca uses percentagens.
- Linguagem informativa, nunca prescritiva: descreves o que "tipicamente sucede",
  nunca dizes o que a pessoa "deve fazer".
- "sentido" resume o desfecho: "procedente", "improcedente", "condenacao",
  "absolvicao", "misto" ou equivalente curto."""

_PROMPT_CENARIOS = """CASO:
{caso}

NORMAS SELECCIONADAS PARA ESTE CASO (cita apenas destas; são uma selecção da
legislação portuguesa, não a totalidade):
{normas}

JURISPRUDÊNCIA FORNECIDA PARA ESTE CASO: {jurisprudencia}

Analisa o caso pelas três lentes e devolve:
{{
  "cenarios": [
    {{
      "lente": "legalista|garantista|consequencialista",
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

    # 15 normas em vez de 8: medido em ferramentas/bancada.py, a cobertura de
    # normas de referência sobe de 50% para 77% sem alterar o motor de busca.
    def gerar(self, texto_caso: str, top_k_normas: int = 15,
              contraditorio: bool = False) -> ResultadoCenarios:
        """
        Gera os cenários de resolução para um caso (texto livre ou Ficha
        de Factos do Instrutor). Cada cenário sai validado e nos dois registos.
        """
        if contraditorio:
            texto_caso = (
                "[ANÁLISE DO CONTRADITÓRIO] Analisa este caso adotando a perspetiva "
                "da PARTE CONTRÁRIA à de quem relata: os argumentos, riscos e "
                "cenários devem ser os que serviriam quem se opõe ao relator.\n\n"
                + texto_caso
            )

        percurso: list[dict] = [{
            "etapa": 1, "nome": "entrada",
            "descricao": "Receção do caso (texto livre ou Ficha de Factos do Instrutor).",
            "dados": {"caracteres": len(texto_caso)},
        }]

        normas = self._rag.search(texto_caso, top_k=top_k_normas)
        # Texto das normas enviado ao modelo.
        #
        # Estava truncado aos 180 caracteres, o que cortava 89% dos artigos do
        # corpus — muitas vezes antes da alínea que resolvia o caso. No art.
        # 381.º CT, por exemplo, o modelo recebia a alínea a) (motivos
        # políticos) e nunca chegava à c) — «se não for precedido do
        # respectivo procedimento» —, que é a norma central de um despedimento
        # sem processo disciplinar. O modelo assinalava correctamente que não
        # podia citar a alínea exacta, e a solidez descia por uma limitação
        # que não era da lei nem dele.
        #
        # 2500 caracteres cobrem 96% do corpus por inteiro. O custo é de
        # cêntimos por análise e o ganho em fundamentação é grande.
        normas_txt = "\n".join(
            f"• Art. {c.artigo}.º {c.diploma} — "
            f"{(c.epigrase + ': ') if getattr(c, 'epigrase', '') else ''}"
            f"{c.texto[:_MAX_CARACTERES_NORMA]}"
            f"{' […]' if len(c.texto) > _MAX_CARACTERES_NORMA else ''}"
            for c in normas
        ) or "— sem normas recuperadas —"

        percurso.append({
            "etapa": 2, "nome": "recuperacao_de_normas",
            "descricao": f"Pesquisa BM25 no corpus legislativo ({self._rag.total_artigos} artigos); top-{top_k_normas} normas por relevância.",
            "dados": {"normas_recuperadas": [
                {"norma": f"{c.diploma}-{c.artigo}", "relevancia": round(float(getattr(c, 'score', 0.0)), 2)}
                for c in normas
            ]},
        })

        if self._llm is not None:
            try:
                cenarios, sintese_tec = self._gerar_llm(texto_caso, normas_txt)
                via_llm = True
            except Exception as exc:
                # Degradação graciosa: chave inválida/rede/saldo nunca nega a análise
                logger.warning("cenarios.llm_falhou_a_degradar_para_stub", erro=str(exc)[:200])
                cenarios, sintese_tec = self._gerar_stub(texto_caso, normas)
                via_llm = False
        else:
            cenarios, sintese_tec = self._gerar_stub(texto_caso, normas)
            via_llm = False

        percurso.append({
            "etapa": 3, "nome": "geracao_das_lentes",
            "descricao": "Análise do caso pelas três lentes interpretativas (garantista, legalista, consequencialista).",
            "dados": {"motor": "llm" if via_llm else "deterministico",
                       "lentes_produzidas": [c.lente.value for c in cenarios]},
        })

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

        percurso.append({
            "etapa": 4, "nome": "validacao_anti_alucinacao",
            "descricao": "Cada citação de cada cenário é verificada letra a letra contra o corpus; citações inexistentes são rejeitadas e assinaladas.",
            "dados": {
                "validadas_por_lente": {c.lente.value: c.fundamentacao_normas for c in cenarios},
                "rejeitadas_por_lente": {c.lente.value: c.normas_rejeitadas for c in cenarios if c.normas_rejeitadas},
            },
        })

        # 2) Regra da viabilidade: apenas cenários viáveis são apresentados
        viaveis = [c for c in cenarios if c.viavel]
        omitidas = [
            {
                "lente": c.lente.value,
                "motivo": (c.riscos or "").strip() or (
                    "Esta abordagem não sustenta uma solução juridicamente "
                    "defensável com as normas disponíveis para este caso."
                ),
            }
            for c in cenarios if not c.viavel
        ]
        if not viaveis:
            viaveis = cenarios[:1]  # nunca devolver vazio: mostra a leitura menos frágil
            if viaveis:
                viaveis[0].viavel = True
                viaveis[0].solidez = "baixa"

        secundarios: list[Cenario] = []

        # 3) Regra da convergência (§2): mesmas conclusões → uma só solução
        sentidos = {_sentido_normalizado(c.sentido) for c in viaveis}
        # A convergência exige direcção comum — nunca se declara quando as
        # lentes coincidem apenas em «incerto», que não é acordo sobre o
        # desfecho mas ausência dele.
        #
        # Uma lente que se diz «incerta» não contraria as restantes: abstém-se.
        # É frequente na consequencialista, cuja incerteza respeita ao tempo e
        # à cobrança efectiva, não ao mérito. Por isso conta-se a direcção das
        # lentes que se pronunciam, exigindo que sejam pelo menos duas e que
        # nenhuma aponte em sentido contrário.
        direccoes = {s for s in sentidos if s != "incerto"}
        pronunciadas = [c for c in viaveis
                        if _sentido_normalizado(c.sentido) != "incerto"]
        convergencia = len(direccoes) == 1 and len(pronunciadas) >= 2
        if convergencia:
            base = max(pronunciadas, key=lambda c: SOLIDEZ_VALORES.index(c.solidez) * -1)
            quantas = len(pronunciadas)
            base.titulo = (
                f"As {'três' if quantas >= 3 else 'duas'} abordagens convergem: "
                + base.titulo)
            base.solidez = "elevada"
            base.solucao_tecnica = (
                "CONVERGÊNCIA DAS LENTES no mesmo sentido — indicador de caso "
                "juridicamente claro. " + base.solucao_tecnica
            )
            # As restantes não são descartadas: passam a secundárias. A leitura
            # fundida fica em destaque, mas as outras continuam disponíveis —
            # sem elas, um documento de convergência mostra uma só lente e
            # perde-se a prova de que as três foram efectivamente percorridas.
            secundarios = [c for c in viaveis if c is not base]
            viaveis = [base]

        percurso.append({
            "etapa": 5, "nome": "regras_de_apresentacao",
            "descricao": "Regra da viabilidade (só cenários juridicamente sustentáveis) e regra da convergência (lentes coincidentes fundem-se numa só solução assinalada).",
            "dados": {"sentidos_das_lentes": sorted(sentidos),
                       "convergencia": convergencia,
                       "cenarios_apresentados": len(viaveis)},
        })

        # 4) Saída dupla: o registo cidadão deriva do técnico (§3)
        self._gerar_registo_cidadao(viaveis, sintese_tec)
        sintese_cid = viaveis[0].__dict__.get("_sintese_cidada_tmp", "")
        for c in viaveis:
            c.__dict__.pop("_sintese_cidada_tmp", None)

        percurso.append({
            "etapa": 6, "nome": "saida_dupla",
            "descricao": "O registo em linguagem clara é derivado do registo técnico (nunca gerado de forma independente), garantindo coerência de conteúdo entre os dois.",
            "dados": {"traducao": "llm" if via_llm else "glossario_deterministico"},
        })

        resultado = ResultadoCenarios(
            cenarios=viaveis,
            convergencia=convergencia,
            sintese_tecnica=sintese_tec,
            sintese_cidada=sintese_cid,
            normas_rejeitadas_total=sorted(set(rejeitadas_total)),
            lentes_omitidas=omitidas,
            cenarios_convergentes=secundarios,
            via_llm=via_llm,
            percurso=percurso,
            perspetiva="contraparte" if contraditorio else "propria",
        )
        logger.info(
            "cenarios.gerados",
            n=len(viaveis), convergencia=convergencia,
            rejeitadas=len(resultado.normas_rejeitadas_total), via_llm=via_llm,
        )
        return resultado

    # ── Geração LLM ─────────────────────────────────────────────────────

    def _gerar_llm(self, caso: str, normas_txt: str) -> tuple[list[Cenario], str]:
        # Identificadores pessoais nunca saem em claro para o serviço externo.
        from app.core.privacidade import pseudonimizar, repor, resumo
        caso_seguro, mapa = pseudonimizar(caso)
        if mapa:
            logger.info("privacidade.pseudonimizado", tipos=resumo(mapa))
        # Sem acórdãos, o modelo tem de saber que não pode falar de tendências.
        prompt = _PROMPT_CENARIOS.format(
            caso=caso_seguro, normas=normas_txt,
            jurisprudencia=(
                "NENHUMA. Não afirmes qual é a orientação dos tribunais; quando "
                "a questão o exigir, escreve que é controvertida ou que não foi "
                "possível verificar a orientação jurisprudencial."
            ),
        )
        raw = repor(self._chamar_llm_completo(_SYSTEM_CENARIOS, prompt), mapa)
        try:
            dados = self._extrair_json(raw)
        except ValueError:
            # Segunda tentativa com instrução reforçada. Em casos muito longos
            # — uma peça processual completa, por exemplo — o modelo tende a
            # responder com análise corrida em vez do formato pedido. Perder
            # a análise inteira por causa do formato seria desperdiçar
            # trabalho já feito e já pago.
            logger.warning("cenarios.json.segunda_tentativa")
            reforco = (
                "\n\nATENÇÃO: a resposta anterior não estava em JSON válido. "
                "Responde ÚNICA E EXCLUSIVAMENTE com o objecto JSON pedido, "
                "começando por { e terminando por }. Sem preâmbulo, sem texto "
                "antes ou depois, sem cercas de código. Se o caso for extenso, "
                "sê mais conciso em cada campo, mas mantém o formato."
            )
            raw = repor(
                self._chamar_llm_completo(_SYSTEM_CENARIOS + reforco, prompt), mapa)
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
        unicos.sort(key=lambda c: ORDEM_LENTES.index(c.lente)
                    if c.lente in ORDEM_LENTES else 99)
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
            from app.core.llm import obter_modelo
            msg = self._llm.messages.create(
                model=obter_modelo(self.MODELO), max_tokens=self.MAX_TOKENS,
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
        from app.core.json_llm import ler_json
        return ler_json(raw, "cenarios")


# Instância partilhada — usa LLM se ANTHROPIC_API_KEY estiver configurada
from app.core.llm import criar_llm as _criar_llm
motor_cenarios = MotorCenarios(llm_client=_criar_llm("cenarios"))
