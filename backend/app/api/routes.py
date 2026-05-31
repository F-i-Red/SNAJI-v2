
from fastapi import APIRouter
from app.orchestrator.legal_orchestrator import LegalOrchestrator

router = APIRouter()

orchestrator = LegalOrchestrator()

@router.get("/health")
async def health():
    return {"status": "healthy"}

@router.post("/analysis")
async def analyse_case(payload: dict):

    texto = payload.get("texto", "")

    result = orchestrator.process(texto)

    return result
