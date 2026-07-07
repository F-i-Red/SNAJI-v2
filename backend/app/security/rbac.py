"""
Controlo de Acesso Baseado em Funções (RBAC) do SNAJI.

Regra base: cada utilizador tem exactamente um papel (role).
Cada papel tem um conjunto de permissões fixas.
O sistema nunca concede mais permissões do que o papel permite.
"""

from enum import Enum
from functools import lru_cache


class Role(str, Enum):
    ADMIN      = "admin"
    MAGISTRADO = "magistrado"
    ADVOGADO   = "advogado"
    ANALISTA   = "analista"
    CIDADAO    = "cidadao"


class Permissao(str, Enum):
    # Casos jurídicos
    SUBMETER_CASO   = "submeter_caso"       # instruir e analisar casos (trabalho cognitivo)
    GERIR_PROCESSOS = "gerir_processos"     # criar/avançar/retificar na carteira de processos
    LER_CASO_PROPRIO = "ler_caso_proprio"
    LER_CASO_QUALQUER = "ler_caso_qualquer"
    VER_ANALISE     = "ver_analise"

    # Auditoria
    VER_AUDITORIA_BASICA   = "ver_auditoria_basica"
    VER_AUDITORIA_COMPLETA = "ver_auditoria_completa"

    # Administração
    GERIR_UTILIZADORES = "gerir_utilizadores"
    VER_METRICAS       = "ver_metricas"
    ACESSO_TOTAL       = "*"


# Tabela de permissões por papel — única fonte de verdade
_PERMISSOES: dict[Role, frozenset[Permissao]] = {
    Role.ADMIN: frozenset([Permissao.ACESSO_TOTAL]),

    Role.MAGISTRADO: frozenset([
        Permissao.SUBMETER_CASO,
        Permissao.GERIR_PROCESSOS,
        Permissao.LER_CASO_PROPRIO,
        Permissao.LER_CASO_QUALQUER,
        Permissao.VER_ANALISE,
        Permissao.VER_AUDITORIA_BASICA,
        Permissao.VER_AUDITORIA_COMPLETA,
        Permissao.VER_METRICAS,
    ]),

    Role.ADVOGADO: frozenset([
        Permissao.SUBMETER_CASO,
        Permissao.GERIR_PROCESSOS,
        Permissao.LER_CASO_PROPRIO,
        Permissao.VER_ANALISE,
        Permissao.VER_AUDITORIA_BASICA,
    ]),

    Role.ANALISTA: frozenset([
        Permissao.LER_CASO_QUALQUER,
        Permissao.VER_ANALISE,
        Permissao.VER_AUDITORIA_BASICA,
        Permissao.VER_METRICAS,
    ]),

    Role.CIDADAO: frozenset([
        Permissao.SUBMETER_CASO,
        Permissao.LER_CASO_PROPRIO,
        Permissao.VER_ANALISE,
    ]),
}


class RBACManager:
    """
    Verifica permissões de forma determinística.
    Sem lógica complexa — apenas consulta a tabela acima.
    """

    def tem_permissao(self, role: Role | str, permissao: Permissao | str) -> bool:
        """Devolve True se o papel tem a permissão pedida."""
        try:
            r = Role(role) if isinstance(role, str) else role
            p = Permissao(permissao) if isinstance(permissao, str) else permissao
        except ValueError:
            return False  # papel ou permissão desconhecida → nega sempre

        perms = _PERMISSOES.get(r, frozenset())

        # Admin com ACESSO_TOTAL passa em tudo
        if Permissao.ACESSO_TOTAL in perms:
            return True

        return p in perms

    def permissoes_do_role(self, role: Role | str) -> list[str]:
        """Lista todas as permissões de um papel (para debug/docs)."""
        try:
            r = Role(role) if isinstance(role, str) else role
        except ValueError:
            return []
        return [p.value for p in _PERMISSOES.get(r, frozenset())]


# Instância partilhada — não precisa de ser recriada
rbac = RBACManager()
