import os
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # LLM
    anthropic_api_key: str = Field(..., description="Chave API Anthropic — obrigatória")
    anthropic_model: str = "claude-sonnet-4-20250514"

    # Segurança JWT — RS256 em produção
    jwt_secret: str = Field(..., description="Secret JWT — nunca hardcoded")
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 8

    # Base de dados
    database_url: str = Field(..., description="PostgreSQL connection string")

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # App
    debug: bool = False
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_settings() -> Settings:
    """
    Falha alto e cedo se variáveis obrigatórias não estiverem definidas.
    Nunca silencia erros de configuração.
    """
    try:
        return Settings()
    except Exception as e:
        raise RuntimeError(
            f"Configuração inválida: {e}\n"
            "Certifica-te de que o ficheiro .env existe e tem todas as variáveis obrigatórias."
        ) from e
