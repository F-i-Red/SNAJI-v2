"""
Criação central do cliente LLM.

Lê a ANTHROPIC_API_KEY primeiro das settings da aplicação (que carregam o
ficheiro .env) e só depois do ambiente do sistema. O placeholder do
.env.example ('sk-ant-...') é tratado como ausência de chave.

Todos os componentes que precisam de LLM (pipeline, audiências, cenários,
instrutor, analisador de peças) devem usar este módulo — nunca criar o
cliente directamente — para que a configuração funcione de forma idêntica
em todo o sistema.
"""
from __future__ import annotations
import os
import structlog

logger = structlog.get_logger(__name__)


def obter_api_key() -> str:
    """Devolve a chave API ou string vazia se não configurada."""
    api_key = ""
    try:
        from app.core.config import get_settings
        api_key = (get_settings().anthropic_api_key or "").strip()
    except Exception:
        api_key = ""
    if not api_key:
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if api_key == "sk-ant-...":  # placeholder por preencher
        api_key = ""
    return api_key


def obter_modelo(default: str = "claude-sonnet-4-20250514") -> str:
    """Devolve o modelo configurado (settings → ambiente → default)."""
    try:
        from app.core.config import get_settings
        modelo = (get_settings().anthropic_model or "").strip()
        if modelo:
            return modelo
    except Exception:
        pass
    return os.getenv("ANTHROPIC_MODEL", "").strip() or default


def criar_llm(componente: str = "llm"):
    """
    Cria o cliente Anthropic se houver chave e o pacote disponível;
    caso contrário devolve None (modo stub). Nunca lança excepção.
    Chaves sem o formato oficial (prefixo 'sk-ant-') são tratadas como
    ausentes — evita chamadas de rede com chaves de teste ou mal coladas.
    """
    api_key = obter_api_key()
    if not api_key:
        logger.info(f"{componente}.llm.stub", motivo="ANTHROPIC_API_KEY ausente")
        return None
    if not api_key.startswith("sk-ant-"):
        logger.warning(
            f"{componente}.llm.stub",
            motivo="ANTHROPIC_API_KEY com formato inesperado — modo stub",
        )
        return None
    try:
        import anthropic
        cliente = anthropic.Anthropic(api_key=api_key)
        logger.info(f"{componente}.llm.ativo")
        return cliente
    except Exception as exc:  # pacote em falta ou erro de inicialização
        logger.warning(f"{componente}.llm.indisponivel", erro=str(exc))
        return None
