
from app.validation.norm_validator import NormValidator

def test_valid_reference():

    validator = NormValidator()

    assert validator.validate_reference("CRP", "13")
