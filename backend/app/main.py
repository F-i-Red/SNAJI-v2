import os
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.api.auth_routes import router as auth_router
from app.api.workflow_routes import router as workflow_router
from app.api.audiencias_routes import router as audiencias_router
from app.api.integracoes_routes import router as integracoes_router
from app.api.instrutor_routes import router as instrutor_router
from app.api.cenarios_routes import router as cenarios_router
from app.api.analista_routes import router as analista_router
from app.api.casos_routes import router as casos_router

structlog.configure(processors=[
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.add_log_level,
    structlog.processors.JSONRenderer(),
])
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.rag.motor import RAGJuridico
    from app.integrations.jurisprudencia import motor_jurisprudencia
    rag = RAGJuridico()
    logger.info("snaji.start",
        artigos_corpus=rag.total_artigos,
        acordaos=motor_jurisprudencia.total_acordaos,
        versao="5.3.0",
        fases="1+2+3+4+instrutor+cenarios+analista+casos",
    )
    yield
    logger.info("snaji.shutdown")


app = FastAPI(
    title="SNAJI — Sistema Nacional de Assistência Jurídica Inteligente",
    version="5.3.0",
    description=(
        "Motor jurídico português completo. "
        "RAG (246 artigos reais), autenticação RBAC + CMD, "
        "workflow processual com prazos legais, audiências multi-agente, "
        "integração DRE e jurisprudência. "
        "Inclui o AgenteInstrutor: instrução do caso por perguntas "
        "estruturadas, com alertas de prazos e vias não judiciais "
        "(Especificação V8)."
    ),
    lifespan=lifespan,
)

def _verificar_dependencias() -> None:
    """Verifica ao arranque se as dependências do requirements.txt estão
    instaladas. NUNCA instala nada (um servidor não instala pacotes sozinho —
    segurança); apenas avisa no terminal, com o comando exato para resolver."""
    em_falta, opcionais = [], []
    try:
        import pypdf  # noqa: F401  (leitura de PDF — essencial)
    except ImportError:
        em_falta.append("pypdf (leitura de PDF)")
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        opcionais.append("pytesseract/Pillow (OCR de imagens)")
    if em_falta or opcionais:
        print("=" * 66)
        if em_falta:
            print("[SNAJI] DEPENDÊNCIAS EM FALTA (funcionalidades vão falhar):")
            for d in em_falta:
                print(f"        - {d}")
        if opcionais:
            print("[SNAJI] Dependências opcionais em falta:")
            for d in opcionais:
                print(f"        - {d}")
        print("[SNAJI] Resolver com:  pip install -r requirements.txt")
        print("        (ou executar o script preparar.bat na pasta backend)")
        print("=" * 66)


_verificar_dependencias()


def _backup_diario() -> None:
    """Cópia diária dos dados persistidos (casos, processos, config).
    Corre no arranque: se o backup de hoje não existe, cria-o."""
    import shutil
    from datetime import date
    from pathlib import Path
    base = Path(__file__).parent / "db"
    destino = base / "backups" / date.today().isoformat()
    if destino.exists():
        return
    destino.mkdir(parents=True, exist_ok=True)
    for nome in ("casos.json", "processos.json", "config.json"):
        f = base / nome
        if f.exists():
            shutil.copy2(f, destino / nome)
    import structlog
    structlog.get_logger(__name__).info("backup.diario", pasta=str(destino))


_backup_diario()

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["*"],
)

app.include_router(auth_router,         prefix="/api/v1")
app.include_router(router,              prefix="/api/v1")
app.include_router(workflow_router,     prefix="/api/v1")
app.include_router(audiencias_router,   prefix="/api/v1")
app.include_router(integracoes_router,  prefix="/api/v1")
app.include_router(instrutor_router,    prefix="/api/v1")
app.include_router(cenarios_router,     prefix="/api/v1")
app.include_router(analista_router,     prefix="/api/v1")
app.include_router(casos_router,        prefix="/api/v1")


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})

@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    logger.error("unhandled.error", path=str(request.url), error=str(exc))
    return JSONResponse(status_code=500, content={"detail": "Erro interno."})

@app.get("/health", tags=["Sistema"])
async def health():
    return {
        "status": "ok",
        "sistema": "SNAJI",
        "versao": "5.3.0",
        "fases": "1+2+3+4+instrutor+cenarios+analista+casos",
        "componentes": {
            "rag": "activo",
            "workflow": "activo",
            "audiencias": "activo",
            "integracoes": "activo",
            "instrutor": "activo",
            "cenarios": "activo",
            "analista": "activo",
        }
    }
