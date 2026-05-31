
from app.performance.legal_benchmark import LegalBenchmark

def test_benchmark():

    benchmark = LegalBenchmark()

    result = benchmark.run()

    assert result["hallucination_rate"] < 0.1
