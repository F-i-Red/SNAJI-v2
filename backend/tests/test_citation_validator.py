
from app.rag.citation_validator import CitationValidator

def test_valid_citation():

    validator = CitationValidator()

    assert validator.validate("CRP", "13")
