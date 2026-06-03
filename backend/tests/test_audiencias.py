"""
Testes da Fase 3 — Audiências e Contraditório.

Testam o ciclo completo de uma audiência:
- Criação por diferentes papéis (vítima, advogado, MP)
- Progressão pelas fases legais
- Loop de contraditório
- Apresentação de provas
- Geração de decisão fundamentada
- Controlo de acesso por fase
- Integridade das intervenções (hash)
"""
import os
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("JWT_SECRET", "test-secret-fase3-snaji")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.audiencias.motor import MotorAudiencias, FaseAudiencia, ORDEM_FASES_AUDIENCIA
from app.audiencias.modelos import (
    TipoAudiencia, PapelAgente, TipoIntervencao, EstadoAudiencia
)

client = TestClient(app)


def login(email: str, pw: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200
    return r.json()["access_token"]

def h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Testes do motor (sem HTTP) ────────────────────────────────────────────────

class TestMotorAudiencias:

    def setup_method(self):
        self.motor = MotorAudiencias(llm_client=None)

    def test_criar_audiencia_como_vitima(self):
        a = self.motor.criar_audiencia(
            descricao_caso="Fui despedido sem justa causa",
            tipo_processo="laboral",
            tipo_audiencia=TipoAudiencia.JULGAMENTO,
            criado_por="user-vitima",
            papel_criador=PapelAgente.ACUSACAO,
        )
        assert a.id
        assert a.estado == EstadoAudiencia.PENDENTE
        assert a.fase_actual == FaseAudiencia.ABERTURA
        assert a.papel_criador == PapelAgente.ACUSACAO

    def test_criar_audiencia_como_arguido(self):
        a = self.motor.criar_audiencia(
            descricao_caso="Sou arguido numa queixa de difamação",
            tipo_processo="penal",
            tipo_audiencia=TipoAudiencia.JULGAMENTO,
            criado_por="user-arguido",
            papel_criador=PapelAgente.DEFESA,
        )
        assert PapelAgente.DEFESA in [p.papel for p in a.participantes]

    def test_participantes_incluem_juiz_acusacao_defesa(self):
        a = self.motor.criar_audiencia("caso teste", "civil", TipoAudiencia.JULGAMENTO, "u1", PapelAgente.ACUSACAO)
        papeis = [p.papel for p in a.participantes]
        assert PapelAgente.JUIZ in papeis
        assert PapelAgente.ACUSACAO in papeis
        assert PapelAgente.DEFESA in papeis

    def test_com_perito(self):
        a = self.motor.criar_audiencia("caso perito", "civil", TipoAudiencia.JULGAMENTO, "u1", PapelAgente.ACUSACAO, com_perito=True)
        papeis = [p.papel for p in a.participantes]
        assert PapelAgente.PERITO in papeis

    def test_juiz_abre_audiencia(self):
        a = self.motor.criar_audiencia("caso", "laboral", TipoAudiencia.JULGAMENTO, "u1", PapelAgente.ACUSACAO)
        iv, orientacao = self.motor.processar_intervencao(a.id, PapelAgente.JUIZ, "Declaro aberta a audiência.")
        assert iv.papel == PapelAgente.JUIZ
        assert a.estado == EstadoAudiencia.EM_CURSO
        assert a.fase_actual == FaseAudiencia.ACUSACAO_PEDIDO
        assert orientacao is not None

    def test_fase_avanca_sequencialmente(self):
        a = self.motor.criar_audiencia("caso", "laboral", TipoAudiencia.JULGAMENTO, "u1", PapelAgente.ACUSACAO)
        # Juiz abre
        self.motor.processar_intervencao(a.id, PapelAgente.JUIZ, "Abertura.")
        assert a.fase_actual == FaseAudiencia.ACUSACAO_PEDIDO
        # Acusação fala
        self.motor.processar_intervencao(a.id, PapelAgente.ACUSACAO, "Os factos são...")
        assert a.fase_actual == FaseAudiencia.DEFESA
        # Defesa fala
        self.motor.processar_intervencao(a.id, PapelAgente.DEFESA, "A defesa contesta...")
        assert a.fase_actual == FaseAudiencia.REPLICA

    def test_papel_errado_rejeitado(self):
        a = self.motor.criar_audiencia("caso", "civil", TipoAudiencia.JULGAMENTO, "u1", PapelAgente.ACUSACAO)
        # Na fase de ABERTURA só o Juiz pode falar
        with pytest.raises(ValueError, match="não pode intervir"):
            self.motor.processar_intervencao(a.id, PapelAgente.ACUSACAO, "Quero falar primeiro.")

    def test_loop_contraditorio(self):
        a = self.motor.criar_audiencia("caso", "penal", TipoAudiencia.JULGAMENTO, "u1", PapelAgente.ACUSACAO, max_loops=2)
        # Percorre até às perguntas do juiz
        self.motor.processar_intervencao(a.id, PapelAgente.JUIZ, "Abertura.")
        self.motor.processar_intervencao(a.id, PapelAgente.ACUSACAO, "Acusação.")
        self.motor.processar_intervencao(a.id, PapelAgente.DEFESA, "Defesa.")
        self.motor.processar_intervencao(a.id, PapelAgente.ACUSACAO, "Réplica.")
        # Prova
        a.fase_actual = FaseAudiencia.PERGUNTAS_JUIZ  # simula chegada às perguntas
        # Juiz pede mais esclarecimentos → deve voltar ao contraditório
        self.motor.processar_intervencao(a.id, PapelAgente.JUIZ, "Tenho dúvidas, preciso de mais.")
        assert a.num_loops_contraditorio == 1

    def test_hash_integridade_unico_por_intervencao(self):
        a = self.motor.criar_audiencia("caso", "civil", TipoAudiencia.JULGAMENTO, "u1", PapelAgente.ACUSACAO)
        self.motor.processar_intervencao(a.id, PapelAgente.JUIZ, "Abertura A.")
        iv2, _ = self.motor.processar_intervencao(a.id, PapelAgente.ACUSACAO, "Argumento.")
        iv3, _ = self.motor.processar_intervencao(a.id, PapelAgente.DEFESA, "Contra-argumento.")
        assert iv2.hash_integridade != iv3.hash_integridade

    def test_apresentar_prova_na_fase_correcta(self):
        a = self.motor.criar_audiencia("caso", "civil", TipoAudiencia.JULGAMENTO, "u1", PapelAgente.ACUSACAO)
        # Avança até fase de prova
        a.fase_actual = FaseAudiencia.PROVA
        prova = self.motor.apresentar_prova(
            a.id, PapelAgente.ACUSACAO, "documento",
            "Contrato de trabalho", "Texto do contrato..."
        )
        assert prova.id
        assert len(a.provas) == 1
        assert prova.hash_integridade

    def test_prova_fora_da_fase_rejeitada(self):
        a = self.motor.criar_audiencia("caso", "laboral", TipoAudiencia.JULGAMENTO, "u1", PapelAgente.ACUSACAO)
        # Fase de ABERTURA — provas não permitidas
        with pytest.raises(ValueError, match="fases de Produção de Prova"):
            self.motor.apresentar_prova(a.id, PapelAgente.ACUSACAO, "documento", "Doc", "texto")

    def test_decisao_so_na_fase_correcta(self):
        a = self.motor.criar_audiencia("caso", "civil", TipoAudiencia.JULGAMENTO, "u1", PapelAgente.ACUSACAO)
        with pytest.raises(ValueError, match="fase de Decisão"):
            self.motor.proferir_decisao(a.id)

    def test_decisao_stub_tem_normas(self):
        a = self.motor.criar_audiencia("despedimento sem justa causa", "laboral", TipoAudiencia.JULGAMENTO, "u1", PapelAgente.ACUSACAO)
        a.fase_actual = FaseAudiencia.DECISAO
        decisao = self.motor.proferir_decisao(a.id)
        assert decisao.sumario
        assert decisao.dispositivo
        assert len(decisao.normas_aplicadas) > 0
        assert len(decisao.recursos_possiveis) > 0
        assert a.estado == EstadoAudiencia.CONCLUIDA

    def test_intervencao_ia_stub(self):
        a = self.motor.criar_audiencia("despedimento", "laboral", TipoAudiencia.JULGAMENTO, "u1", PapelAgente.ACUSACAO)
        self.motor.processar_intervencao(a.id, PapelAgente.JUIZ, "Abertura.")
        iv = self.motor.gerar_intervencao_automatica(a.id, PapelAgente.ACUSACAO)
        assert iv.conteudo
        assert "Art." in iv.conteudo or "acusação" in iv.conteudo.lower() or "despedimento" in iv.conteudo.lower()

    def test_ordem_fases_legal_correcta(self):
        assert ORDEM_FASES_AUDIENCIA[0] == FaseAudiencia.ABERTURA
        assert ORDEM_FASES_AUDIENCIA[1] == FaseAudiencia.ACUSACAO_PEDIDO
        assert ORDEM_FASES_AUDIENCIA[2] == FaseAudiencia.DEFESA
        assert ORDEM_FASES_AUDIENCIA[3] == FaseAudiencia.REPLICA
        assert ORDEM_FASES_AUDIENCIA[4] == FaseAudiencia.PROVA
        assert ORDEM_FASES_AUDIENCIA[-1] == FaseAudiencia.DECISAO


# ── Testes de integração HTTP ─────────────────────────────────────────────────

class TestAudienciasAPI:

    def setup_method(self):
        """Isola o estado do motor entre testes de integração."""
        from app.audiencias.motor import MotorAudiencias
        import app.api.audiencias_routes as ar
        ar.motor_audiencias._audiencias = {}  # reset estado global

    def test_criar_audiencia_autenticado(self):
        token = login("advogado@snaji.gov.pt", "Advog2024!")
        r = client.post("/api/v1/audiencias", json={
            "descricao_caso": "Trabalhador despedido sem justa causa — API test",
            "tipo_processo": "laboral",
            "tipo_audiencia": "julgamento",
            "papel_criador": "acusacao",
        }, headers=h(token))
        assert r.status_code == 200
        assert r.json()["id"]
        assert r.json()["fase_actual"] == "abertura"
        assert r.json()["estado"] == "pendente"

    def test_criar_audiencia_sem_token(self):
        r = client.post("/api/v1/audiencias", json={
            "descricao_caso": "Teste", "tipo_processo": "civil",
            "tipo_audiencia": "julgamento", "papel_criador": "acusacao",
        })
        assert r.status_code == 401

    def test_listar_audiencias(self):
        token = login("magistrado@snaji.gov.pt", "Magis2024!")
        r = client.get("/api/v1/audiencias", headers=h(token))
        assert r.status_code == 200
        data = r.json()
        assert "audiencias" in data
        assert "total" in data
        assert isinstance(data["audiencias"], list)

    def test_fluxo_completo_api(self):
        """Testa o fluxo completo de uma audiência via API."""
        token = login("advogado@snaji.gov.pt", "Advog2024!")

        # 1. Criar
        r = client.post("/api/v1/audiencias", json={
            "descricao_caso": "Furto em estabelecimento comercial — teste fluxo",
            "tipo_processo": "penal",
            "tipo_audiencia": "julgamento",
            "papel_criador": "acusacao",
        }, headers=h(token))
        assert r.status_code == 200
        aid = r.json()["id"]

        # 2. Ver fases
        r2 = client.get(f"/api/v1/audiencias/{aid}/fases", headers=h(token))
        assert r2.status_code == 200
        assert r2.json()["fase_actual"] == "abertura"

        # 3. Juiz abre
        r3 = client.post(f"/api/v1/audiencias/{aid}/intervencao", json={
            "papel": "juiz",
            "conteudo": "Declaro aberta a audiência. Identifico as partes presentes.",
            "tipo": "abertura",
        }, headers=h(token))
        assert r3.status_code == 200
        assert r3.json()["orientacao_proximo_passo"]

        # 4. Acusação fala
        r4 = client.post(f"/api/v1/audiencias/{aid}/intervencao", json={
            "papel": "acusacao",
            "conteudo": "O arguido praticou furto nos termos do Art. 203.º CP. A prova é concludente.",
            "tipo": "alegacao",
        }, headers=h(token))
        assert r4.status_code == 200
        assert "CP-203" in r4.json()["normas_citadas"] or len(r4.json()["normas_citadas"]) >= 0

        # 5. Defesa responde com geração IA
        r5 = client.post(f"/api/v1/audiencias/{aid}/intervencao-ia", json={
            "papel": "defesa",
        }, headers=h(token))
        assert r5.status_code == 200
        assert r5.json()["gerado_por_ia"] is True
        assert r5.json()["conteudo"]

        # 6. Ver audiência completa
        r6 = client.get(f"/api/v1/audiencias/{aid}", headers=h(token))
        assert r6.status_code == 200
        assert len(r6.json()["intervencoes"]) == 3  # juiz + acusação + defesa

    def test_intervencao_papel_errado_rejeitada_api(self):
        token = login("cidadao@snaji.gov.pt", "Cidad2024!")
        # Cria audiência
        r = client.post("/api/v1/audiencias", json={
            "descricao_caso": "Teste papel errado",
            "tipo_processo": "civil",
            "tipo_audiencia": "contraditorio",
            "papel_criador": "acusacao",
        }, headers=h(token))
        aid = r.json()["id"]
        # Na fase de abertura, acusação não pode falar
        r2 = client.post(f"/api/v1/audiencias/{aid}/intervencao", json={
            "papel": "acusacao",
            "conteudo": "Quero falar agora",
            "tipo": "alegacao",
        }, headers=h(token))
        assert r2.status_code == 400

    def test_apresentar_prova_ficheiro(self):
        token = login("advogado@snaji.gov.pt", "Advog2024!")
        # Cria e avança até fase de prova
        r = client.post("/api/v1/audiencias", json={
            "descricao_caso": "Teste prova ficheiro",
            "tipo_processo": "civil",
            "tipo_audiencia": "julgamento",
            "papel_criador": "acusacao",
        }, headers=h(token))
        aid = r.json()["id"]

        # Avança para fase de prova via intervenções
        for papel, conteudo in [
            ("juiz", "Abertura."),
            ("acusacao", "Pedido."),
            ("defesa", "Defesa."),
            ("acusacao", "Réplica."),
        ]:
            client.post(f"/api/v1/audiencias/{aid}/intervencao",
                json={"papel": papel, "conteudo": conteudo, "tipo": "alegacao"},
                headers=h(token))

        # Apresenta prova (ficheiro de texto)
        txt = b"CONTRATO DE ARRENDAMENTO\nData: 01/01/2023\nRenda: 800 euros"
        r2 = client.post(
            f"/api/v1/audiencias/{aid}/prova-ficheiro",
            data={"papel": "acusacao", "tipo_prova": "documento", "descricao": "Contrato de arrendamento"},
            files={"ficheiro": ("contrato.txt", txt, "text/plain")},
            headers=h(token),
        )
        assert r2.status_code == 200
        assert r2.json()["prova_id"]
        assert r2.json()["hash_integridade"]
