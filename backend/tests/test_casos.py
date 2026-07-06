"""
Testes da persistência de casos (SNAJI v5.3) — repositório e isolamento.
"""

import pytest
from app.db import casos_repo


@pytest.fixture(autouse=True)
def casos_limpos(tmp_path, monkeypatch):
    """Cada teste usa um ficheiro de casos isolado e descartável."""
    monkeypatch.setattr(casos_repo, "FICHEIRO_CASOS", tmp_path / "casos.json")


class TestRepositorioCasos:
    def test_guardar_e_listar(self):
        cid = casos_repo.guardar_caso("u1", {"relato": "Despedimento sem justa causa."})
        lista = casos_repo.listar_casos("u1")
        assert len(lista) == 1
        assert lista[0]["caso_id"] == cid
        assert "Despedimento" in lista[0]["titulo"]

    def test_isolamento_entre_utilizadores(self):
        casos_repo.guardar_caso("u1", {"relato": "Caso da utilizadora 1."})
        assert casos_repo.listar_casos("u2") == []
        cid = casos_repo.listar_casos("u1")[0]["caso_id"]
        assert casos_repo.obter_caso("u2", cid) is None   # nunca vê caso alheio

    def test_anexar_analises_acumula_historico(self):
        cid = casos_repo.guardar_caso("u1", {"relato": "Caso com análises."})
        assert casos_repo.anexar_cenarios("u1", cid, {"convergencia": True, "cenarios": []})
        assert casos_repo.anexar_cenarios("u1", cid, {"convergencia": False, "cenarios": []})
        caso = casos_repo.obter_caso("u1", cid)
        assert len(caso["analises_cenarios"]) == 2
        assert all("analisado_em" in a for a in caso["analises_cenarios"])

    def test_anexar_a_caso_inexistente_devolve_false(self):
        assert casos_repo.anexar_cenarios("u1", "nao-existe", {}) is False

    def test_percurso_nao_e_guardado(self):
        """O percurso de explicabilidade pede-se de novo; não incha o histórico."""
        cid = casos_repo.guardar_caso("u1", {"relato": "Caso."})
        casos_repo.anexar_cenarios("u1", cid, {"convergencia": True, "percurso": [1, 2, 3]})
        caso = casos_repo.obter_caso("u1", cid)
        assert "percurso" not in caso["analises_cenarios"][0]

    def test_lista_ordenada_do_mais_recente(self):
        casos_repo.guardar_caso("u1", {"relato": "Primeiro caso."})
        casos_repo.guardar_caso("u1", {"relato": "Segundo caso."})
        lista = casos_repo.listar_casos("u1")
        assert len(lista) == 2
        assert lista[0]["criado_em"] >= lista[1]["criado_em"]
