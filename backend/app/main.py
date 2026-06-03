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
        versao="4.0.0",
        fases="1+2+3+4",
    )
    yield
    logger.info("snaji.shutdown")


app = FastAPI(
    title="SNAJI — Sistema Nacional de Assistência Jurídica Inteligente",
    version="4.0.0",
    description=(
        "Motor jurídico português completo. "
        "RAG (246 artigos reais), autenticação RBAC + CMD, "
        "workflow processual com prazos legais, audiências multi-agente, "
        "integração DRE e jurisprudência."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(auth_router,         prefix="/api/v1")
app.include_router(router,              prefix="/api/v1")
app.include_router(workflow_router,     prefix="/api/v1")
app.include_router(audiencias_router,   prefix="/api/v1")
app.include_router(integracoes_router,  prefix="/api/v1")


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
        "versao": "4.0.0",
        "fases": "1+2+3+4",
        "componentes": {
            "rag": "activo",
            "workflow": "activo",
            "audiencias": "activo",
            "integracoes": "activo",
        }
    }
