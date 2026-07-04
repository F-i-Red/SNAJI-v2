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

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

FICHEIRO_EVENTOS = Path(__file__).parent / "eventos.jsonl"
_CAMPOS_PROIBIDOS = {"user_id", "utilizador", "nome", "email", "relato", "texto", "nif"}
_lock = threading.Lock()


def registar(evento: str, dados: dict | None = None) -> None:
    """Regista um evento analítico anonimizado. Nunca lança exceções."""
    try:
        dados = dict(dados or {})
        proibidos = _CAMPOS_PROIBIDOS & set(dados)
        for campo in proibidos:
            dados.pop(campo)
        if proibidos:
            logger.warning("analitica.campos_pessoais_removidos", campos=sorted(proibidos))
        linha = json.dumps(
            {"ts": datetime.now(timezone.utc).isoformat(), "evento": evento, **dados},
            ensure_ascii=False,
        )
        with _lock:
            with open(FICHEIRO_EVENTOS, "a", encoding="utf-8") as f:
                f.write(linha + "\n")
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
