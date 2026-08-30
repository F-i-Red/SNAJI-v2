"""
Motor RAG jurídico real.
BM25 sobre o corpus integral de legislação portuguesa (12 diplomas).
Corpus construído a partir de fontes oficiais (parlamento.pt, pgdlisboa.pt, eur-lex.europa.eu).
"""
import json
import os
import re
import unicodedata
from pathlib import Path
from dataclasses import dataclass
from rank_bm25 import BM25Okapi


@dataclass
class Chunk:
    diploma: str
    artigo: str
    epigrase: str
    texto: str
    fonte: str
    score: float = 0.0


def _carregar_corpus() -> list[dict]:
    caminho = Path(__file__).parent / "corpus" / "corpus.json"
    if not caminho.exists():
        raise FileNotFoundError(
            f"Corpus não encontrado em {caminho}.\n"
            "Corre: python app/rag/corpus/processador.py"
        )
    return json.loads(caminho.read_text(encoding="utf-8"))


def _stem(tok: str) -> str:
    """
    Radical aproximado (stemmer leve para português).

    Sem isto, a linguagem do cidadão nunca encontra a linguagem da lei:
    'despedida' não casa com 'despedimento', 'grávida' não casa com
    'gravidez'. As regras removem sufixos flexionais e derivacionais
    frequentes, preservando um radical mínimo de 4 caracteres.
    """
    if len(tok) <= 4:
        return tok
    for suf in (
        "mentos", "mento", "coes", "cao", "idades", "idade", "izacao",
        "amentos", "amento", "adores", "ador", "antes", "ante",
        "aveis", "avel", "veis", "eis", "oes", "aes",
        "issimo", "issima", "ismos", "ismo",
        "adas", "ada", "idas", "ida", "ados", "ado", "idos", "ido",
        "ares", "ar", "eres", "er", "ires", "ir",
        "amos", "emos", "imos", "aram", "eram", "iram",
        "ando", "endo", "indo", "ez", "es", "as", "os", "a", "o", "e",
    ):
        if tok.endswith(suf) and len(tok) - len(suf) >= 4:
            return tok[: -len(suf)]
    return tok


# Palavras vazias — em narrativas longas do cidadão, dominam a contagem
# e afogam os termos que realmente discriminam o caso.
_STOPWORDS = {
    "a", "ao", "aos", "as", "com", "como", "da", "das", "de", "do", "dos",
    "e", "em", "entre", "essa", "esse", "esta", "este", "eu", "foi", "ha",
    "isso", "isto", "ja", "la", "lhe", "lhes", "mas", "me", "meu", "minha",
    "muito", "na", "nao", "nas", "no", "nos", "num", "numa", "o", "os",
    "ou", "para", "pela", "pelo", "por", "que", "quando", "se", "sem",
    "ser", "seu", "sua", "tem", "ter", "um", "uma", "vou", "ainda", "ate",
    "depois", "disse", "estou", "fui", "onde", "porque", "qual", "quer",
    "sobre", "so", "tudo", "ver", "vez", "mim", "nem", "mesmo", "outro",
}

# Linguagem comum → linguagem legal. Expande a pergunta (nunca o corpus),
# para que a forma como as pessoas falam encontre a forma como a lei escreve.
_EXPANSOES = {
    "despedida": "despedimento cessacao contrato",
    "despedido": "despedimento cessacao contrato",
    "despediram": "despedimento cessacao",
    "despedir": "despedimento",
    "gravida": "gravidez parentalidade maternidade",
    "gravidez": "parentalidade maternidade",
    "patrao": "empregador entidade empregadora",
    "chefe": "empregador superior hierarquico",
    "senhorio": "locador arrendamento",
    "inquilino": "arrendatario locatario",
    "renda": "arrendamento locacao actualizacao",
    "casa": "habitacao locado imovel",
    "despejo": "resolucao desocupacao arrendamento",
    "salario": "retribuicao",
    "ordenado": "retribuicao",
    "empurrou": "ofensa integridade fisica agressao",
    "bateu": "ofensa integridade fisica agressao",
    "agrediu": "ofensa integridade fisica",
    "roubou": "furto roubo subtracao",
    "queixa": "denuncia participacao procedimento criminal",
    "indemnizacao": "responsabilidade civil danos reparacao",
    "filhos": "menores responsabilidades parentais",
    "divida": "obrigacao cumprimento credito",
}


def _normalizar(texto: str, expandir: bool = False) -> list[str]:
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("ascii").lower()
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    brutos = texto.split()

    if expandir:  # só do lado da pergunta
        extra: list[str] = []
        for t in brutos:
            termos = _EXPANSOES.get(t)
            if termos:
                extra.extend(termos.split())
        brutos = brutos + extra

    tokens: list[str] = []
    for t in brutos:
        if t in _STOPWORDS or len(t) < 2:
            continue
        tokens.append(t)
        radical = _stem(t)
        if radical != t:
            tokens.append(radical)  # indexa termo e radical
    return tokens


# Mapeamento de aliases para o código do diploma
ALIAS_DIPLOMA = {
    "crp": "CRP", "constituição": "CRP", "constituicao": "CRP",
    "ct": "CT", "código do trabalho": "CT", "codigo do trabalho": "CT",
    "cc": "CC", "código civil": "CC", "codigo civil": "CC",
    "rgpd": "RGPD", "protecção de dados": "RGPD", "proteção de dados": "RGPD",
    "cp": "CP", "código penal": "CP", "codigo penal": "CP",
    "cpc": "CPC", "código de processo civil": "CPC",
    "cpp": "CPP", "código de processo penal": "CPP",
    "csc": "CSC", "código das sociedades comerciais": "CSC",
    "cire": "CIRE", "código da insolvência": "CIRE",
    "cpa": "CPA", "código do procedimento administrativo": "CPA",
    "ljp": "LJP", "lei dos julgados de paz": "LJP",
    "ldc": "LDC", "lei de defesa do consumidor": "LDC",
}

# Normas válidas para anti-alucinação (preenchido dinamicamente)
NORMAS_VALIDAS: dict[str, set[str]] = {}

# Peso do BM25 na fusão híbrida (o restante vai para os embeddings).
# 0.6 = 60% posição no BM25, 40% posição no semântico. O BM25 é, para já,
# o sinal mais fiável na maioria dos casos; medir com
# ferramentas/afinar_recuperacao.py antes de alterar.
try:
    _PESO_BM25 = float(os.getenv("SNAJI_PESO_BM25", "0.6"))
except ValueError:
    _PESO_BM25 = 0.6

# Reescrita da pergunta em linguagem jurídica pela LLM antes da pesquisa.
# Custa uma chamada curta por análise; desactivável com SNAJI_REESCRITA=0.
# Máximo de artigos que entram por citação directa, para não ocuparem todos
# os lugares disponíveis à custa dos que a pesquisa encontrou.
try:
    _MAX_CITADOS = int(os.getenv("SNAJI_MAX_CITADOS", "8"))
except ValueError:
    _MAX_CITADOS = 8

_REESCRITA_ACTIVA = os.getenv("SNAJI_REESCRITA", "1").strip().lower() not in (
    "0", "false", "nao", "não",
)


class RAGJuridico:
    """BM25 sobre corpus jurídico real. Sem dados hardcoded."""

    def __init__(self):
        self._chunks = _carregar_corpus()
        # Preenche normas válidas para o validador
        for c in self._chunks:
            NORMAS_VALIDAS.setdefault(c["diploma"], set()).add(c["artigo"])
        # Indexa: texto + epígrafe + diploma para melhor recall.
        # A epígrafe entra com peso 3: é o resumo temático do artigo
        # ('Protecção em caso de despedimento') e por isso o sinal mais
        # fiável do assunto, ao contrário do texto longo, que dilui.
        textos = [
            _normalizar(
                f"{c['epigrase']} {c['epigrase']} {c['epigrase']} "
                f"{c['texto']} {c['diploma']}"
            )
            for c in self._chunks
        ]
        self._bm25 = BM25Okapi(textos)

        # Índice semântico (opcional): calcula-se uma vez e fica em cache.
        # Se não estiver disponível, a pesquisa continua só com BM25.
        try:
            from app.rag.semantico import indice_semantico, texto_para_vector
            indice_semantico.preparar([
                texto_para_vector(c.get("epigrase", ""), c.get("texto", ""))
                for c in self._chunks
            ])
        except Exception:
            pass

    def search_bm25(self, query: str, top_k: int = 6) -> list[Chunk]:
        """
        Pesquisa apenas por palavras (BM25). Usada em diagnóstico.
        Aplica a mesma reescrita jurídica que a pesquisa normal, para que a
        comparação entre motores isole o método de correspondência e não a
        preparação da pergunta.
        """
        if _REESCRITA_ACTIVA:
            try:
                from app.rag.reescrita import reescrever
                query = reescrever(query)
            except Exception:
                pass
        tokens = _normalizar(query, expandir=True)
        scores = self._bm25.get_scores(tokens)
        ordem = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [self._como_chunk(i, float(scores[i])) for i in ordem[:top_k]]

    def search_semantico(self, query: str, top_k: int = 6) -> list[Chunk] | None:
        """
        Pesquisa apenas por significado (embeddings). None se indisponível.
        Também aplica a reescrita, pela mesma razão de comparabilidade.
        """
        if _REESCRITA_ACTIVA:
            try:
                from app.rag.reescrita import reescrever
                query = reescrever(query)
            except Exception:
                pass
        try:
            from app.rag.semantico import indice_semantico
            sims = indice_semantico.similaridades(query)
        except Exception:
            return None
        if sims is None:
            return None
        ordem = sorted(range(len(sims)), key=lambda i: sims[i], reverse=True)
        return [self._como_chunk(i, float(sims[i])) for i in ordem[:top_k]]

    def _como_chunk(self, i: int, score: float) -> Chunk:
        c = self._chunks[i]
        return Chunk(
            diploma=c["diploma"], artigo=c["artigo"],
            epigrase=c.get("epigrase", ""), texto=c["texto"],
            fonte=c.get("fonte", ""), score=round(score, 4),
        )

    def _citados_explicitamente(self, query: str) -> list[int]:
        """
        Artigos que o utilizador nomeou na pergunta.

        Quando alguém escreve "o artigo 1077.º do Código Civil", esse artigo
        tem de aparecer — não pode depender de o BM25 o classificar bem. São
        colocados à cabeça dos resultados.
        """
        validas, _ = ValidadorCitacoes().extrair_e_validar(query)
        indices: list[int] = []
        for v in validas:
            for i, c in enumerate(self._chunks):
                if c["diploma"] == v["diploma"] and c["artigo"] == v["artigo"]:
                    if i not in indices:
                        indices.append(i)
                    break
        return indices

    def search(self, query: str, top_k: int = 6, diploma: str | None = None) -> list[Chunk]:
        # Reescrita da pergunta em linguagem jurídica (se houver LLM).
        # É aqui que se atravessa a distância entre 'estou despedida' e
        # 'cessação do contrato de trabalho'. Sem LLM, segue o texto original.
        if _REESCRITA_ACTIVA:
            try:
                from app.rag.reescrita import reescrever
                query = reescrever(query)
            except Exception:
                pass

        tokens = _normalizar(query, expandir=True)
        scores = self._bm25.get_scores(tokens)

        # Recuperação híbrida por fusão de posições (Reciprocal Rank Fusion).
        #
        # Não se somam pontuações: as do BM25 espalham-se por uma escala
        # ampla, enquanto as semelhanças de embeddings se concentram numa
        # faixa estreita. Somá-las faz o sinal semântico comportar-se como
        # uma constante e a ordenação fica igual à do BM25 sozinho.
        # A RRF combina apenas as *posições* em cada lista, sendo por isso
        # imune às diferenças de escala.
        try:
            from app.rag.semantico import indice_semantico
            semelhancas = indice_semantico.similaridades(query)
        except Exception:  # nunca comprometer a pesquisa
            semelhancas = None

        if semelhancas is not None and len(semelhancas) == len(scores):
            import numpy as _np
            K_RRF = 60.0  # amortece o peso das primeiras posições
            pos_bm25 = _np.empty(len(scores), dtype=_np.int32)
            pos_bm25[_np.argsort(-scores, kind="stable")] = _np.arange(len(scores))
            pos_sem = _np.empty(len(semelhancas), dtype=_np.int32)
            pos_sem[_np.argsort(-semelhancas, kind="stable")] = _np.arange(len(semelhancas))
            scores = (
                _PESO_BM25 / (K_RRF + pos_bm25 + 1)
                + (1.0 - _PESO_BM25) / (K_RRF + pos_sem + 1)
            )

        indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

        # Artigos nomeados na pergunta — pelo utilizador ou sugeridos pela
        # reescrita — entram à frente, sem depender da pontuação do BM25.
        #
        # Segurança: só entram artigos que EXISTEM no corpus. Uma sugestão
        # inventada não encontra correspondência e é simplesmente ignorada,
        # sem qualquer efeito na resposta. O limite evita que uma lista longa
        # de sugestões ocupe todos os lugares e afaste o que a pesquisa
        # encontrou por mérito próprio.
        citados = self._citados_explicitamente(query)[:_MAX_CITADOS]
        if citados:
            indices = citados + [i for i in indices if i not in citados]

        resultados = []
        for i in indices:
            if len(resultados) >= top_k:
                break
            c = self._chunks[i]
            if diploma and c["diploma"] != diploma.upper():
                continue
            if scores[i] <= 0.0:
                continue
            resultados.append(Chunk(
                diploma=c["diploma"],
                artigo=c["artigo"],
                epigrase=c.get("epigrase", ""),
                texto=c["texto"],
                fonte=c.get("fonte", ""),
                score=round(float(scores[i]), 4),
            ))
        return resultados

    def get_artigo(self, diploma: str, artigo: str) -> Chunk | None:
        """Recupera um artigo específico pelo diploma e número."""
        for c in self._chunks:
            if c["diploma"] == diploma.upper() and c["artigo"] == artigo:
                return Chunk(**{k: c.get(k, "") for k in
                               ["diploma","artigo","epigrase","texto","fonte"]})
        return None

    @property
    def total_artigos(self) -> int:
        return len(self._chunks)

    @property
    def artigos(self) -> list[dict]:
        """Acesso público (só leitura) aos artigos do corpus."""
        return self._chunks


class ValidadorCitacoes:
    """Anti-alucinação determinístico baseado no corpus real."""

    PADRAO = re.compile(
        r"[Aa]rt(?:igo)?\.?\s*(\d+[A-Z]?)\.?[°º]?\s*"
        r"(?:do|da|n\.?[°º]?)?\s*"
        r"(Constituição da República Portuguesa|Constituição|"
        r"Código de Processo Civil|Código de Processo Penal|"
        r"Código das Sociedades Comerciais|"
        r"Código da Insolvência e da Recuperação de Empresas|"
        r"Código do Procedimento Administrativo|"
        r"Código do Trabalho|Código Civil|Código Penal|"
        r"Regulamento Geral sobre a Prote[cç]?ção de Dados|"
        r"Lei dos Julgados de Paz|Lei de Defesa do Consumidor|"
        r"CIRE|RGPD|CPP|CPC|CPA|CSC|CRP|LJP|LDC|CC|CP|CT)\b",
        re.IGNORECASE | re.UNICODE,
    )
    MAPA = {
        "crp": "CRP", "constituição": "CRP",
        "constituição da república portuguesa": "CRP",
        "código do trabalho": "CT", "ct": "CT",
        "código civil": "CC", "cc": "CC",
        "rgpd": "RGPD",
        "regulamento geral sobre a proteção de dados": "RGPD",
        "regulamento geral sobre a protecção de dados": "RGPD",
        "código penal": "CP", "cp": "CP",
        "código de processo civil": "CPC", "cpc": "CPC",
        "código de processo penal": "CPP", "cpp": "CPP",
        "código das sociedades comerciais": "CSC", "csc": "CSC",
        "código da insolvência e da recuperação de empresas": "CIRE",
        "cire": "CIRE",
        "código do procedimento administrativo": "CPA", "cpa": "CPA",
        "lei dos julgados de paz": "LJP", "ljp": "LJP",
        "lei de defesa do consumidor": "LDC", "ldc": "LDC",
    }

    def validar(self, diploma: str, artigo: str) -> bool:
        normas = NORMAS_VALIDAS.get(diploma.upper(), set())
        return artigo in normas

    def extrair_e_validar(self, texto: str) -> tuple[list[dict], list[dict]]:
        validas, suspeitas, vistos = [], [], set()
        for m in self.PADRAO.finditer(texto):
            artigo = m.group(1)
            raw = m.group(2).strip().lower()
            diploma = self.MAPA.get(raw, raw.upper())
            chave = f"{diploma}-{artigo}"
            if chave in vistos:
                continue
            vistos.add(chave)
            entrada = {"diploma": diploma, "artigo": artigo}
            (validas if self.validar(diploma, artigo) else suspeitas).append(entrada)
        return validas, suspeitas
