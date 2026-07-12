"""
Rotas das Audiências do SNAJI — Fase 3.

API completa para gestão de audiências judiciais:

POST /audiencias                           → criar audiência
GET  /audiencias                           → listar audiências do utilizador
GET  /audiencias/{id}                      → detalhe completo
POST /audiencias/{id}/intervencao          → submeter intervenção (humana)
POST /audiencias/{id}/intervencao-ia       → gerar intervenção automática (IA)
POST /audiencias/{id}/prova                → apresentar prova
POST /audiencias/{id}/decidir              → juiz profere decisão
GET  /audiencias/{id}/fases                → estado das fases e quem deve falar
POST /audiencias/{id}/avancar-fase         → juiz avança para próxima fase
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
import structlog

from app.security.dependencias import requer_login, requer_permissao
from app.db import config_repo
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from app.security.rbac import Permissao
from app.db.utilizadores import Utilizador
from app.audiencias.motor import (
    motor_audiencias, FaseAudiencia, ORDEM_FASES_AUDIENCIA,
    DESCRICAO_FASES, PAPEIS_POR_FASE
)
from app.audiencias.modelos import (
    TipoAudiencia, PapelAgente, TipoIntervencao, EstadoAudiencia
)
from app.documents.processador import ProcessadorDocumentos

router = APIRouter(prefix="/audiencias", tags=["Audiências — Fase 3"])
logger = structlog.get_logger(__name__)
_doc_processor = ProcessadorDocumentos()


# ── Schemas ──────────────────────────────────────────────────────────────────

class CriarAudienciaRequest(BaseModel):
    descricao_caso: str
    tipo_processo: str                    # laboral | penal | civil | etc.
    tipo_audiencia: TipoAudiencia = TipoAudiencia.JULGAMENTO
    papel_criador: PapelAgente            # qual o papel de quem cria
    processo_id: Optional[str] = None
    com_perito: bool = False
    max_loops_contraditorio: int = 3      # quantas rondas o juiz pode pedir
    # V2: caso misto — ex.: ["penal", "civil"] ativa o regime de adesão (art. 71.º CPP)
    areas: Optional[list[str]] = None
    com_interprete: bool = False


class IntervencaoRequest(BaseModel):
    papel: PapelAgente
    conteudo: str
    tipo: TipoIntervencao = TipoIntervencao.ALEGACAO


class IntervencaoIARequest(BaseModel):
    papel: PapelAgente


class ProvaTextoRequest(BaseModel):
    papel: PapelAgente
    tipo_prova: str   # documento | pericia | testemunho | video | imagem
    descricao: str
    conteudo_texto: str


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("")
async def criar_audiencia(
    dados: CriarAudienciaRequest,
    utilizador: Utilizador = Depends(requer_permissao(Permissao.FERRAMENTAS_PROFISSIONAIS)),
):
    """
    Cria uma nova audiência.
    Qualquer utilizador autenticado pode criar — vítima, arguido, advogado, etc.
    O papel_criador define a posição processual de quem cria.
    """
    a = motor_audiencias.criar_audiencia(
        descricao_caso=dados.descricao_caso,
        tipo_processo=dados.tipo_processo,
        tipo_audiencia=dados.tipo_audiencia,
        areas=dados.areas,
        com_interprete=dados.com_interprete,
        criado_por=utilizador.id,
        papel_criador=dados.papel_criador,
        processo_id=dados.processo_id,
        com_perito=dados.com_perito,
        max_loops=dados.max_loops_contraditorio,
    )
    logger.info("audiencia.criada.api", id=a.id, user=utilizador.id, papel=dados.papel_criador.value)
    return _serializar_audiencia(a)


@router.get("")
async def listar_audiencias(utilizador: Utilizador = Depends(requer_login)):
    """Lista todas as audiências criadas pelo utilizador."""
    audiencias = motor_audiencias.listar_audiencias(criado_por=utilizador.id)
    return {
        "audiencias": [_serializar_resumo(a) for a in audiencias],
        "total": len(audiencias),
    }


@router.get("/{aid}")
async def ver_audiencia(aid: str, utilizador: Utilizador = Depends(requer_login)):
    """Detalhe completo de uma audiência com todas as intervenções e provas."""
    try:
        a = motor_audiencias.obter_audiencia(aid)
        return _serializar_audiencia(a)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{aid}/fases")
async def estado_fases(aid: str, utilizador: Utilizador = Depends(requer_login)):
    """
    Mostra o estado actual das fases, quem deve falar a seguir,
    e o que acontecerá em cada fase futura.
    """
    try:
        a = motor_audiencias.obter_audiencia(aid)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    fases = []
    idx_actual = ORDEM_FASES_AUDIENCIA.index(a.fase_actual) if a.fase_actual in ORDEM_FASES_AUDIENCIA else -1

    for i, fase in enumerate(ORDEM_FASES_AUDIENCIA):
        papeis = [p.value for p in PAPEIS_POR_FASE.get(fase, [])]
        fases.append({
            "fase": fase.value,
            "descricao": DESCRICAO_FASES.get(fase, ""),
            "papeis_permitidos": papeis,
            "estado": "concluida" if i < idx_actual else "actual" if i == idx_actual else "futura",
        })

    return {
        "audiencia_id": aid,
        "fase_actual": a.fase_actual.value,
        "estado_audiencia": a.estado.value,
        "aguarda_intervencao_de": a.aguarda_intervencao_de.value if a.aguarda_intervencao_de else None,
        "loops_contraditorio": f"{a.num_loops_contraditorio}/{a.max_loops_contraditorio}",
        "fases": fases,
    }


@router.post("/{aid}/intervencao")
async def submeter_intervencao(
    aid: str,
    dados: IntervencaoRequest,
    utilizador: Utilizador = Depends(requer_login),
):
    """
    Submete uma intervenção humana numa audiência.
    O conteúdo é escrito pelo utilizador — não gerado por IA.
    """
    try:
        iv, orientacao = motor_audiencias.processar_intervencao(
            audiencia_id=aid,
            papel=dados.papel,
            conteudo=dados.conteudo,
            tipo=dados.tipo,
        )
        return {
            "intervencao_id": iv.id,
            "papel": iv.papel.value,
            "tipo": iv.tipo.value,
            "normas_citadas": iv.normas_citadas,
            "hash_integridade": iv.hash_integridade,
            "timestamp": iv.timestamp.isoformat(),
            "orientacao_proximo_passo": orientacao,
            "papel_sugerido": motor_audiencias.papel_sugerido(
                motor_audiencias.obter_audiencia(aid)),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{aid}/intervencao-ia")
async def gerar_intervencao_ia(
    aid: str,
    dados: IntervencaoIARequest,
    utilizador: Utilizador = Depends(requer_login),
):
    """
    Gera automaticamente uma intervenção para um papel usando IA.
    Útil para simular a parte contrária ou treinar.
    """
    try:
        iv = motor_audiencias.gerar_intervencao_automatica(aid, dados.papel)
        return {
            "intervencao_id": iv.id,
            "papel": iv.papel.value,
            "conteudo": iv.conteudo,
            "normas_citadas": iv.normas_citadas,
            "hash_integridade": iv.hash_integridade,
            "gerado_por_ia": True,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{aid}/prova-texto")
async def apresentar_prova_texto(
    aid: str,
    dados: ProvaTextoRequest,
    utilizador: Utilizador = Depends(requer_login),
):
    """Apresenta uma prova em formato texto (testemunho, descrição, etc.)."""
    try:
        prova = motor_audiencias.apresentar_prova(
            audiencia_id=aid,
            papel=dados.papel,
            tipo_prova=dados.tipo_prova,
            descricao=dados.descricao,
            conteudo_texto=dados.conteudo_texto,
        )
        return {
            "prova_id": prova.id,
            "tipo": prova.tipo,
            "hash_integridade": prova.hash_integridade,
            "timestamp": prova.timestamp.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{aid}/prova-ficheiro")
async def apresentar_prova_ficheiro(
    aid: str,
    papel: str = Form(...),
    tipo_prova: str = Form(...),
    descricao: str = Form(...),
    ficheiro: UploadFile = File(...),
    utilizador: Utilizador = Depends(requer_login),
):
    """
    Apresenta uma prova como ficheiro (PDF, imagem, vídeo descrito em texto).
    O sistema extrai o texto do ficheiro para análise jurídica.
    """
    try:
        papel_enum = PapelAgente(papel)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Papel inválido: {papel}")

    conteudo = await ficheiro.read()
    doc = _doc_processor.processar(ficheiro.filename or "ficheiro", conteudo)

    texto_prova = doc.texto if doc.texto else f"[Ficheiro: {ficheiro.filename} — {doc.num_paginas} página(s)]"
    if doc.avisos:
        texto_prova += f"\n[Avisos: {'; '.join(doc.avisos)}]"

    try:
        prova = motor_audiencias.apresentar_prova(
            audiencia_id=aid,
            papel=papel_enum,
            tipo_prova=tipo_prova,
            descricao=descricao,
            conteudo_texto=texto_prova,
            nome_ficheiro=ficheiro.filename,
        )
        return {
            "prova_id": prova.id,
            "tipo": prova.tipo,
            "nome_ficheiro": prova.nome_ficheiro,
            "caracteres_extraidos": len(doc.texto),
            "avisos": doc.avisos,
            "hash_integridade": prova.hash_integridade,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{aid}/decidir")
async def proferir_decisao(aid: str, utilizador: Utilizador = Depends(requer_login)):
    """
    O juiz profere a decisão final.
    Só possível na fase de Decisão, após todas as partes terem falado.
    """
    try:
        decisao = motor_audiencias.proferir_decisao(aid)
        return {
            "sumario": decisao.sumario,
            "fundamentacao": decisao.fundamentacao,
            "normas_aplicadas": decisao.normas_aplicadas,
            "dispositivo": decisao.dispositivo,
            "recursos_possiveis": decisao.recursos_possiveis,
            "timestamp": decisao.timestamp.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Ata da sessão (escrivão): consultar e exportar ───────────────────────────

def _linha_contactos() -> str:
    try:
        c = config_repo.obter_config()
        partes = [c.get("email_suporte"), c.get("telefone_suporte"), c.get("horario")]
        partes = [p for p in partes if p]
        return ("Apoio: " + " · ".join(partes)) if partes else ""
    except Exception:
        return ""


def _ata_markdown(d: dict) -> str:
    """Compõe a ata em Markdown — legível, copiável, imprimível."""
    L = []
    L.append(f"# {d['titulo']}")
    L.append("")
    L.append(f"**{d['tribunal']}**  ")
    L.append(f"Audiência de {d['tipo_audiencia']} — {d['data_por_extenso']}  ")
    L.append(f"Áreas: {', '.join(d['areas'])} · Regime: {d['regime']}  ")
    if d.get("processo_id"):
        L.append(f"Processo: {d['processo_id']}  ")
    L.append("")
    L.append(f"**Objeto:** {d['caso']}")
    L.append("")
    L.append("## Participantes")
    for p in d["participantes"]:
        L.append(f"- **{p['papel']}**: {p['nome']}")
    L.append("")
    L.append("## Termos da audiência (todos os atos)")
    for s in d["passos"]:
        marca = " 🔏 *[ata]*" if s["e_ata"] else ""
        hora = f" ({s['hora']})" if s["hora"] else ""
        L.append(f"{s['n']}. **{s['papel']}**{hora}{marca}: {s['conteudo']}")
    L.append("")
    if d["provas"]:
        L.append("## Prova produzida")
        for pv in d["provas"]:
            L.append(f"- [{pv['tipo']}] {pv['descricao']} — apresentada por {pv['papel']} (hash {pv['hash']})")
        L.append("")
    if d.get("decisao"):
        L.append("## Decisão")
        L.append(str(d["decisao"]))
        L.append("")
    L.append("---")
    estado = "✔ íntegra" if d["integridade_verificada"] else "✘ SELO QUEBRADO"
    L.append(f"**Integridade da cadeia de atas:** {estado} · Selo: `{d['selo']}` · "
             f"{d['total_atos']} atos, {d['total_atas']} atas")
    L.append("")
    L.append(f"_{d['rodape']}_")
    L.append("")
    L.append("**SNAJI — Serviço Nacional de Assistência Jurídica Inteligente**")
    if _linha_contactos():
        L.append(_linha_contactos())
    return "\n".join(L)


def _ata_txt(d: dict) -> str:
    """Ata em texto simples (.txt) — sem marcação, para arquivo universal."""
    L = []
    sep = "=" * 66
    L.append(sep)
    L.append(d["titulo"].center(66))
    L.append(sep)
    L.append(d["tribunal"])
    L.append(f"Audiencia de {d['tipo_audiencia']} — {d['data_por_extenso']}")
    L.append(f"Areas: {', '.join(d['areas'])} · Regime: {d['regime']}")
    if d.get("processo_id"):
        L.append(f"Processo: {d['processo_id']}")
    L.append("")
    L.append(f"OBJETO: {d['caso']}")
    L.append("")
    L.append("PARTICIPANTES")
    L.append("-" * 66)
    for p in d["participantes"]:
        L.append(f"  {p['papel'].upper():16s} {p['nome']}")
    L.append("")
    L.append("TERMOS DA AUDIENCIA (todos os atos)")
    L.append("-" * 66)
    for s in d["passos"]:
        marca = "  [ATA]" if s["e_ata"] else ""
        hora = f" {s['hora']}" if s["hora"] else ""
        L.append(f"{s['n']:>3}.{hora} {s['papel'].upper()}{marca}")
        for linha in _wrap(s["conteudo"], 62):
            L.append(f"     {linha}")
    L.append("")
    if d["provas"]:
        L.append("PROVA PRODUZIDA")
        L.append("-" * 66)
        for pv in d["provas"]:
            L.append(f"  [{pv['tipo']}] {pv['descricao']} — {pv['papel']} (hash {pv['hash']})")
        L.append("")
    if d.get("decisao"):
        L.append("DECISAO")
        L.append("-" * 66)
        for linha in _wrap(str(d["decisao"]), 62):
            L.append(f"  {linha}")
        L.append("")
    L.append(sep)
    estado = "INTEGRA" if d["integridade_verificada"] else "*** SELO QUEBRADO ***"
    L.append(f"Integridade da cadeia de atas: {estado}")
    L.append(f"Selo: {d['selo']} · {d['total_atos']} atos · {d['total_atas']} atas")
    L.append("")
    for linha in _wrap(d["rodape"], 66):
        L.append(linha)
    L.append("")
    L.append("SNAJI — Serviço Nacional de Assistência Jurídica Inteligente")
    if _linha_contactos():
        L.append(_linha_contactos())
    return "\n".join(L)


def _wrap(texto: str, larg: int) -> list[str]:
    """Quebra texto em linhas de largura fixa, sem cortar palavras."""
    palavras = str(texto).split()
    linhas, atual = [], ""
    for p in palavras:
        if len(atual) + len(p) + 1 > larg:
            linhas.append(atual); atual = p
        else:
            atual = f"{atual} {p}".strip()
    if atual:
        linhas.append(atual)
    return linhas or [""]


def _ata_html(d: dict) -> str:
    """Ata em HTML autossuficiente, com botão de impressão do navegador."""
    linhas = []
    for s in d["passos"]:
        cor = "#f5ead1" if s["e_ata"] else "transparent"
        marca = " <span style='color:#7a5c07'>🔏 ata</span>" if s["e_ata"] else ""
        hora = f"<span style='color:#888'> {s['hora']}</span>" if s["hora"] else ""
        linhas.append(
            f"<li style='background:{cor};padding:6px 8px;margin:3px 0;border-radius:4px'>"
            f"<strong>{s['papel']}</strong>{hora}{marca}<br>{s['conteudo']}</li>")
    parts = "".join(f"<li><strong>{p['papel']}</strong>: {p['nome']}</li>" for p in d["participantes"])
    provas = ""
    if d["provas"]:
        pv = "".join(f"<li>[{x['tipo']}] {x['descricao']} — {x['papel']} "
                     f"<code>{x['hash']}</code></li>" for x in d["provas"])
        provas = f"<h2>Prova produzida</h2><ul>{pv}</ul>"
    decisao = f"<h2>Decisão</h2><p>{d['decisao']}</p>" if d.get("decisao") else ""
    estado = "✔ íntegra" if d["integridade_verificada"] else "✘ SELO QUEBRADO"
    cor_selo = "#1a7a3a" if d["integridade_verificada"] else "#8a1d1d"
    return f"""<!DOCTYPE html><html lang="pt"><head><meta charset="utf-8">
<title>{d['titulo']} — {d['data_por_extenso']}</title>
<style>
  body {{ font-family: Georgia, 'Times New Roman', serif; max-width: 800px;
         margin: 32px auto; padding: 0 24px; color: #1a1a1a; line-height: 1.6; }}
  h1 {{ font-size: 24px; border-bottom: 2px solid #0a2342; padding-bottom: 8px; }}
  h2 {{ font-size: 17px; color: #0a2342; margin-top: 24px; }}
  ul {{ list-style: none; padding-left: 0; }}
  .cab {{ color: #444; font-size: 14px; }}
  .selo {{ margin-top: 24px; padding: 12px; border: 1px solid {cor_selo};
           border-radius: 6px; color: {cor_selo}; font-size: 13px; }}
  .rodape {{ color: #777; font-size: 12px; margin-top: 16px; font-style: italic; }}
  @media print {{ .noprint {{ display: none; }} body {{ margin: 0; }} }}
</style></head><body>
<button class="noprint" onclick="window.print()" style="float:right;padding:8px 16px;
  background:#0a2342;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:14px">
  🖨 Imprimir / Guardar PDF</button>
<h1>{d['titulo']}</h1>
<p class="cab"><strong>{d['tribunal']}</strong><br>
Audiência de {d['tipo_audiencia']} — {d['data_por_extenso']}<br>
Áreas: {', '.join(d['areas'])} · Regime: {d['regime']}</p>
<p><strong>Objeto:</strong> {d['caso']}</p>
<h2>Participantes</h2><ul>{parts}</ul>
<h2>Termos da audiência (todos os atos)</h2><ol>{''.join(linhas)}</ol>
{provas}{decisao}
<div class="selo"><strong>Integridade da cadeia de atas:</strong> {estado}<br>
Selo: <code>{d['selo']}</code> · {d['total_atos']} atos · {d['total_atas']} atas</div>
<p class="rodape">{d['rodape']}<br><strong>SNAJI — Serviço Nacional de Assistência Jurídica Inteligente</strong><br>{_linha_contactos()}</p>
</body></html>"""


@router.get("/{aid}/ata")
async def obter_ata(aid: str, utilizador: Utilizador = Depends(requer_login)) -> dict:
    """Ata consolidada da sessão (dados estruturados)."""
    try:
        a = motor_audiencias.obter_audiencia(aid)
        return motor_audiencias.ata_consolidada(a)
    except (ValueError, KeyError):
        raise HTTPException(status_code=404, detail="Audiência não encontrada")


@router.get("/{aid}/ata.md", response_class=PlainTextResponse)
async def ata_markdown(aid: str, utilizador: Utilizador = Depends(requer_login)):
    """Ata em Markdown (copiar/arquivar)."""
    try:
        a = motor_audiencias.obter_audiencia(aid)
        return _ata_markdown(motor_audiencias.ata_consolidada(a))
    except (ValueError, KeyError):
        raise HTTPException(status_code=404, detail="Audiência não encontrada")


@router.get("/{aid}/ata.txt", response_class=PlainTextResponse)
async def ata_txt(aid: str, utilizador: Utilizador = Depends(requer_login)):
    """Ata em texto simples (.txt) — arquivo universal, sem marcação."""
    try:
        a = motor_audiencias.obter_audiencia(aid)
        return _ata_txt(motor_audiencias.ata_consolidada(a))
    except (ValueError, KeyError):
        raise HTTPException(status_code=404, detail="Audiência não encontrada")


@router.get("/{aid}/ata.html", response_class=HTMLResponse)
async def ata_html(aid: str, utilizador: Utilizador = Depends(requer_login)):
    """Ata em HTML (imprimir/guardar PDF pelo navegador)."""
    try:
        a = motor_audiencias.obter_audiencia(aid)
        return _ata_html(motor_audiencias.ata_consolidada(a))
    except (ValueError, KeyError):
        raise HTTPException(status_code=404, detail="Audiência não encontrada")


# ── Serialização ─────────────────────────────────────────────────────────────

def _serializar_audiencia(a) -> dict:
    return {
        "id": a.id,
        "processo_id": a.processo_id,
        "tipo": a.tipo.value,
        "tipo_processo": a.tipo_processo,
        "areas": a.areas,
        "regime": a.regime,
        "papel_sugerido": motor_audiencias.papel_sugerido(a),
        "descricao_caso": a.descricao_caso,
        "estado": a.estado.value,
        "fase_actual": a.fase_actual.value,
        "fase_descricao": DESCRICAO_FASES.get(a.fase_actual, ""),
        "papel_criador": a.papel_criador.value,
        "aguarda_intervencao_de": a.aguarda_intervencao_de.value if a.aguarda_intervencao_de else None,
        "loops_contraditorio": a.num_loops_contraditorio,
        "max_loops": a.max_loops_contraditorio,
        "criada_em": a.criada_em.isoformat(),
        "participantes": [
            {"papel": p.papel.value, "nome": p.nome, "activo": p.activo}
            for p in a.participantes
        ],
        "intervencoes": [
            {
                "id": iv.id,
                "ronda": iv.ronda,
                "papel": iv.papel.value,
                "tipo": iv.tipo.value,
                "conteudo": iv.conteudo,
                "normas_citadas": iv.normas_citadas,
                "timestamp": iv.timestamp.isoformat(),
                "hash_integridade": iv.hash_integridade,
            }
            for iv in a.intervencoes
        ],
        "provas": [
            {
                "id": pr.id,
                "apresentada_por": pr.apresentada_por.value,
                "tipo": pr.tipo,
                "descricao": pr.descricao,
                "nome_ficheiro": pr.nome_ficheiro,
                "timestamp": pr.timestamp.isoformat(),
                "hash_integridade": pr.hash_integridade,
            }
            for pr in a.provas
        ],
        "decisao": {
            "sumario": a.decisao.sumario,
            "fundamentacao": a.decisao.fundamentacao,
            "normas_aplicadas": a.decisao.normas_aplicadas,
            "dispositivo": a.decisao.dispositivo,
            "recursos_possiveis": a.decisao.recursos_possiveis,
        } if a.decisao else None,
    }


def _serializar_resumo(a) -> dict:
    return {
        "id": a.id,
        "tipo": a.tipo.value,
        "tipo_processo": a.tipo_processo,
        "descricao_caso": a.descricao_caso[:100],
        "estado": a.estado.value,
        "fase_actual": a.fase_actual.value,
        "num_intervencoes": len(a.intervencoes),
        "num_provas": len(a.provas),
        "criada_em": a.criada_em.isoformat(),
        "tem_decisao": a.decisao is not None,
    }
