"""
Recuperação semântica (embeddings) sobre o corpus jurídico.

Porquê: o BM25 casa palavras. O cidadão escreve "estou despedida"; a lei diz
"cessação do contrato de trabalho". Zero palavras em comum, zero resultados
certos. Manter um dicionário de sinónimos não escala — há tantas maneiras de
descrever um caso quantas as pessoas que o descrevem.

Os embeddings resolvem isto pela raiz: cada artigo e cada pergunta são
convertidos num vector que representa o *significado*. Textos com sentido
próximo ficam próximos no espaço vectorial, mesmo sem partilhar vocabulário.
Não há dicionário para manter.

Desenho:
- Carregamento preguiçoso — o modelo só é carregado quando é preciso.
- Cache em disco — os vectores do corpus são calculados uma vez e guardados,
  validados por impressão digital do corpus (muda o corpus, recalcula).
- Degradação graciosa — sem o pacote ou sem o modelo, devolve None e o
  sistema continua a funcionar apenas com BM25. Nunca falha o arranque.

Configuração (.env):
  SNAJI_EMBEDDINGS=1                          activar (0 desactiva)
  SNAJI_MODELO_EMBEDDING=intfloat/multilingual-e5-small
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

_DIR_CACHE = Path(__file__).parent / "corpus"
_FICH_VECTORES = _DIR_CACHE / "embeddings.npy"
_FICH_IMPRESSAO = _DIR_CACHE / "embeddings.sha256"

# Modelo por omissão: multilingue, treinado para recuperação, leve o
# suficiente para correr em CPU num portátil comum (~470 MB).
_MODELO_OMISSAO = "intfloat/multilingual-e5-small"


def _activo() -> bool:
    return os.getenv("SNAJI_EMBEDDINGS", "1").strip().lower() not in ("0", "false", "nao", "não")


def _nome_modelo() -> str:
    return os.getenv("SNAJI_MODELO_EMBEDDING", "").strip() or _MODELO_OMISSAO


def _impressao(textos: list[str], modelo: str) -> str:
    """Identifica corpus + modelo, para invalidar a cache quando mudam."""
    h = hashlib.sha256()
    h.update(modelo.encode("utf-8"))
    h.update(str(len(textos)).encode("utf-8"))
    for t in textos[::37]:  # amostragem: suficiente para detectar alterações
        h.update(t[:200].encode("utf-8", "ignore"))
    return h.hexdigest()


class IndiceSemantico:
    """Índice de vectores do corpus. Silencioso e opcional."""

    def __init__(self) -> None:
        self._modelo = None
        self._vectores: np.ndarray | None = None
        self._preparado = False
        self._indisponivel = False

    # ── Interface pública ────────────────────────────────────────────────

    @property
    def disponivel(self) -> bool:
        return self._vectores is not None

    def preparar(self, textos: list[str]) -> None:
        """
        Garante que existem vectores para o corpus. Na primeira execução
        calcula-os (demorado: minutos em CPU) e guarda em disco; depois
        carrega da cache em segundos.
        """
        if self._preparado or self._indisponivel or not _activo():
            return
        self._preparado = True

        modelo_nome = _nome_modelo()
        impressao = _impressao(textos, modelo_nome)

        # 1. Tentar cache
        try:
            if _FICH_VECTORES.exists() and _FICH_IMPRESSAO.exists():
                if _FICH_IMPRESSAO.read_text().strip() == impressao:
                    vec = np.load(_FICH_VECTORES)
                    if vec.shape[0] == len(textos):
                        self._vectores = vec
                        logger.info("rag.semantico.cache", vectores=vec.shape[0])
                        return
        except Exception as exc:
            logger.warning("rag.semantico.cache_invalida", erro=str(exc)[:120])

        # 2. Calcular
        modelo = self._carregar_modelo()
        if modelo is None:
            return
        try:
            logger.info("rag.semantico.a_calcular", total=len(textos),
                        nota="primeira execução — pode demorar alguns minutos")
            vec = modelo.encode(
                [self._prefixo_passagem(t) for t in textos],
                batch_size=32,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            ).astype(np.float32)
            self._vectores = vec
            try:
                _FICH_VECTORES.parent.mkdir(parents=True, exist_ok=True)
                np.save(_FICH_VECTORES, vec)
                _FICH_IMPRESSAO.write_text(impressao)
                logger.info("rag.semantico.cache_gravada", ficheiro=str(_FICH_VECTORES))
            except Exception as exc:  # cache é opcional
                logger.warning("rag.semantico.cache_nao_gravada", erro=str(exc)[:120])
        except Exception as exc:
            logger.warning("rag.semantico.falhou", erro=str(exc)[:200])
            self._indisponivel = True

    def similaridades(self, pergunta: str) -> np.ndarray | None:
        """
        Semelhança de significado entre a pergunta e cada artigo, em [0, 1].
        Devolve None se a recuperação semântica não estiver disponível.
        """
        if self._vectores is None:
            return None
        modelo = self._carregar_modelo()
        if modelo is None:
            return None
        try:
            v = modelo.encode(
                [self._prefixo_pergunta(pergunta)],
                convert_to_numpy=True,
                normalize_embeddings=True,
            ).astype(np.float32)[0]
            sims = self._vectores @ v          # vectores normalizados → cosseno
            return np.clip((sims + 1.0) / 2.0, 0.0, 1.0)
        except Exception as exc:
            logger.warning("rag.semantico.pergunta_falhou", erro=str(exc)[:160])
            return None

    # ── Interno ──────────────────────────────────────────────────────────

    def _carregar_modelo(self):
        if self._modelo is not None:
            return self._modelo
        if self._indisponivel or not _activo():
            return None
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as exc:
            logger.info("rag.semantico.indisponivel",
                        motivo="sentence-transformers não instalado", erro=str(exc)[:120])
            self._indisponivel = True
            return None
        try:
            nome = _nome_modelo()
            logger.info("rag.semantico.a_carregar_modelo", modelo=nome)
            self._modelo = SentenceTransformer(nome)
            return self._modelo
        except Exception as exc:
            # Sem rede na primeira execução, disco cheio, etc.
            logger.warning("rag.semantico.modelo_indisponivel", erro=str(exc)[:200])
            self._indisponivel = True
            return None

    @staticmethod
    def _e5() -> bool:
        return "e5" in _nome_modelo().lower()

    def _prefixo_passagem(self, texto: str) -> str:
        return f"passage: {texto}" if self._e5() else texto

    def _prefixo_pergunta(self, texto: str) -> str:
        return f"query: {texto}" if self._e5() else texto


# Instância partilhada
indice_semantico = IndiceSemantico()
