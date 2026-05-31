
from app.orchestrator.legal_orchestrator import LegalOrchestrator

def test_process():

    orchestrator = LegalOrchestrator()

    result = orchestrator.process("Teste")

    assert "result" in result
