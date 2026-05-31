
class TribunalConstitucionalAPI:

    def search_acordaos(self, tema: str):

        return {
            "tema": tema,
            "acordaos": []
        }

    def get_acordao(self, acordao_id):

        return {
            "id": acordao_id,
            "texto": "Acórdão"
        }
