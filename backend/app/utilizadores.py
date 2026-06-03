"""
Repositório de utilizadores do SNAJI.

Para desenvolvimento: usa um dicionário em memória.
Para produção: substitui por queries PostgreSQL (a interface é a mesma).

A separação entre a interface (o que faz) e a implementação (como faz)
significa que mudar de memória para PostgreSQL não toca em mais nenhum ficheiro.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from app.security.rbac import Role
from app.security.passwords import criar_hash, verificar_password


@dataclass
class Utilizador:
    id: str
    email: str
    nome: str
    role: Role
    hash_password: str
    activo: bool = True
    criado_em: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ultimo_login: Optional[datetime] = None


class RepositorioUtilizadores:
    """
    Armazenamento de utilizadores.
    Desenvolvimento: memória. Produção: PostgreSQL.
    """

    def __init__(self):
        self._utilizadores: dict[str, Utilizador] = {}
        self._por_email: dict[str, str] = {}  # email → id
        self._seed_dados_demo()

    def _seed_dados_demo(self) -> None:
        """Cria utilizadores de demonstração para desenvolvimento."""
        demo = [
            ("admin@snaji.gov.pt",      "Administrador SNAJI", Role.ADMIN,      "Admin2024!"),
            ("magistrado@snaji.gov.pt", "Dr. António Silva",   Role.MAGISTRADO, "Magis2024!"),
            ("advogado@snaji.gov.pt",   "Dra. Maria Santos",   Role.ADVOGADO,   "Advog2024!"),
            ("analista@snaji.gov.pt",   "João Ferreira",       Role.ANALISTA,   "Anali2024!"),
            ("cidadao@snaji.gov.pt",    "Ana Costa",           Role.CIDADAO,    "Cidad2024!"),
        ]
        for email, nome, role, password in demo:
            self.criar(email=email, nome=nome, role=role, password=password)

    def criar(self, email: str, nome: str, role: Role, password: str) -> Utilizador:
        """Cria um novo utilizador. Lança ValueError se o email já existir."""
        if email in self._por_email:
            raise ValueError(f"Email já registado: {email}")
        uid = str(uuid4())
        u = Utilizador(
            id=uid,
            email=email,
            nome=nome,
            role=role,
            hash_password=criar_hash(password),
        )
        self._utilizadores[uid] = u
        self._por_email[email] = uid
        return u

    def por_email(self, email: str) -> Optional[Utilizador]:
        """Devolve utilizador pelo email, ou None se não existir."""
        uid = self._por_email.get(email)
        return self._utilizadores.get(uid) if uid else None

    def por_id(self, uid: str) -> Optional[Utilizador]:
        """Devolve utilizador pelo ID, ou None se não existir."""
        return self._utilizadores.get(uid)

    def autenticar(self, email: str, password: str) -> Optional[Utilizador]:
        """
        Verifica email + password.
        Devolve o utilizador se correcto, None caso contrário.
        Nunca indica se foi o email ou a password que estava errada
        (segurança: não revela informação sobre contas existentes).
        """
        u = self.por_email(email)
        if not u or not u.activo:
            # Mesmo sem utilizador, verifica a password para evitar timing attacks
            verificar_password(password, "$2b$12$dummy_hash_para_timing_attack_prevention")
            return None
        if not verificar_password(password, u.hash_password):
            return None
        # Actualiza último login
        u.ultimo_login = datetime.now(timezone.utc)
        return u

    def listar(self) -> list[Utilizador]:
        """Lista todos os utilizadores (apenas para admin)."""
        return list(self._utilizadores.values())


# Instância partilhada — em produção injectar via dependency injection
repositorio = RepositorioUtilizadores()
