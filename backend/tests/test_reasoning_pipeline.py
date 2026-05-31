
from app.reasoning.reasoning_pipeline import ReasoningPipeline

def test_reasoning():

    pipeline = ReasoningPipeline()

    result = pipeline.execute({})

    assert "reasoning" in result
