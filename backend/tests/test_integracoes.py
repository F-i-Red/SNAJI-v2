"""
Testes das integrações governamentais — Fase 4.
Testam sem dependências externas — DRE usa fallback local.
"""
import os
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("JWT_SECRET", "test-secret-fase4-snaji")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.integrations.jurisprudencia import MotorJurisprudencia
from app.integrations.cmd import GestorCMD

client = TestClient(app)


def login(email: str, pw: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200
    return r.json()["access_token"]

def h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestJurisprudencia:

    def setup_method(self):
        self.motor = MotorJurisprudencia()

    def test_pesquisa_despedimento(self):
        r = self.motor.pesquisar("despedimento sem justa causa trabalhador")
        assert r.total > 0
        assert any("despedimento" in a.sumario.lower() for a in r.acordaos)

    def test_pesquisa_prescricao_credito(self):
        """Base real: o AUJ 6/2022 fixa a prescrição das prestações de crédito."""
        r = self.motor.pesquisar("prescrição prestações crédito mútuo quotas amortização")
        assert r.total > 0
        assert any("UNIFORMIZAÇÃO" in " ".join(a.descritores).upper() for a in r.acordaos)
        assert any("prescrição" in a.sumario.lower() for a in r.acordaos)

    def test_pesquisa_sem_resultados_nao_falha(self):
        """Tema sem acórdãos na base devolve 0 resultados, sem erro nem invenções."""
        r = self.motor.pesquisar("corrupção funcionário público suborno")
        assert r.total == 0
        assert r.acordaos == []

    def test_acordaos_por_norma_ct366(self):
        """Cruzamento norma→acórdão: o AUJ 7/2024 interpreta o art. 366.º do CT."""
        acordaos = self.motor.acordaos_por_norma("CT", "366")
        assert len(acordaos) > 0
        assert all("CT-366" in a.normas_citadas for a in acordaos)

    def test_acordaos_por_norma_cc498(self):
        """O AUJ 14/2025 (prescrição, ocupação ilícita) cita o art. 498.º do CC."""
        acordaos = self.motor.acordaos_por_norma("CC", "498")
        assert len(acordaos) > 0

    def test_acordaos_por_norma_inexistente(self):
        acordaos = self.motor.acordaos_por_norma("CRP", "999")
        assert len(acordaos) == 0

    def test_resultado_tem_url(self):
        r = self.motor.pesquisar("despedimento")
        for a in r.acordaos:
            assert a.url
            assert "dgsi.pt" in a.url or "tribunalconstitucional.pt" in a.url

    def test_resultado_tem_tribunal(self):
        r = self.motor.pesquisar("despedimento")
        for a in r.acordaos:
            assert a.tribunal in ("STJ", "TRL", "TRP", "TRC", "TRE", "TRG", "TC")

    def test_total_acordaos_base(self):
        assert self.motor.total_acordaos >= 7


class TestCMD:

    def test_gestor_sem_config_nao_configurado(self):
        g = GestorCMD(config=None)
        assert not g.esta_configurada()

    def test_gerar_url_sem_config_lanca_erro(self):
        g = GestorCMD(config=None)
        with pytest.raises(ValueError, match="CMD não configurada"):
            g.gerar_url_autorizacao()

    def test_pkce_verifier_e_challenge_diferentes(self):
        from app.integrations.cmd import ConfigCMD
        g = GestorCMD(ConfigCMD("id", "secret", "http://localhost/cb"))
        v1, c1 = g._gerar_pkce()
        v2, c2 = g._gerar_pkce()
        assert v1 != v2  # cada chamada gera valores únicos
        assert c1 != c2
        assert v1 != c1  # verifier ≠ challenge


class TestIntegracoeAPI:

    def test_jurisprudencia_despedimento(self):
        token = login("advogado@snaji.gov.pt", "Advog2024!")
        r = client.get("/api/v1/integracoes/jurisprudencia?q=despedimento+justa+causa&top_k=3", headers=h(token))
        assert r.status_code == 200
        data = r.json()
        assert "acordaos" in data
        assert data["total"] > 0

    def test_jurisprudencia_norma(self):
        token = login("magistrado@snaji.gov.pt", "Magis2024!")
        r = client.get("/api/v1/integracoes/jurisprudencia/norma?diploma=CRP&artigo=53", headers=h(token))
        assert r.status_code == 200
        assert r.json()["norma"] == "Art. 53.º CRP"

    def test_jurisprudencia_sem_token(self):
        r = client.get("/api/v1/integracoes/jurisprudencia?q=teste")
        assert r.status_code == 401

    def test_dre_pesquisar_fallback(self):
        """O DRE pode estar indisponível nos testes — usa fallback local."""
        token = login("advogado@snaji.gov.pt", "Advog2024!")
        r = client.get("/api/v1/integracoes/dre/pesquisar?q=código+do+trabalho", headers=h(token))
        # Aceita 200 (online ou fallback) — nunca deve ser 500
        assert r.status_code == 200
        assert "diplomas" in r.json()

    def test_dre_vigencia(self):
        token = login("advogado@snaji.gov.pt", "Advog2024!")
        r = client.get("/api/v1/integracoes/dre/vigencia?diploma=CRP&artigo=53", headers=h(token))
        assert r.status_code == 200
        data = r.json()
        assert data["diploma"] == "CRP"
        assert data["artigo"] == "53"
        assert "em_corpus_local" in data
        assert data["em_corpus_local"] is True

    def test_cmd_iniciar_sem_config(self):
        """Sem configuração CMD, devolve 503 com instrução clara."""
        r = client.get("/api/v1/auth/cmd/iniciar")
        assert r.status_code == 503
        assert "CMD_CLIENT_ID" in r.json()["detail"]

    def test_estado_integracoes_magistrado(self):
        token = login("magistrado@snaji.gov.pt", "Magis2024!")
        r = client.get("/api/v1/integracoes/estado", headers=h(token))
        assert r.status_code == 200
        estado = r.json()["integracoes"]
        assert "rag" in estado
        assert estado["rag"]["artigos"] >= 6000   # corpus integral (10 diplomas)
        assert "jurisprudencia" in estado
        assert estado["jurisprudencia"]["acordaos"] >= 13   # AUJ reais do STJ

    def test_estado_integracoes_cidadao_negado(self):
        """Cidadão não tem acesso ao estado das integrações."""
        token = login("cidadao@snaji.gov.pt", "Cidad2024!")
        r = client.get("/api/v1/integracoes/estado", headers=h(token))
        assert r.status_code == 403

    def test_health_versao_5(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["versao"].startswith("5.")
        for componente in ("instrutor", "cenarios", "analista", "casos"):
            assert componente in r.json()["fases"]
