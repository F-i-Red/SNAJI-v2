"""
Registo Analítico — SNAJI (Especificação V8, §8)
=================================================
Registo de eventos ANONIMIZADO POR DESENHO que alimenta o módulo Analista.

Regras invioláveis:
  - NUNCA se registam dados pessoais: sem user_id, sem nomes, sem textos
    dos casos. Apenas categorias, contagens e sinais de qualidade.
  - Cada módulo chama registar() com campos agregáveis (área, tipo de
    alerta, convergência, n.º de perguntas...).
  - Formato: JSON Lines (um evento por linha) — auditável e portátil.
    Em produção institucional migra para base de dados analítica.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

FICHEIRO_EVENTOS = Path(__file__).parent / "eventos.jsonl"
_CAMPOS_PROIBIDOS = {"user_id", "utilizador", "nome", "email", "relato", "texto", "nif"}
_lock = threading.Lock()
_LIMITE_ROTACAO_BYTES = 5 * 1024 * 1024  # 5 MB → arquiva e começa novo


def _ultimo_hash() -> str:
    """Hash do último evento gravado (âncora da cadeia)."""
    if not FICHEIRO_EVENTOS.exists():
        return "genesis"
    try:
        ultimo = ""
        with open(FICHEIRO_EVENTOS, "rb") as f:
            for linha in f:
                if linha.strip():
                    ultimo = linha
        if not ultimo:
            return "genesis"
        return json.loads(ultimo).get("hash", "genesis")
    except Exception:
        return "genesis"


def _rodar_se_grande() -> None:
    """Arquiva o registo quando excede o limite (rotação)."""
    try:
        if FICHEIRO_EVENTOS.exists() and FICHEIRO_EVENTOS.stat().st_size > _LIMITE_ROTACAO_BYTES:
            destino = FICHEIRO_EVENTOS.with_name(
                f"eventos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl")
            FICHEIRO_EVENTOS.rename(destino)
            logger.info("analitica.rotacao", arquivo=destino.name)
    except Exception as exc:
        logger.warning("analitica.rotacao_falhou", erro=str(exc))


def verificar_cadeia() -> dict:
    """Percorre a cadeia de hash e confirma a integridade do registo.
    Devolve o resultado da verificação — prova de não-adulteração."""
    if not FICHEIRO_EVENTOS.exists():
        return {"integra": True, "eventos": 0, "detalhe": "registo vazio"}
    anterior = "genesis"
    n = 0
    for linha in FICHEIRO_EVENTOS.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha:
            continue
        try:
            ev = json.loads(linha)
        except json.JSONDecodeError:
            return {"integra": False, "eventos": n,
                    "detalhe": f"linha {n + 1} ilegível"}
        h = ev.pop("hash", None)
        if h is None:
            # eventos antigos (pré-cadeia) são tolerados no início
            anterior = "genesis"
            n += 1
            continue
        esperado = hashlib.sha256(
            (anterior + json.dumps(ev, ensure_ascii=False, sort_keys=True)).encode()
        ).hexdigest()
        if h != esperado:
            return {"integra": False, "eventos": n,
                    "detalhe": f"cadeia quebrada no evento {n + 1} — registo adulterado ou corrompido"}
        anterior = h
        n += 1
    return {"integra": True, "eventos": n, "detalhe": "cadeia de hash íntegra"}


def registar(evento: str, dados: dict | None = None) -> None:
    """Regista um evento analítico anonimizado. Nunca lança exceções."""
    try:
        dados = dict(dados or {})
        proibidos = _CAMPOS_PROIBIDOS & set(dados)
        for campo in proibidos:
            dados.pop(campo)
        if proibidos:
            logger.warning("analitica.campos_pessoais_removidos", campos=sorted(proibidos))
        registo = {"ts": datetime.now(timezone.utc).isoformat(), "evento": evento, **dados}
        with _lock:
            _rodar_se_grande()
            anterior = _ultimo_hash()
            registo["hash"] = hashlib.sha256(
                (anterior + json.dumps(registo, ensure_ascii=False, sort_keys=True)).encode()
            ).hexdigest()
            with open(FICHEIRO_EVENTOS, "a", encoding="utf-8") as f:
                f.write(json.dumps(registo, ensure_ascii=False) + "\n")
    except Exception as exc:  # a analítica nunca pode partir o serviço
        logger.warning("analitica.registo_falhou", erro=str(exc))


def carregar_eventos() -> list[dict]:
    """Lê todos os eventos registados (para o motor de agregação)."""
    if not FICHEIRO_EVENTOS.exists():
        return []
    eventos = []
    for linha in FICHEIRO_EVENTOS.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha:
            continue
        try:
            eventos.append(json.loads(linha))
        except json.JSONDecodeError:
            continue
    return eventos
