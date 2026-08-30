"""
Limitação de pedidos (rate limiting).

Sem isto, um utilizador autenticado — ou um script — pode disparar análises
em cadeia. Cada análise consome tokens do serviço de IA, ou seja, dinheiro,
e ocupa o servidor. Num serviço público é abuso trivial de executar.

Desenho deliberadamente simples: contadores em memória, por utilizador (ou
por endereço, quando não há sessão) e por classe de rota. Não substitui uma
solução de infraestrutura (Redis partilhado, ou limitação no balanceador),
que é o que se exige em produção com vários processos — aqui protege-se o
caso real de um único servidor.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)

# (limite de pedidos, janela em segundos) por classe de rota
LIMITES: dict[str, tuple[int, int]] = {
    "pesado": (12, 300),    # análises e geração: 12 por 5 minutos
    "escrita": (60, 300),   # criar/alterar processos, audiências, provas
    "leitura": (240, 60),   # consultas: generoso, só trava automatismos
}

# Rotas que envolvem chamadas ao modelo de linguagem (as caras)
_PESADAS = (
    "/analysis", "/cenarios", "/instrutor", "/gerar-documento",
    "/pecas", "/dossie", "/intervencao-ia", "/decidir", "/documentos",
)

_registos: dict[str, deque] = defaultdict(deque)


def _classe(caminho: str, metodo: str) -> str:
    if any(p in caminho for p in _PESADAS):
        return "pesado"
    if metodo in ("POST", "PUT", "PATCH", "DELETE"):
        return "escrita"
    return "leitura"


def _identidade(request: Request) -> str:
    """Utilizador autenticado quando possível; caso contrário, o endereço."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return "t:" + auth[7:][-24:]  # sufixo do token: identifica sem o guardar
    return "ip:" + (request.client.host if request.client else "desconhecido")


async def limitar_pedidos(request: Request, call_next):
    caminho = request.url.path
    if caminho in ("/health", "/docs", "/openapi.json") or request.method == "OPTIONS":
        return await call_next(request)

    classe = _classe(caminho, request.method)
    limite, janela = LIMITES[classe]
    chave = f"{_identidade(request)}|{classe}"

    agora = time.time()
    marcas = _registos[chave]
    while marcas and agora - marcas[0] > janela:
        marcas.popleft()

    if len(marcas) >= limite:
        espera = int(janela - (agora - marcas[0])) + 1
        logger.warning("limite.pedidos.excedido", classe=classe, caminho=caminho)
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(espera)},
            content={"detail": (
                f"Demasiados pedidos. Aguarde {espera} segundos antes de tentar de novo."
            )},
        )

    marcas.append(agora)
    resposta = await call_next(request)
    resposta.headers["X-RateLimit-Limit"] = str(limite)
    resposta.headers["X-RateLimit-Remaining"] = str(max(0, limite - len(marcas)))
    return resposta
