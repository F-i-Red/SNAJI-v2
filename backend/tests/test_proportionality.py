
from app.reasoning.proportionality_test import ProportionalityTest

def test_proportionality():

    test = ProportionalityTest()

    result = test.execute("medida")

    assert result["adequacy"]
