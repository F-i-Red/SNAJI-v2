
from fastapi import APIRouter
from app.reasoning.reasoning_pipeline import ReasoningPipeline

router = APIRouter()

pipeline = ReasoningPipeline()

@router.post("/reasoning/analyse")
async def reasoning_analysis(payload: dict):

    result = pipeline.execute(payload)

    return result
