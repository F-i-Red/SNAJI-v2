"""
Rotas de autenticação do SNAJI.

POST /auth/login  → faz login, recebe token
GET  /auth/me     → vê os teus dados (requer login)
GET  /auth/roles  → lista papéis e permissões (público, para documentação)
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
import structlog

from app.security.jwt_manager import jwt_manager, TokenResponse
from app.security.rbac import rbac, Role
from app.security.dependencias import requer_login
from app.db.utilizadores import repositorio, Utilizador

router = APIRouter(prefix="/auth", tags=["Autenticação"])
logger = structlog.get_logger(__name__)


class LoginRequest(BaseModel):
    email: str
    password: str


class UtilizadorInfo(BaseModel):
    id: str
    email: str
    nome: str
    role: str
    permissoes: list[str]


class RegistoRequest(BaseModel):
    nome: str = Field(..., min_length=3, max_length=80)
    email: str = Field(..., min_length=5, max_length=120)
    password: str = Field(..., min_length=10, max_length=128,
                          description="Mínimo 10 caracteres")


@router.post("/registo", response_model=TokenResponse, status_code=201)
async def registo_cidadao(dados: RegistoRequest) -> TokenResponse:
    """
    Auto-registo de CIDADÃOS. Advogados, magistrados e analistas não se
    auto-registam: são credenciados pelo administrador (a verificação do
    papel profissional — cédula da Ordem, vínculo ao CSM — é feita fora
    da aplicação). Numa versão de produção, o registo do cidadão usaria a
    Chave Móvel Digital / autenticação.gov para verificar a identidade.
    """
    import re as _re
    email = str(dados.email).strip().lower()
    if not _re.fullmatch(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}", email):
        raise HTTPException(status_code=422, detail="Indique um email válido.")
    from app.db.utilizadores import repositorio as _ru
    from app.security.rbac import Role
    try:
        u = _ru.criar(email=email,
                      nome=dados.nome.strip(),
                      role=Role.CIDADAO,
                      password=dados.password)
    except ValueError:
        # não revelar se o email existe (enumeração de contas)
        raise HTTPException(status_code=409,
                            detail="Não foi possível criar a conta com esses dados.")
    logger.info("auth.registo.cidadao", user_id=u.id)
    return jwt_manager.criar_token(user_id=u.id, role=u.role)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Fazer login",
    description="Autentica com email e password. Devolve um token JWT válido por 8 horas.",
)
async def login(dados: LoginRequest) -> TokenResponse:
    utilizador = repositorio.autenticar(dados.email, dados.password)

    if not utilizador:
        # Mensagem genérica — não revela se foi o email ou a password
        logger.warning("auth.login.falhou", email=dados.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas.",
        )

    token = jwt_manager.criar_token(
        user_id=utilizador.id,
        role=utilizador.role,
    )

    logger.info("auth.login.ok", user_id=utilizador.id, role=utilizador.role.value)
    return token


@router.get(
    "/me",
    response_model=UtilizadorInfo,
    summary="Ver os meus dados",
    description="Devolve informação sobre o utilizador autenticado e as suas permissões.",
)
async def meus_dados(
    utilizador: Utilizador = Depends(requer_login),
) -> UtilizadorInfo:
    return UtilizadorInfo(
        id=utilizador.id,
        email=utilizador.email,
        nome=utilizador.nome,
        role=utilizador.role.value,
        permissoes=rbac.permissoes_do_role(utilizador.role),
    )


@router.get(
    "/roles",
    summary="Listar papéis e permissões",
    description="Documenta os papéis disponíveis e as respectivas permissões. Público.",
)
async def listar_roles():
    return {
        "roles": [
            {
                "papel": role.value,
                "permissoes": rbac.permissoes_do_role(role),
            }
            for role in Role
        ]
    }
