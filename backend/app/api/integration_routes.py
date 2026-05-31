
from fastapi import APIRouter
from app.integrations.dr_api import DiarioRepublicaAPI
from app.integrations.tribunal_constitucional import TribunalConstitucionalAPI

router = APIRouter()

dr_api = DiarioRepublicaAPI()
tc_api = TribunalConstitucionalAPI()

@router.get("/integrations/dre/search")
async def search_dre(query: str):

    return dr_api.search_diploma(query)

@router.get("/integrations/tc/search")
async def search_tc(tema: str):

    return tc_api.search_acordaos(tema)
