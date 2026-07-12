"""
Motor do Analista — SNAJI (Especificação V8, §8)
=================================================
Agrega o registo analítico anonimizado em indicadores para o perfil
Analista (DGPJ/gestão):

  OBSERVATÓRIO DA CONFLITUALIDADE
    - volumes por área jurídica e evolução temporal (série diária)
    - alertas emitidos por tipo e gravidade (prazos expirados/em risco,
      vias não judiciais, apoio judiciário)

  ZONAS CINZENTAS DA LEI (indicador inédito)
    - casos em que as três lentes interpretativas DIVERGEM ou em que a
      solidez dos cenários é baixa: medida objetiva de incerteza jurídica,
      área a área — informação que nenhuma estatística tradicional dá.

  QUALIDADE E OPERAÇÃO DO SISTEMA
    - taxa de groundedness (citações validadas vs. rejeitadas)
    - utilização de LLM vs. modo determinístico (fallbacks)
    - perguntas médias do Instrutor até classificação estável

  PRIVACIDADE
    - k-anonimato: nenhum indicador é devolvido com contagem inferior a K
      (por omissão, 3) — aparece como "<K" em vez do número real.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

from app.analytics.registo import carregar_eventos

logger = structlog.get_logger(__name__)

K_ANONIMATO = 3


def _k(valor: int, k: int = K_ANONIMATO) -> int | str:
    """Aplica o k-anonimato a uma contagem."""
    return valor if valor == 0 or valor >= k else f"<{k}"


def _k_dict(contagens: dict[str, int], k: int = K_ANONIMATO) -> dict[str, Any]:
    return {chave: _k(v, k) for chave, v in sorted(contagens.items(), key=lambda x: -x[1])}


class MotorAnalista:
    def __init__(self, dias: int = 30, k: int = K_ANONIMATO):
        self.k = k
        limite = datetime.now(timezone.utc) - timedelta(days=dias)
        self.eventos = [
            e for e in carregar_eventos()
            if self._data(e) and self._data(e) >= limite
        ]
        self.dias = dias

    @staticmethod
    def _data(e: dict) -> datetime | None:
        try:
            return datetime.fromisoformat(e.get("ts", ""))
        except ValueError:
            return None

    # ── Observatório da conflitualidade ────────────────────────────────

    def observatorio(self) -> dict:
        instrucoes = [e for e in self.eventos if e["evento"] == "instrucao_concluida"]

        por_area: Counter = Counter()
        alertas_tipo: Counter = Counter()
        alertas_gravidade: Counter = Counter()
        prazos_expirados = 0
        serie: dict[str, int] = defaultdict(int)

        for e in instrucoes:
            for area in e.get("areas", []):
                por_area[area] += 1
            serie[e["ts"][:10]] += 1
            for a in e.get("alertas", []):
                alertas_tipo[a.get("tipo", "?")] += 1
                alertas_gravidade[a.get("gravidade", "?")] += 1
                if a.get("tipo") == "prazo" and a.get("gravidade") == "urgente":
                    prazos_expirados += 1

        return {
            "periodo_dias": self.dias,
            "total_instrucoes": _k(len(instrucoes), self.k),
            "volumes_por_area": _k_dict(por_area, self.k),
            "serie_diaria": {d: _k(v, self.k) for d, v in sorted(serie.items())},
            "alertas_por_tipo": _k_dict(alertas_tipo, self.k),
            "alertas_por_gravidade": _k_dict(alertas_gravidade, self.k),
            "prazos_urgentes_detectados": _k(prazos_expirados, self.k),
            "nota_privacidade": f"Indicadores com menos de {self.k} ocorrências são mascarados (k-anonimato).",
        }

    # ── Governação do sistema ───────────────────────────────────────────

    def utilizacao(self) -> dict:
        """Métricas de utilização do sistema: logins, funcionalidades mais usadas,
        atividade por perfil. Para o analista melhorar o SNAJI e o admin
        acompanhar a adoção. Dados agregados."""
        from collections import Counter
        logins = [e for e in self.eventos if e["evento"] == "login"]
        por_perfil = Counter(e.get("dados", {}).get("role", "?") for e in logins)
        # Funcionalidades usadas (todos os eventos que não são de sistema)
        func = Counter(e["evento"] for e in self.eventos)
        mais_usadas = dict(func.most_common(10))
        return {
            "periodo_dias": self.dias,
            "total_logins": len(logins),
            "logins_por_perfil": dict(por_perfil),
            "funcionalidades_mais_usadas": mais_usadas,
            "total_eventos": len(self.eventos),
        }

    def governacao(self) -> dict:
        """
        Indicadores para governar o sistema e informar política pública:
        funil (abandono), equidade de acesso (papel processual), território,
        prazos salvos vs. perdidos, e artigos de lei mais invocados.
        """
        iniciadas = [e for e in self.eventos if e["evento"] == "instrucao_iniciada"]
        concluidas = [e for e in self.eventos if e["evento"] == "instrucao_concluida"]
        cenarios = [e for e in self.eventos if e["evento"] == "cenarios_gerados"]

        # Funil: quem começa vs. quem conclui (sem viés de sobrevivência)
        taxa_conclusao = (
            round(len(concluidas) / len(iniciadas), 2)
            if len(iniciadas) >= self.k else None
        )

        # Equidade de acesso: quem usa o sistema — quem ataca ou quem se defende?
        por_papel: Counter = Counter(e.get("papel", "desconhecido") for e in concluidas)

        # Território (apenas quando o utilizador o indicou, voluntariamente)
        por_distrito: Counter = Counter(
            e["distrito"] for e in iniciadas if e.get("distrito")
        )

        # Prazos: direitos salvos (em risco, ainda a tempo) vs. chegados tarde
        expirados: Counter = Counter()
        em_risco: Counter = Counter()
        for e in concluidas:
            for a in e.get("alertas", []):
                if a.get("tipo") != "prazo":
                    continue
                norma = a.get("norma", "?")
                if a.get("subtipo") == "expirado":
                    expirados[norma] += 1
                elif a.get("subtipo") == "em_risco":
                    em_risco[norma] += 1

        # Artigos de lei mais invocados nas análises (mapa de atenção legislativa)
        normas: Counter = Counter()
        for e in cenarios:
            for n in e.get("normas_validadas", []):
                normas[n] += 1

        return {
            "periodo_dias": self.dias,
            "funil": {
                "instrucoes_iniciadas": _k(len(iniciadas), self.k),
                "instrucoes_concluidas": _k(len(concluidas), self.k),
                "taxa_de_conclusao": taxa_conclusao,
            },
            "equidade_de_acesso": {
                "por_papel_processual": _k_dict(dict(por_papel), self.k),
                "leitura": "Um sistema justo serve quem reclama E quem se defende; "
                           "esta distribuição mede-o em contínuo.",
            },
            "territorio": {
                "instrucoes_por_distrito": _k_dict(dict(por_distrito), self.k),
                "nota": "Recolha voluntária, categórica e agregada; sem moradas.",
            },
            "prazos": {
                "direitos_em_risco_sinalizados_a_tempo": _k_dict(dict(em_risco), self.k),
                "chegaram_com_prazo_expirado": _k_dict(dict(expirados), self.k),
                "leitura": "A razão expirados/sinalizados, por norma, é evidência "
                           "objetiva para avaliar se as janelas legais (ex.: 60 dias "
                           "do art. 387.º CT) são adequadas.",
            },
            "normas_mais_invocadas": dict(list(_k_dict(dict(normas), self.k).items())[:10]),
        }

    # ── Zonas cinzentas da lei ──────────────────────────────────────────

    def zonas_cinzentas(self) -> dict:
        cenarios = [e for e in self.eventos if e["evento"] == "cenarios_gerados"]
        total = len(cenarios)
        convergentes = sum(1 for e in cenarios if e.get("convergencia"))
        divergentes = total - convergentes
        solidez: Counter = Counter()
        for e in cenarios:
            for s in e.get("solidez", []):
                solidez[s] += 1

        indice = round(divergentes / total, 2) if total else None

        # Aproximação da incerteza por diploma (via normas invocadas nas análises divergentes)
        divergencia_por_diploma: Counter = Counter()
        for e in cenarios:
            if not e.get("convergencia"):
                for n in e.get("normas_validadas", []):
                    divergencia_por_diploma[n.split("-")[0]] += 1

        return {
            "divergencia_por_diploma": _k_dict(dict(divergencia_por_diploma), self.k),
            "periodo_dias": self.dias,
            "total_analises_de_cenarios": _k(total, self.k),
            "casos_convergentes": _k(convergentes, self.k),
            "casos_divergentes": _k(divergentes, self.k),
            "indice_de_incerteza_juridica": indice if total >= self.k else None,
            "distribuicao_de_solidez": _k_dict(solidez, self.k),
            "leitura": (
                "O índice de incerteza jurídica mede a fração de casos em que as três "
                "lentes interpretativas divergem — um sinal objetivo de zonas da lei "
                "onde a orientação é pouco clara e a intervenção legislativa ou "
                "uniformizadora pode ser útil."
            ),
        }

    # ── Qualidade e operação ───────────────────────────────────────────

    def qualidade(self) -> dict:
        instrucoes = [e for e in self.eventos if e["evento"] == "instrucao_concluida"]
        cenarios = [e for e in self.eventos if e["evento"] == "cenarios_gerados"]

        com_llm = sum(1 for e in instrucoes + cenarios if e.get("via_llm"))
        total_llm_base = len(instrucoes) + len(cenarios)

        rejeitadas = sum(e.get("normas_rejeitadas", 0) for e in cenarios)
        analises_limpa = sum(1 for e in cenarios if e.get("normas_rejeitadas", 0) == 0)

        perguntas = [e.get("n_perguntas") for e in instrucoes if e.get("n_perguntas") is not None]
        media_perguntas = round(sum(perguntas) / len(perguntas), 1) if perguntas else None

        return {
            "periodo_dias": self.dias,
            "taxa_utilizacao_llm": (
                round(com_llm / total_llm_base, 2) if total_llm_base >= self.k else None
            ),
            "groundedness": {
                "analises_sem_citacoes_rejeitadas": _k(analises_limpa, self.k),
                "total_citacoes_rejeitadas_pelo_validador": _k(rejeitadas, self.k),
            },
            "perguntas_medias_por_instrucao": (
                media_perguntas if len(perguntas) >= self.k else None
            ),
            "leitura": (
                "Groundedness: quanto mais análises sem citações rejeitadas, mais "
                "fundamentado no corpus está o sistema. A taxa de LLM distingue o "
                "modo pleno do modo determinístico de contingência."
            ),
        }
