"""
Gestor de tokens JWT do SNAJI.

JWT = JSON Web Token. É um código cifrado que prova quem és.
Contém: quem és (user_id), que papel tens (role), e quando expira.
Ninguém pode falsificar um token sem conhecer o segredo do servidor.

IMPORTANTE:
- O segredo (JWT_SECRET) vem das variáveis de ambiente — nunca hardcoded.
- Tokens expiram ao fim de 8 horas por defeito.
- Em produção .gov usar RS256 com chave privada/pública.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
from pydantic import BaseModel

from app.core.config import get_settings
from app.security.rbac import Role


class TokenPayload(BaseModel):
    """O que está dentro do token JWT."""
    sub: str          # user_id
    role: str         # papel do utilizador
    exp: datetime     # quando expira
    iat: datetime     # quando foi criado


class TokenResponse(BaseModel):
    """Resposta ao fazer login."""
    access_token: str
    token_type: str = "bearer"
    expira_em: int    # segundos até expirar
    role: str


class JWTManager:
    """
    Cria e verifica tokens JWT.
    Usa o segredo das variáveis de ambiente.
    """

    def __init__(self):
        self._settings = get_settings()

    def criar_token(self, user_id: str, role: Role) -> TokenResponse:
        """
        Cria um token JWT para o utilizador.
        Válido durante JWT_EXPIRY_HOURS horas (padrão: 8).
        """
        agora = datetime.now(timezone.utc)
        expira = agora + timedelta(hours=self._settings.jwt_expiry_hours)
        expira_segundos = int(self._settings.jwt_expiry_hours * 3600)

        payload = {
            "sub": user_id,
            "role": role.value,
            "iat": agora,
            "exp": expira,
        }

        token = jwt.encode(
            payload,
            self._settings.jwt_secret,
            algorithm=self._settings.jwt_algorithm,
        )

        return TokenResponse(
            access_token=token,
            expira_em=expira_segundos,
            role=role.value,
        )

    def verificar_token(self, token: str) -> TokenPayload:
        """
        Verifica e descodifica um token JWT.
        Lança ValueError se o token for inválido ou expirado.
        """
        try:
            dados = jwt.decode(
                token,
                self._settings.jwt_secret,
                algorithms=[self._settings.jwt_algorithm],
            )
            return TokenPayload(
                sub=dados["sub"],
                role=dados["role"],
                exp=datetime.fromtimestamp(dados["exp"], tz=timezone.utc),
                iat=datetime.fromtimestamp(dados["iat"], tz=timezone.utc),
            )
        except JWTError as e:
            raise ValueError(f"Token inválido ou expirado: {e}") from e


# Instância partilhada
jwt_manager = JWTManager()
