
from app.integrations.dr_api import DiarioRepublicaAPI

def test_dre_search():

    api = DiarioRepublicaAPI()

    result = api.search_diploma("Constituição")

    assert result["source"] == "Diário da República"
