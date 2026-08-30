"""
Reescrita da pergunta em linguagem jurídica, antes da recuperação.

O problema que resolve: o cidadão escreve "o meu chefe disse-me que estou
despedida e eu estou grávida"; a lei diz "cessação do contrato de trabalho",
"ilicitude do despedimento", "protecção da parentalidade". Nem o BM25 nem
os embeddings pequenos atravessam bem esta distância de vocabulário.

A solução não é um dicionário de sinónimos (não escala: há tantas maneiras
de contar um caso quantas as pessoas). É pedir ao modelo de linguagem, que
o sistema já usa, que traduza o relato para os termos técnicos que a lei
emprega — e procurar com esses termos, além do texto original.

Princípios:
- Nunca inventa factos: apenas nomeia institutos jurídicos convocados.
- Nunca cita artigos: a escolha das normas continua a ser do RAG, e a
  validação continua a ser feita contra o corpus (anti-alucinação).
- Degradação graciosa: sem LLM, devolve o texto original inalterado.
- Cache por conteúdo: o mesmo caso não paga duas vezes.
"""
from __future__ import annotations

import hashlib
import re

import structlog

logger = structlog.get_logger(__name__)

_SYSTEM = (
    "És um jurista português. Recebes o relato de um caso em linguagem comum "
    "e devolves APENAS os termos técnicos do direito português que servem "
    "para pesquisar a legislação aplicável.\n"
    "Regras estritas:\n"
    "- Devolve entre 10 e 20 termos ou expressões curtas, separados por ponto e vírgula.\n"
    "- Escreve em minúsculas, sem numeração e sem marcadores.\n"
    "- Inclui sempre o nome do regime ou área em causa (ex.: 'direitos do consumidor', 'protecção da parentalidade'), além dos conceitos técnicos.\n"
    "- Usa a terminologia dos códigos portugueses (ex.: 'cessação do contrato de "
    "trabalho', 'ilicitude do despedimento', 'protecção da parentalidade').\n"
    "- Inclui os institutos processuais relevantes (ex.: 'pedido de indemnização "
    "civil em processo penal').\n"
    "- NÃO inventes factos. NÃO expliques nada. NÃO analises o caso.\n"
    "- Responde só com as listas pedidas, sem preâmbulo.\n"
    "\n"
    "Depois da lista de termos, numa segunda linha iniciada por 'NORMAS:', indica "
    "até 8 artigos da legislação portuguesa que um jurista esperaria consultar "
    "neste caso, no formato 'artigo N.º SIGLA' (ex.: artigo 483.º CC; artigo 71.º CPP).\n"
    "Estas indicações servem apenas para orientar a pesquisa: são verificadas "
    "contra o corpus e descartadas se não existirem. Na dúvida, indica na mesma."
)

_MAX_CACHE = 256
_cache: dict[str, str] = {}


def _chave(texto: str) -> str:
    return hashlib.sha256(texto.strip().lower().encode("utf-8", "ignore")).hexdigest()


def _limpar(bruto: str) -> str:
    """Aceita apenas uma lista de termos; descarta divagações do modelo."""
    texto = bruto.strip()
    texto = re.sub(r"^(termos|resposta|pesquisa)\s*:\s*", "", texto, flags=re.I)
    brutos = [p.strip(" .;\n\t-–—") for p in re.split(r"[;\n]", texto)]
    partes: list[str] = []
    for b in brutos:
        if len(b) <= 90:
            partes.append(b)
        else:
            # Antes descartava-se a linha inteira, perdendo todos os termos
            # quando o modelo devolvia tudo seguido. Agora divide-se.
            partes.extend(x.strip() for x in b.split(","))
    partes = [p for p in partes if 2 < len(p) <= 90]
    return "; ".join(partes[:28])


def reescrever(texto: str, llm=None) -> str:
    """
    Devolve o texto original enriquecido com termos jurídicos.
    Se não houver LLM disponível, devolve o texto tal como veio.
    """
    if not texto or not texto.strip():
        return texto

    chave = _chave(texto)
    if chave in _cache:
        return f"{texto}\n{_cache[chave]}"

    if llm is None:
        try:
            from app.core.llm import criar_llm
            llm = criar_llm("reescrita")
        except Exception:
            llm = None
    if llm is None:
        return texto

    try:
        from app.core.llm import obter_modelo
        from app.core.privacidade import pseudonimizar
        texto_seguro, _ = pseudonimizar(texto[:6000])
        msg = llm.messages.create(
            model=obter_modelo(),
            max_tokens=400,
            # Temperatura 0: a reescrita é uma tradução técnica, não um
            # exercício criativo. Sem isto, o mesmo caso produzia termos
            # diferentes a cada execução e a qualidade da pesquisa oscilava —
            # observou-se um caso de direito do consumo a variar entre 4/5 e
            # 0/5 só por causa da variação dos termos gerados.
            temperature=0,
            system=_SYSTEM,
            messages=[{"role": "user", "content": texto_seguro}],
        )
        bruto = "".join(b.text for b in msg.content if getattr(b, "text", None))
        termos = _limpar(bruto)
        if not termos:
            return texto
        if len(_cache) >= _MAX_CACHE:
            _cache.clear()
        _cache[chave] = termos
        logger.info("rag.reescrita.ok", termos=termos[:160])
        return f"{texto}\n{termos}"
    except Exception as exc:
        logger.warning("rag.reescrita.falhou", erro=str(exc)[:160])
        return texto
