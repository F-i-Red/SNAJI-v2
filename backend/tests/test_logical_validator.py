
from app.reasoning.logical_validator import LogicalValidator

def test_logic():

    validator = LogicalValidator()

    result = validator.validate({})

    assert result["logical_consistency"]
