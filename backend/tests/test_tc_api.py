
from app.integrations.tribunal_constitucional import TribunalConstitucionalAPI

def test_tc_search():

    api = TribunalConstitucionalAPI()

    result = api.search_acordaos("igualdade")

    assert "acordaos" in result
