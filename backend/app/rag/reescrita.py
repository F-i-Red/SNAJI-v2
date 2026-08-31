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
import json
import re
from pathlib import Path

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

# A cache é persistida em disco. O modelo não aceita temperatura zero, pelo
# que a mesma pergunta produz termos diferentes a cada execução e a qualidade
# da pesquisa oscila. Guardando a primeira reescrita de cada caso, o sistema
# passa a ser reprodutível: o mesmo caso dá sempre o mesmo resultado — o que
# num sistema de justiça importa tanto para a qualidade como para a auditoria.
_FICHEIRO_CACHE = Path(__file__).parent / "corpus" / "reescritas.json"


def _carregar_cache() -> None:
    if _cache or not _FICHEIRO_CACHE.is_file():
        return
    try:
        _cache.update(json.loads(_FICHEIRO_CACHE.read_text(encoding="utf-8")))
        logger.info("rag.reescrita.cache_carregada", entradas=len(_cache))
    except Exception as exc:
        logger.warning("rag.reescrita.cache_ilegivel", erro=str(exc)[:120])


def _gravar_cache() -> None:
    try:
        _FICHEIRO_CACHE.parent.mkdir(parents=True, exist_ok=True)
        _FICHEIRO_CACHE.write_text(
            json.dumps(_cache, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as exc:  # a cache é uma optimização, nunca um bloqueio
        logger.warning("rag.reescrita.cache_nao_gravada", erro=str(exc)[:120])


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


# Alguns modelos aceitam o parâmetro de temperatura e outros já o recusam
# ("temperature is deprecated for this model"). Detecta-se uma vez, na
# primeira chamada, e memoriza-se — evita repetir um pedido inválido a cada
# análise e mantém o determinismo onde ele é possível.
_TEMPERATURA_SUPORTADA: bool | None = None


def _criar_mensagem(llm, conteudo: str):
    """
    Chama o modelo pedindo determinismo quando o modelo o permitir.

    A reescrita é uma tradução técnica, não um exercício criativo: convém que
    o mesmo caso produza sempre os mesmos termos de pesquisa. Num sistema de
    justiça isso não é só qualidade — é auditabilidade.
    """
    global _TEMPERATURA_SUPORTADA
    from app.core.llm import obter_modelo

    base = dict(
        model=obter_modelo(),
        max_tokens=400,
        system=_SYSTEM,
        messages=[{"role": "user", "content": conteudo}],
    )

    if _TEMPERATURA_SUPORTADA is not False:
        try:
            msg = llm.messages.create(temperature=0, **base)
            _TEMPERATURA_SUPORTADA = True
            return msg
        except Exception as exc:
            if "temperature" not in str(exc).lower():
                raise
            _TEMPERATURA_SUPORTADA = False
            logger.info("rag.reescrita.sem_temperatura",
                        motivo="modelo não aceita o parâmetro; segue sem ele")

    return llm.messages.create(**base)


# Ângulos pedidos a cada reescrita. A variação natural entre gerações produz
# termos demasiado parecidos — e o consenso entre listas parecidas não
# acrescenta nada. Pedindo ângulos distintos, cada reescrita procura numa
# direcção diferente e a fusão cobre o caso por inteiro.
_ANGULOS = [
    "Foca-te nos DIREITOS E OBRIGAÇÕES substantivos das partes e nos vícios ou "
    "defeitos da relação (o que cada parte devia ter feito e não fez).",
    "Foca-te no INCUMPRIMENTO, nas suas consequências e nos remédios: mora, "
    "resolução, indemnização, restituição, prazos.",
    "Foca-te nos MEIOS DE TUTELA e no processo: que providências existem, que "
    "condutas são proibidas às partes, que via judicial se aplica.",
    "Foca-te nas GARANTIAS E PROTECÇÕES especiais aplicáveis (pessoas "
    "vulneráveis, habitação, saúde, trabalho, consumo) e nos princípios "
    "constitucionais convocados.",
]


def reescrever_varias(texto: str, quantas: int = 3, llm=None) -> list[str]:
    """
    Produz várias reescritas independentes do mesmo caso.

    O modelo não aceita temperatura zero, pelo que cada reescrita sai
    diferente — umas melhores, outras piores. Em vez de aceitar a sorte da
    primeira, ou de exigir que alguém escolha a melhor à mão, geram-se
    várias e o motor de pesquisa combina-as: um artigo encontrado por várias
    reescritas independentes é mais provavelmente relevante do que um que só
    aparece numa. É o sistema a escolher, por consenso, sem intervenção
    humana e sem conhecer a resposta certa.

    Devolve a lista de conjuntos de termos (sem o texto original).
    """
    _carregar_cache()
    chave = _chave(texto) + f"|x{quantas}"
    if chave in _cache:
        guardado = _cache[chave]
        return [v for v in guardado.split("\n@@\n") if v.strip()]

    variantes: list[str] = []
    vistos: set[str] = set()
    for i in range(max(1, quantas)):
        angulo = _ANGULOS[i % len(_ANGULOS)] if quantas > 1 else None
        resultado = reescrever(texto, llm=llm, _sem_cache=True, _angulo=angulo)
        termos = resultado[len(texto):].strip()
        if termos and termos not in vistos:
            vistos.add(termos)
            variantes.append(termos)

    if variantes:
        if len(_cache) >= _MAX_CACHE:
            _cache.clear()
        _cache[chave] = "\n@@\n".join(variantes)
        _gravar_cache()
        logger.info("rag.reescrita.variantes", n=len(variantes))
    return variantes


def reescrever(texto: str, llm=None, _sem_cache: bool = False,
               _angulo: str | None = None) -> str:
    """
    Devolve o texto original enriquecido com termos jurídicos.
    Se não houver LLM disponível, devolve o texto tal como veio.
    """
    if not texto or not texto.strip():
        return texto

    _carregar_cache()
    chave = _chave(texto + (_angulo or ''))
    if not _sem_cache and chave in _cache:
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
        conteudo = texto_seguro
        if _angulo:
            conteudo = f"{texto_seguro}\n\n[ÂNGULO DESTA PESQUISA] {_angulo}"
        msg = _criar_mensagem(llm, conteudo)
        bruto = "".join(b.text for b in msg.content if getattr(b, "text", None))
        termos = _limpar(bruto)
        if not termos:
            return texto
        if not _sem_cache:
            if len(_cache) >= _MAX_CACHE:
                _cache.clear()
            _cache[chave] = termos
            _gravar_cache()
        logger.info("rag.reescrita.ok", termos=termos[:160])
        return f"{texto}\n{termos}"
    except Exception as exc:
        logger.warning("rag.reescrita.falhou", erro=str(exc)[:160])
        return texto
