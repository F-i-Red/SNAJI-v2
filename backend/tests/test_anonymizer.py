
from app.security.anonymizer import LegalAnonymizer

def test_anonymization():

    anonymizer = LegalAnonymizer()

    result = anonymizer.anonymize(
        "Joao Silva 123456789"
    )

    assert "[NIF_REDACTED]" in result
