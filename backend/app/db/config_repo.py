"""
Configuração do sistema — SNAJI
================================
Guarda definições institucionais editáveis pelo administrador técnico, sem
tocar no código. Neste momento: os contactos de apoio que os utilizadores veem
quando precisam de ajuda ou de um pedido especial (ex.: um processo demasiado
extenso para a análise automática).

Persistência simples em JSON, com valores por omissão sensatos — o sistema
funciona mesmo antes de o admin configurar seja o que for.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

FICHEIRO_CONFIG = Path(__file__).parent / "config.json"
_lock = threading.Lock()

# Valores por omissão — o admin altera-os na aplicação, não no código
_PADRAO = {
    "email_suporte": "",
    "telefone_suporte": "",
    "horario": "",
    "mensagem_casos_extensos": (
        "Este caso excede o limite de análise automática. Para processamento "
        "de processos muito extensos, contacte o SNAJI pelos meios indicados."
    ),
}


def _carregar() -> dict:
    if not FICHEIRO_CONFIG.exists():
        return dict(_PADRAO)
    try:
        dados = json.loads(FICHEIRO_CONFIG.read_text(encoding="utf-8"))
        # completa com padrões para chaves em falta (retrocompatível);
        # os carimbos atualizado_em/atualizado_por vêm dos dados gravados
        return {**_PADRAO, **dados}
    except Exception as exc:
        logger.warning("config.leitura_falhou", erro=str(exc)[:120])
        return dict(_PADRAO)


def obter_config() -> dict:
    """Configuração atual (contactos e mensagens). Pública — qualquer perfil lê."""
    with _lock:
        return _carregar()


def guardar_config(novos: dict, utilizador_id: str) -> dict:
    """Atualiza a configuração (só admin). Ignora chaves desconhecidas."""
    from datetime import datetime, timezone
    with _lock:
        atual = _carregar()
        for chave in _PADRAO:
            if chave in novos and novos[chave] is not None:
                atual[chave] = str(novos[chave]).strip()
        # carimbo do servidor: prova de quando/quem gravou (diagnóstico)
        atual["atualizado_em"] = datetime.now(timezone.utc).isoformat()
        atual["atualizado_por"] = utilizador_id
        # Gravação atómica (Windows-safe): escreve num temporário e substitui.
        tmp = FICHEIRO_CONFIG.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(atual, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(FICHEIRO_CONFIG)
        logger.info("config.gravada_em", caminho=str(FICHEIRO_CONFIG.resolve()))
    logger.info("config.guardada", por=utilizador_id, chaves=list(novos.keys()))
    return atual
