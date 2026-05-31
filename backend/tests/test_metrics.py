
from app.observability.legal_metrics import LegalMetrics

def test_metrics():

    metrics = LegalMetrics()

    result = metrics.collect()

    assert "casos_processados" in result
