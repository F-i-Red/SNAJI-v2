
from fastapi import APIRouter
from app.rag.retrieval_pipeline import RetrievalPipeline

router = APIRouter()

pipeline = RetrievalPipeline()

@router.post("/rag/search")
async def rag_search(payload: dict):

    query = payload.get("query", "")

    results = pipeline.retrieve(query)

    return {
        "results": results
    }
