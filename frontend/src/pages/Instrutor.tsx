/**
 * Página do Agente Instrutor — SNAJI (Especificação V8, §1)
 *
 * O cidadão descreve o caso; o Instrutor faz perguntas estruturadas
 * (escolha / texto / data / valor) até compreender o caso, emitindo
 * alertas de prazos, vias não judiciais e apoio judiciário.
 * No fim, a Ficha de Factos pode ser enviada diretamente para a
 * análise jurídica (/analysis).
 *
 * Autossuficiente: usa o cliente `api` existente; não altera services/api.ts.
 */

import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, juridicalService, tratarErroAPI } from '../services/api'
import { useAuthStore } from '../auth/session'
import type { AnalysisResponse } from '../types'

// ── Tipos da API do Instrutor ────────────────────────────────────────────────

interface AlertaAPI {
  tipo: 'prazo' | 'via_nao_judicial' | 'apoio_judiciario'
  gravidade: 'informativo' | 'atencao' | 'urgente'
  mensagem_tecnica: string
  mensagem_cidada: string
  norma_base: string
}

interface PerguntaAPI {
  id: string
  texto: string
  tipo: 'escolha' | 'texto' | 'data' | 'valor'
  opcoes: string[]
}

interface EstadoAPI {
  caso_id: string
  ressalva: string
  terminado: boolean
  motivo_fim: string
  via_llm: boolean
  perguntas_feitas: number
  areas_preliminares: string[]
  confianca: number
  alertas: AlertaAPI[]
  pergunta: PerguntaAPI | null
}

interface FichaAPI {
  caso_id: string
  ficha: Record<string, unknown>
  texto_para_analise: string
  alertas: AlertaAPI[]
  areas: string[]
  resumo: string
}

const OPCAO_OUTRO = 'Outro / prefiro explicar'
const MAX_PERGUNTAS = 7

const NOMES_AREAS: Record<string, string> = {
  laboral: 'Trabalho', penal: 'Penal', civil: 'Civil',
  dados_pessoais: 'Dados pessoais', familia: 'Família',
  consumo: 'Consumo', administrativo: 'Administrativo', outro: 'Outra',
}

const NOMES_ALERTAS: Record<AlertaAPI['tipo'], string> = {
  prazo: 'Prazo',
  via_nao_judicial: 'Caminho a seguir',
  apoio_judiciario: 'Apoio judiciário',
}

// ── Página ───────────────────────────────────────────────────────────────────

export default function PaginaInstrutor() {
  const { utilizador } = useAuthStore()
  const ehProfissional = utilizador?.role === 'advogado' || utilizador?.role === 'magistrado'

  const [fase, setFase] = useState<'intro' | 'perguntas' | 'ficha'>('intro')
  const [relato, setRelato] = useState('')
  const [dificuldades, setDificuldades] = useState(false)
  const [estado, setEstado] = useState<EstadoAPI | null>(null)
  const [ficha, setFicha] = useState<FichaAPI | null>(null)
  const [analise, setAnalise] = useState<AnalysisResponse | null>(null)

  const [respostaTexto, setRespostaTexto] = useState('')
  const [modoOutro, setModoOutro] = useState(false)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const topoRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  const mensagem = (a: AlertaAPI) => (ehProfissional ? a.mensagem_tecnica : a.mensagem_cidada)

  // ── Chamadas à API ─────────────────────────────────────────────────────

  const iniciar = async () => {
    if (relato.trim().length < 10 || carregando) return
    setCarregando(true); setErro(null)
    try {
      const res = await api.post<EstadoAPI>('/instrutor/iniciar', {
        relato, dificuldades_economicas: dificuldades,
      })
      setEstado(res.data)
      setFase('perguntas')
      if (res.data.terminado) await concluir(res.data.caso_id)
    } catch (e) { setErro(tratarErroAPI(e)) }
    finally { setCarregando(false) }
  }

  const responder = async (valor: string) => {
    if (!estado?.pergunta || carregando || !valor.trim()) return
    setCarregando(true); setErro(null)
    try {
      const res = await api.post<EstadoAPI>(
        `/instrutor/${estado.caso_id}/responder`,
        { pergunta_id: estado.pergunta.id, valor },
      )
      setEstado(res.data)
      setRespostaTexto(''); setModoOutro(false)
      if (res.data.terminado) await concluir(res.data.caso_id)
    } catch (e) { setErro(tratarErroAPI(e)) }
    finally { setCarregando(false) }
  }

  const concluir = async (casoId: string) => {
    try {
      const res = await api.post<FichaAPI>(`/instrutor/${casoId}/concluir`)
      setFicha(res.data)
      setFase('ficha')
      setTimeout(() => topoRef.current?.scrollIntoView({ behavior: 'smooth' }), 100)
    } catch (e) { setErro(tratarErroAPI(e)) }
  }

  const enviarParaAnalise = async () => {
    if (!ficha || carregando) return
    setCarregando(true); setErro(null)
    try {
      const res = await juridicalService.analisar({
        texto: ficha.texto_para_analise,
        fontes: ['CRP', 'CT', 'CC', 'RGPD', 'CP', 'CPC'],
      })
      setAnalise(res)
    } catch (e) { setErro(tratarErroAPI(e)) }
    finally { setCarregando(false) }
  }

  const recomecar = () => {
    setFase('intro'); setEstado(null); setFicha(null); setAnalise(null)
    setRelato(''); setDificuldades(false); setErro(null)
    setRespostaTexto(''); setModoOutro(false)
  }

  // ── Blocos visuais ─────────────────────────────────────────────────────

  const cartao: React.CSSProperties = {
    background: 'var(--color-background-primary)',
    border: '0.5px solid var(--color-border-tertiary)',
    borderRadius: 'var(--border-radius-lg)',
    padding: '14px 16px',
  }

  const botaoPrimario: React.CSSProperties = {
    background: '#0a2342', color: '#fff', border: 'none',
    borderRadius: 'var(--border-radius-md)', padding: '9px 18px',
    fontSize: 13, fontWeight: 500, cursor: 'pointer', fontFamily: 'inherit',
  }

  const Alertas = ({ alertas }: { alertas: AlertaAPI[] }) => (
    <>
      {alertas.map((a, i) => {
        const urgente = a.gravidade === 'urgente'
        return (
          <div key={i} style={{
            ...cartao,
            borderLeft: `3px solid ${urgente ? 'var(--color-text-danger)' : '#c4960a'}`,
          }}>
            <div style={{
              fontSize: 10, fontWeight: 600, textTransform: 'uppercase',
              letterSpacing: '0.08em', marginBottom: 4,
              color: urgente ? 'var(--color-text-danger)' : 'var(--color-text-tertiary)',
            }}>
              {urgente ? '⚠ Atenção urgente · ' : ''}{NOMES_ALERTAS[a.tipo]}
              {a.norma_base ? ` · ${a.norma_base.replace('-', ' art. ')}` : ''}
            </div>
            <div style={{ fontSize: 13, lineHeight: 1.55, color: 'var(--color-text-primary)' }}>
              {mensagem(a)}
            </div>
          </div>
        )
      })}
    </>
  )

  const Ressalva = ({ texto }: { texto: string }) => (
    <div style={{
      fontSize: 11.5, lineHeight: 1.55, color: 'var(--color-text-tertiary)',
      borderTop: '0.5px solid var(--color-border-tertiary)', paddingTop: 10,
    }}>
      {texto}
    </div>
  )

  // ── Render da pergunta consoante o tipo ────────────────────────────────

  const renderPergunta = (p: PerguntaAPI) => {
    if (p.tipo === 'escolha' && !modoOutro) {
      return (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {p.opcoes.map(op => (
            <button
              key={op}
              disabled={carregando}
              onClick={() => (op === OPCAO_OUTRO ? setModoOutro(true) : responder(op))}
              style={{
                background: op === OPCAO_OUTRO ? 'transparent' : 'var(--color-background-secondary)',
                border: '0.5px solid var(--color-border-secondary)',
                borderRadius: 'var(--border-radius-md)',
                padding: '9px 16px', fontSize: 13, cursor: 'pointer',
                fontFamily: 'inherit', color: 'var(--color-text-primary)',
              }}
            >
              {op}
            </button>
          ))}
        </div>
      )
    }

    if (p.tipo === 'data') {
      return (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            type="date"
            value={respostaTexto}
            onChange={e => setRespostaTexto(e.target.value)}
            style={{
              border: '0.5px solid var(--color-border-secondary)',
              borderRadius: 'var(--border-radius-md)', padding: '8px 12px',
              fontSize: 13, fontFamily: 'inherit',
            }}
          />
          <button style={botaoPrimario} disabled={carregando || !respostaTexto}
                  onClick={() => responder(respostaTexto)}>
            Confirmar data
          </button>
        </div>
      )
    }

    if (p.tipo === 'valor') {
      return (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            type="number" min="0" step="0.01" placeholder="0,00"
            value={respostaTexto}
            onChange={e => setRespostaTexto(e.target.value)}
            style={{
              border: '0.5px solid var(--color-border-secondary)',
              borderRadius: 'var(--border-radius-md)', padding: '8px 12px',
              fontSize: 13, fontFamily: 'inherit', width: 140,
            }}
          />
          <span style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>€</span>
          <button style={botaoPrimario} disabled={carregando || !respostaTexto}
                  onClick={() => responder(respostaTexto)}>
            Confirmar valor
          </button>
        </div>
      )
    }

    // texto livre (inclui o modo "Outro / prefiro explicar")
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <textarea
          rows={3}
          value={respostaTexto}
          onChange={e => setRespostaTexto(e.target.value)}
          placeholder="Escreva a sua resposta…"
          style={{
            border: '0.5px solid var(--color-border-secondary)',
            borderRadius: 'var(--border-radius-md)', padding: '10px 12px',
            fontSize: 13, fontFamily: 'inherit', resize: 'vertical',
            lineHeight: 1.5,
          }}
        />
        <div style={{ display: 'flex', gap: 8 }}>
          <button style={botaoPrimario} disabled={carregando || !respostaTexto.trim()}
                  onClick={() => responder(respostaTexto)}>
            Enviar resposta
          </button>
          {modoOutro && (
            <button
              onClick={() => { setModoOutro(false); setRespostaTexto('') }}
              style={{
                background: 'transparent', border: 'none', fontSize: 12,
                color: 'var(--color-text-tertiary)', cursor: 'pointer',
                fontFamily: 'inherit',
              }}
            >
              ← voltar às opções
            </button>
          )}
        </div>
      </div>
    )
  }

  // ── Página ─────────────────────────────────────────────────────────────

  return (
    <div ref={topoRef} style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: 780 }}>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
        <h1 style={{
          fontFamily: "'Cormorant Garamond', serif",
          fontSize: 22, fontWeight: 500, color: 'var(--color-text-primary)',
        }}>
          Instrução do caso
        </h1>
        <small style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>
          O Instrutor faz-lhe perguntas para compreender a sua situação
        </small>
      </div>

      {erro && (
        <div style={{ ...cartao, borderLeft: '3px solid var(--color-text-danger)', fontSize: 13 }}>
          {erro}
        </div>
      )}

      {/* ── Fase 1: relato inicial ─────────────────────────────────── */}
      {fase === 'intro' && (
        <div style={{ ...cartao, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{
            fontSize: 11, fontWeight: 500, textTransform: 'uppercase',
            letterSpacing: '0.07em', color: 'var(--color-text-tertiary)',
          }}>
            Descreva o que aconteceu, por palavras suas
          </div>
          <textarea
            rows={6}
            value={relato}
            onChange={e => setRelato(e.target.value)}
            placeholder="Ex.: Fui despedido no mês passado sem me darem qualquer explicação por escrito…"
            style={{
              border: '0.5px solid var(--color-border-secondary)',
              borderRadius: 'var(--border-radius-md)', padding: '10px 12px',
              fontSize: 13.5, fontFamily: 'inherit', resize: 'vertical',
              lineHeight: 1.6,
            }}
          />
          <label style={{
            display: 'flex', alignItems: 'center', gap: 8,
            fontSize: 13, color: 'var(--color-text-secondary)', cursor: 'pointer',
          }}>
            <input
              type="checkbox"
              checked={dificuldades}
              onChange={e => setDificuldades(e.target.checked)}
            />
            Tenho dificuldades económicas em pagar advogado ou custas
          </label>
          <div>
            <button
              style={botaoPrimario}
              disabled={carregando || relato.trim().length < 10}
              onClick={iniciar}
            >
              {carregando ? 'A iniciar…' : 'Começar a instrução'}
            </button>
          </div>
          <Ressalva texto={
            'O SNAJI presta informação jurídica de carácter geral e apoio à preparação ' +
            'processual. Não presta consulta jurídica nem patrocínio, atos reservados por ' +
            'lei a advogados e solicitadores (Lei n.º 49/2004). Nenhum resultado deste ' +
            'sistema substitui o aconselhamento de um profissional habilitado nem constitui ' +
            'decisão judicial.'
          } />
        </div>
      )}

      {/* ── Fase 2: perguntas do Instrutor ─────────────────────────── */}
      {fase === 'perguntas' && estado && (
        <>
          {estado.areas_preliminares.length > 0 && (
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {estado.areas_preliminares.map(a => (
                <span key={a} style={{
                  fontSize: 11, padding: '3px 10px', borderRadius: 20,
                  background: 'var(--color-background-secondary)',
                  border: '0.5px solid var(--color-border-tertiary)',
                  color: 'var(--color-text-secondary)',
                }}>
                  {NOMES_AREAS[a] ?? a}
                </span>
              ))}
              <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)', alignSelf: 'center' }}>
                — classificação preliminar, pode mudar com as suas respostas
              </span>
            </div>
          )}

          <Alertas alertas={estado.alertas} />

          {estado.pergunta && (
            <div style={{ ...cartao, display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              }}>
                <div style={{
                  fontSize: 11, fontWeight: 500, textTransform: 'uppercase',
                  letterSpacing: '0.07em', color: 'var(--color-text-tertiary)',
                }}>
                  Pergunta {estado.perguntas_feitas} de no máximo {MAX_PERGUNTAS}
                </div>
                <div style={{ display: 'flex', gap: 4 }}>
                  {Array.from({ length: MAX_PERGUNTAS }).map((_, i) => (
                    <span key={i} style={{
                      width: 6, height: 6, borderRadius: '50%',
                      background: i < estado.perguntas_feitas ? '#c4960a' : 'var(--color-border-tertiary)',
                    }} />
                  ))}
                </div>
              </div>

              <div style={{
                fontSize: 15, lineHeight: 1.55, color: 'var(--color-text-primary)',
                fontWeight: 450,
              }}>
                {estado.pergunta.texto}
              </div>

              {renderPergunta(estado.pergunta)}
            </div>
          )}
        </>
      )}

      {/* ── Fase 3: Ficha de Factos e análise ──────────────────────── */}
      {fase === 'ficha' && ficha && (
        <>
          <div style={{ ...cartao, display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{
              fontSize: 11, fontWeight: 500, textTransform: 'uppercase',
              letterSpacing: '0.07em', color: 'var(--color-text-tertiary)',
            }}>
              Instrução concluída · Ficha de Factos
            </div>
            {ficha.resumo && (
              <div style={{ fontSize: 13.5, lineHeight: 1.6, color: 'var(--color-text-primary)' }}>
                {ficha.resumo}
              </div>
            )}
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {ficha.areas.map(a => (
                <span key={a} style={{
                  fontSize: 11, padding: '3px 10px', borderRadius: 20,
                  background: 'var(--color-background-secondary)',
                  border: '0.5px solid var(--color-border-tertiary)',
                  color: 'var(--color-text-secondary)',
                }}>
                  {NOMES_AREAS[a] ?? a}
                </span>
              ))}
            </div>
            <pre style={{
              fontSize: 12, lineHeight: 1.6, whiteSpace: 'pre-wrap',
              background: 'var(--color-background-secondary)',
              borderRadius: 'var(--border-radius-md)', padding: '10px 12px',
              color: 'var(--color-text-secondary)', margin: 0,
              fontFamily: 'inherit',
            }}>
              {ficha.texto_para_analise}
            </pre>
            <div style={{ display: 'flex', gap: 10 }}>
              {!analise && (
                <button style={botaoPrimario} disabled={carregando} onClick={enviarParaAnalise}>
                  {carregando ? 'A analisar…' : 'Enviar para análise jurídica'}
                </button>
              )}
              <button
                onClick={() => navigate('/cenarios', { state: { texto: ficha.texto_para_analise } })}
                style={{ ...botaoPrimario, background: '#1a4a7a' }}
              >
                Ver cenários de resolução
              </button>
              <button
                onClick={recomecar}
                style={{
                  background: 'transparent',
                  border: '0.5px solid var(--color-border-secondary)',
                  borderRadius: 'var(--border-radius-md)', padding: '9px 18px',
                  fontSize: 13, cursor: 'pointer', fontFamily: 'inherit',
                  color: 'var(--color-text-secondary)',
                }}
              >
                Novo caso
              </button>
            </div>
          </div>

          <Alertas alertas={ficha.alertas} />

          {analise && (
            <div style={{ ...cartao, display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{
                fontSize: 11, fontWeight: 500, textTransform: 'uppercase',
                letterSpacing: '0.07em', color: 'var(--color-text-tertiary)',
              }}>
                Análise jurídica
              </div>
              <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--color-text-primary)' }}>
                {analise.qualificacao_juridica}
              </div>
              <div style={{ fontSize: 13.5, lineHeight: 1.65, whiteSpace: 'pre-wrap', color: 'var(--color-text-primary)' }}>
                {analise.analise}
              </div>
              {analise.vias_processuais?.length > 0 && (
                <div style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--color-text-secondary)' }}>
                  <strong style={{ color: 'var(--color-text-primary)' }}>Vias processuais típicas: </strong>
                  {analise.vias_processuais.join('; ')}
                </div>
              )}
              <div style={{ fontSize: 13.5, lineHeight: 1.6, color: 'var(--color-text-primary)' }}>
                {analise.conclusao}
              </div>
            </div>
          )}

          <Ressalva texto={
            'Esta informação é geral e não substitui consulta jurídica por advogado ' +
            '(Lei n.º 49/2004). Se algum alerta acima indicar prazos, procure ajuda ' +
            'profissional o mais rapidamente possível.'
          } />
        </>
      )}
    </div>
  )
}
