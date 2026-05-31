
from app.rag.retrieval_pipeline import RetrievalPipeline

def test_retrieval():

    pipeline = RetrievalPipeline()

    results = pipeline.retrieve("igualdade")

    assert len(results) > 0
