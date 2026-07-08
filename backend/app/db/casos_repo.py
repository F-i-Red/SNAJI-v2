"""
Repositório de Casos — SNAJI
=============================
Persistência dos casos instruídos e das suas análises, por utilizador.
Resolve o problema de UX: "criei um caso, mudei de aba, desapareceu".

Cada caso guarda: relato, Ficha de Factos, alertas, áreas, papel e as
análises de cenários que lhe forem sendo anexadas — o histórico completo.

PoC: armazenamento em JSON (backend/app/db/casos.json), thread-safe,
isolado por utilizador (um utilizador nunca vê casos de outro).
Versão institucional: migra para a base de dados relacional — a interface
(guardar/listar/obter/anexar) mantém-se.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)

FICHEIRO_CASOS = Path(__file__).parent / "casos.json"
_lock = threading.Lock()


def _carregar() -> dict:
    if not FICHEIRO_CASOS.exists():
        return {}
    try:
        return json.loads(FICHEIRO_CASOS.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.error("casos.ficheiro_corrompido — a começar vazio")
        return {}


def _gravar(dados: dict) -> None:
    FICHEIRO_CASOS.write_text(
        json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def guardar_caso(user_id: str, dados: dict) -> str:
    """Guarda um caso concluído no Instrutor. Devolve o id do caso."""
    caso_id = dados.get("caso_id") or str(uuid.uuid4())
    relato = dados.get("relato", "")
    titulo = (relato[:70] + "…") if len(relato) > 70 else (relato or "Caso sem descrição")
    with _lock:
        todos = _carregar()
        todos.setdefault(str(user_id), {})[caso_id] = {
            "caso_id": caso_id,
            "titulo": titulo,
            "criado_em": datetime.now(timezone.utc).isoformat(),
            "areas": dados.get("areas", []),
            "papel": dados.get("papel", ""),
            "numero_processo": dados.get("numero_processo", ""),
            "relato": relato,
            "ficha": dados.get("ficha", {}),
            "alertas": dados.get("alertas", []),
            "texto_para_analise": dados.get("texto_para_analise", ""),
            "analises_cenarios": [],
            "analises_juridicas": [],
        }
        _gravar(todos)
    logger.info("caso.guardado", caso_id=caso_id)
    return caso_id


def listar_casos(user_id: str) -> list[dict]:
    """Lista os casos do utilizador (resumo), do mais recente para o mais antigo."""
    todos = _carregar().get(str(user_id), {})
    resumo = [
        {
            "caso_id": c["caso_id"],
            "titulo": c["titulo"],
            "criado_em": c["criado_em"],
            "areas": c.get("areas", []),
            "papel": c.get("papel", ""),
            "numero_processo": c.get("numero_processo", ""),
            "n_alertas": len(c.get("alertas", [])),
            "n_analises": len(c.get("analises_cenarios", [])),
        }
        for c in todos.values()
    ]
    return sorted(resumo, key=lambda c: c["criado_em"], reverse=True)


def obter_caso(user_id: str, caso_id: str) -> Optional[dict]:
    """Devolve o caso completo — apenas se pertencer ao utilizador."""
    return _carregar().get(str(user_id), {}).get(caso_id)


def _essencia(d: dict) -> str:
    """Representação estável de uma análise, ignorando campos voláteis —
    serve para detetar repetições exatas (idempotência)."""
    limpo = {k: v for k, v in d.items()
             if k not in ("analisado_em", "percurso", "caso_id", "timestamp", "audit")}
    return json.dumps(limpo, ensure_ascii=False, sort_keys=True)


def _anexar(user_id: str, caso_id: str, campo: str, resultado: dict, evento: str) -> bool:
    """Anexa uma análise ao histórico do caso. Idempotente: se for exatamente
    igual à última guardada, não acumula duplicados (repetir não é criar)."""
    with _lock:
        todos = _carregar()
        caso = todos.get(str(user_id), {}).get(caso_id)
        if not caso:
            return False
        lista = caso.setdefault(campo, [])
        resultado = dict(resultado)
        resultado.pop("percurso", None)  # o percurso pede-se de novo quando se quer
        if lista and _essencia(lista[-1]) == _essencia(resultado):
            logger.info(f"caso.{evento}_repetida_ignorada", caso_id=caso_id)
            return True
        resultado["analisado_em"] = datetime.now(timezone.utc).isoformat()
        lista.append(resultado)
        _gravar(todos)
    logger.info(f"caso.{evento}_anexada", caso_id=caso_id)
    return True


def anexar_cenarios(user_id: str, caso_id: str, resultado: dict) -> bool:
    """Anexa uma análise de cenários ao histórico do caso (idempotente)."""
    return _anexar(user_id, caso_id, "analises_cenarios", resultado, "cenarios")


def anexar_analise_juridica(user_id: str, caso_id: str, resultado: dict) -> bool:
    """Anexa uma análise jurídica (pipeline) ao histórico do caso (idempotente)."""
    return _anexar(user_id, caso_id, "analises_juridicas", resultado, "analise_juridica")
