"""
Repositório de Casos — SNAJI
=============================
Persistência dos casos instruídos e das suas análises, por utilizador.
Resolve o problema de UX: "criei um caso, mudei de aba, desapareceu".

Cada caso guarda: relato, Ficha de Factos, alertas, áreas, papel e as
análises de cenários que lhe forem sendo anexadas — o histórico completo.

PoC: armazenamento em JSON (backend/app/db/casos.json), thread-safe,
isolado por utilizador (um utilizador nunca vê casos de outro).
Versão institucional: migra para a base de dados relacional — a interface
(guardar/listar/obter/anexar) mantém-se.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)

FICHEIRO_CASOS = Path(__file__).parent / "casos.json"
_lock = threading.Lock()


def _carregar() -> dict:
    if not FICHEIRO_CASOS.exists():
        return {}
    try:
        return json.loads(FICHEIRO_CASOS.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.error("casos.ficheiro_corrompido — a começar vazio")
        return {}


def _gravar(dados: dict) -> None:
    FICHEIRO_CASOS.write_text(
        json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def guardar_caso(user_id: str, dados: dict) -> str:
    """Guarda um caso concluído no Instrutor. Devolve o id do caso."""
    caso_id = dados.get("caso_id") or str(uuid.uuid4())
    relato = dados.get("relato", "")
    titulo = (relato[:70] + "…") if len(relato) > 70 else (relato or "Caso sem descrição")
    with _lock:
        todos = _carregar()
        todos.setdefault(str(user_id), {})[caso_id] = {
            "caso_id": caso_id,
            "titulo": titulo,
            "criado_em": datetime.now(timezone.utc).isoformat(),
            "areas": dados.get("areas", []),
            "papel": dados.get("papel", ""),
            "numero_processo": dados.get("numero_processo", ""),
            "relato": relato,
            "ficha": dados.get("ficha", {}),
            "alertas": dados.get("alertas", []),
            "texto_para_analise": dados.get("texto_para_analise", ""),
            "analises_cenarios": [],
            "analises_juridicas": [],
        }
        _gravar(todos)
    logger.info("caso.guardado", caso_id=caso_id)
    return caso_id


def listar_casos(user_id: str) -> list[dict]:
    """Lista os casos do utilizador (resumo), do mais recente para o mais antigo."""
    todos = _carregar().get(str(user_id), {})
    resumo = [
        {
            "caso_id": c["caso_id"],
            "titulo": c["titulo"],
            "criado_em": c["criado_em"],
            "areas": c.get("areas", []),
            "papel": c.get("papel", ""),
            "numero_processo": c.get("numero_processo", ""),
            "n_alertas": len(c.get("alertas", [])),
            "n_analises": len(c.get("analises_cenarios", [])),
        }
        for c in todos.values()
    ]
    return sorted(resumo, key=lambda c: c["criado_em"], reverse=True)


def obter_caso(user_id: str, caso_id: str,
               partilhado: bool = False) -> Optional[dict]:
    """
    Devolve o caso completo.

    Por omissão, apenas se pertencer ao utilizador: os casos que um cidadão
    guarda são pessoais e assim se mantêm.

    Com `partilhado`, procura em todos os utilizadores. Serve os casos
    ligados a processos: um processo em carteira não é pessoal — é do
    serviço, e as análises pertencem ao processo, não a quem as gerou. Num
    processo judicial as peças estão no processo, não na gaveta de quem as
    escreveu.
    """
    todos = _carregar()
    proprio = todos.get(str(user_id), {}).get(caso_id)
    if proprio is not None or not partilhado:
        return proprio
    for uid, casos in todos.items():
        if caso_id in casos:
            return casos[caso_id]
    return None


def dono_do_caso(caso_id: str) -> Optional[str]:
    """Identificador do utilizador a quem o caso pertence."""
    for uid, casos in _carregar().items():
        if caso_id in casos:
            return uid
    return None


def _essencia(d: dict) -> str:
    """
    Representação estável de uma análise, ignorando campos voláteis — serve
    para detetar repetições exatas (idempotência).

    A perspetiva entra sempre na comparação, ainda que o conteúdo saia igual:
    a análise própria e a do contraditório são duas peças distintas do
    processo, e guardar apenas uma delas faria desaparecer do histórico
    justamente o lado que se quis ver.
    """
    limpo = {k: v for k, v in d.items()
             if k not in ("analisado_em", "percurso", "caso_id", "timestamp", "audit")}
    limpo["_perspetiva"] = d.get("perspetiva", "propria")
    return json.dumps(limpo, ensure_ascii=False, sort_keys=True)


def _anexar(user_id: str, caso_id: str, campo: str, resultado: dict, evento: str) -> bool:
    """Anexa uma análise ao histórico do caso. Idempotente: se for exatamente
    igual à última guardada, não acumula duplicados (repetir não é criar)."""
    with _lock:
        todos = _carregar()
        caso = todos.get(str(user_id), {}).get(caso_id)
        if not caso:
            return False
        lista = caso.setdefault(campo, [])
        resultado = dict(resultado)
        resultado.pop("percurso", None)  # o percurso pede-se de novo quando se quer
        if lista and _essencia(lista[-1]) == _essencia(resultado):
            logger.info(f"caso.{evento}_repetida_ignorada", caso_id=caso_id)
            return True
        resultado["analisado_em"] = datetime.now(timezone.utc).isoformat()
        # A primeira análise de um caso fica automaticamente activa: sem isso,
        # um caso com uma única análise apareceria sem apreciação corrente.
        # As seguintes entram em apreciação, para não substituírem em silêncio
        # a leitura em que o processo se apoia.
        resultado["activa"] = not any(a.get("activa") for a in lista)
        lista.append(resultado)
        _gravar(todos)
    logger.info(f"caso.{evento}_anexada", caso_id=caso_id)
    return True


# Motivos de descarte oferecidos ao utilizador. A lista é curta de propósito:
# um campo livre produz registos incomparáveis entre si.
MOTIVOS_DESCARTE = {
    "falhada": "Análise falhada ou incompleta",
    "texto_errado": "Erro no texto do caso submetido",
    "factos_novos": "Chegaram factos novos ao processo",
    "ensaio": "Ensaio ou teste",
    "outro": "Outro motivo",
}


def definir_definitiva(user_id: str, caso_id: str, indice: int,
                       campo: str = "analises_cenarios") -> bool:
    """
    Fixa uma análise como a apreciação definitiva do processo.

    A partir daqui não pode ser descartada. É o equivalente a proferir: uma
    decisão que entra no processo não se retira — anula-se ou recorre-se dela,
    mas o registo permanece. Quem fixa assume a leitura; as restantes
    continuam disponíveis para consulta e comparação.

    Só uma análise pode ser definitiva, e passa a ser também a activa.
    """
    with _lock:
        todos = _carregar()
        caso = todos.get(str(user_id), {}).get(caso_id) or _procurar(todos, caso_id)
        if not caso:
            return False
        lista = caso.get(campo, [])
        if not (0 <= indice < len(lista)):
            return False
        for i, a in enumerate(lista):
            a["definitiva"] = (i == indice)
            a["activa"] = (i == indice)
        lista[indice]["definitiva_em"] = datetime.now(timezone.utc).isoformat()
        lista[indice]["definitiva_por"] = str(user_id)
        _gravar(todos)
    logger.info("caso.analise_definitiva", caso_id=caso_id, indice=indice)
    return True


def _procurar(todos: dict, caso_id: str) -> Optional[dict]:
    """Localiza um caso em qualquer utilizador (casos de processo)."""
    for casos in todos.values():
        if caso_id in casos:
            return casos[caso_id]
    return None


def descartar_analise(user_id: str, caso_id: str, indice: int,
                      motivo: str = "outro", nota: str = "",
                      campo: str = "analises_cenarios") -> bool:
    """
    Retira uma análise da vista principal, guardando-a no arquivo do caso.

    Não destrói: uma análise descartada continua no processo, com a data do
    descarte e o motivo. Num sistema de justiça o rasto documental é o que
    permite auditar uma decisão a posteriori — saber o que foi analisado,
    quando, e o que foi posto de lado. Uma peça anulada não desaparece de um
    processo judicial; fica assinalada como anulada.
    """
    with _lock:
        todos = _carregar()
        caso = todos.get(str(user_id), {}).get(caso_id)
        if not caso:
            return False
        lista = caso.get(campo, [])
        if not (0 <= indice < len(lista)):
            return False
        if lista[indice].get("definitiva"):
            logger.info("caso.descarte_recusado_definitiva",
                        caso_id=caso_id, indice=indice)
            return False
        analise = lista.pop(indice)
        analise["descartada_em"] = datetime.now(timezone.utc).isoformat()
        analise["descarte_motivo"] = motivo if motivo in MOTIVOS_DESCARTE else "outro"
        if nota:
            analise["descarte_nota"] = nota[:400]
        caso.setdefault(f"{campo}_descartadas", []).append(analise)
        _gravar(todos)
    logger.info("caso.analise_descartada",
                caso_id=caso_id, indice=indice, motivo=motivo, campo=campo)
    return True


def descartar_todas(user_id: str, caso_id: str, motivo: str = "outro",
                    nota: str = "", campo: str = "analises_cenarios") -> int:
    """Descarta todas as análises de um caso. Devolve quantas foram arquivadas."""
    with _lock:
        todos = _carregar()
        caso = todos.get(str(user_id), {}).get(caso_id)
        if not caso:
            return 0
        lista = caso.get(campo, [])
        # A definitiva não é descartada: fica no processo.
        manter = [a for a in lista if a.get("definitiva")]
        lista = [a for a in lista if not a.get("definitiva")]
        n = len(lista)
        agora = datetime.now(timezone.utc).isoformat()
        for a in lista:
            a["descartada_em"] = agora
            a["descarte_motivo"] = motivo if motivo in MOTIVOS_DESCARTE else "outro"
            if nota:
                a["descarte_nota"] = nota[:400]
        caso.setdefault(f"{campo}_descartadas", []).extend(lista)
        caso[campo] = manter
        _gravar(todos)
    logger.info("caso.analises_descartadas",
                caso_id=caso_id, descartadas=n, motivo=motivo, campo=campo)
    return n


def activar_analise(user_id: str, caso_id: str, indice: int,
                    campo: str = "analises_cenarios") -> bool:
    """
    Marca uma análise como a activa do caso; as restantes ficam em apreciação.

    Um caso pode ter várias leituras — refeitas, do contraditório, com factos
    novos — mas apenas uma vale como apreciação corrente do processo. As
    outras não desaparecem: ficam disponíveis para comparação, que é o que
    permite ver como a apreciação evoluiu.
    """
    with _lock:
        todos = _carregar()
        caso = todos.get(str(user_id), {}).get(caso_id)
        if not caso:
            return False
        lista = caso.get(campo, [])
        if not (0 <= indice < len(lista)):
            return False
        for i, a in enumerate(lista):
            a["activa"] = (i == indice)
        _gravar(todos)
    logger.info("caso.analise_activada", caso_id=caso_id, indice=indice)
    return True


def restaurar_analise(user_id: str, caso_id: str, indice: int,
                      campo: str = "analises_cenarios") -> bool:
    """Traz uma análise do arquivo de volta à lista activa."""
    with _lock:
        todos = _carregar()
        caso = todos.get(str(user_id), {}).get(caso_id)
        if not caso:
            return False
        arquivo = caso.get(f"{campo}_descartadas", [])
        if not (0 <= indice < len(arquivo)):
            return False
        a = arquivo.pop(indice)
        for k in ("descartada_em", "descarte_motivo", "descarte_nota"):
            a.pop(k, None)
        a["activa"] = False
        caso.setdefault(campo, []).append(a)
        _gravar(todos)
    logger.info("caso.analise_restaurada", caso_id=caso_id, indice=indice)
    return True


def estatisticas_descarte(user_id: str | None = None) -> dict:
    """
    Contagem de análises activas e descartadas, por caso.

    Devolve factos, não juízos: quantas análises um caso teve e quantas foram
    postas de lado, com os motivos declarados. Refazer uma análise tem
    explicações legítimas — texto corrigido, factos novos, ver o contraditório
    — e cabe a quem tem contexto interpretar, não ao sistema presumir
    intenção.
    """
    with _lock:
        todos = _carregar()
    utilizadores = [str(user_id)] if user_id else list(todos.keys())
    casos: list[dict] = []
    motivos: dict[str, int] = {}
    for uid in utilizadores:
        for cid, c in todos.get(uid, {}).items():
            activas = len(c.get("analises_cenarios", []))
            descartadas = c.get("analises_cenarios_descartadas", [])
            for d in descartadas:
                m = d.get("descarte_motivo", "outro")
                motivos[m] = motivos.get(m, 0) + 1
            if activas or descartadas:
                casos.append({
                    "caso_id": cid,
                    "titulo": c.get("titulo", ""),
                    "numero_processo": c.get("numero_processo", ""),
                    "analises_activas": activas,
                    "analises_descartadas": len(descartadas),
                    "total": activas + len(descartadas),
                })
    casos.sort(key=lambda x: x["total"], reverse=True)
    return {
        "casos": casos,
        "motivos_descarte": motivos,
        "total_casos": len(casos),
        "total_analises": sum(c["total"] for c in casos),
        "total_descartadas": sum(c["analises_descartadas"] for c in casos),
    }


def anexar_cenarios(user_id: str, caso_id: str, resultado: dict) -> bool:
    """Anexa uma análise de cenários ao histórico do caso (idempotente)."""
    return _anexar(user_id, caso_id, "analises_cenarios", resultado, "cenarios")


def anexar_analise_juridica(user_id: str, caso_id: str, resultado: dict) -> bool:
    """Anexa uma análise jurídica (pipeline) ao histórico do caso (idempotente)."""
    return _anexar(user_id, caso_id, "analises_juridicas", resultado, "analise_juridica")
