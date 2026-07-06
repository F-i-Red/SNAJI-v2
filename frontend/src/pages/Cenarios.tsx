/**
 * Página dos Cenários de Resolução — SNAJI (Especificação V8, §2 e §3)
 *
 * Mostra até 3 cenários (garantista / legalista / consequencialista) com:
 *  - interruptor de registo: linguagem clara ↔ registo técnico
 *  - faixa de convergência quando as três lentes coincidem
 *  - solidez qualitativa (nunca percentagens)
 *  - normas validadas contra o corpus e citações rejeitadas visíveis
 *
 * Pode receber o texto do caso via navegação (state.texto) — é assim que a
 * página do Instrutor encaminha a Ficha de Factos para aqui.
 */

import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { api, tratarErroAPI } from '../services/api'
import { useAuthStore } from '../auth/session'

// ── Tipos da API ─────────────────────────────────────────────────────────────

interface CenarioAPI {
  lente: 'garantista' | 'legalista' | 'consequencialista'
  lente_descricao_tecnica: string
  lente_descricao_cidada: string
  titulo: string
  sentido: string
  solucao_tecnica: string
  solucao_cidada: string
  riscos: string
  riscos_cidadao: string
  solidez: 'elevada' | 'media' | 'baixa'
  fundamentacao_normas: string[]
  normas_rejeitadas: string[]
}

interface EtapaPercurso {
  etapa: number
  nome: string
  descricao: string
  dados: Record<string, unknown>
}

interface CenariosAPI {
  cenarios: CenarioAPI[]
  convergencia: boolean
  sintese_tecnica: string
  sintese_cidada: string
  normas_rejeitadas_total: string[]
  ressalva: string
  via_llm: boolean
  percurso: EtapaPercurso[] | null
}

const NOME_LENTE: Record<CenarioAPI['lente'], string> = {
  garantista: 'Garantista',
  legalista: 'Legalista',
  consequencialista: 'Consequencialista',
}

const NOME_SENTIDO: Record<string, string> = {
  procedente: 'Tipicamente favorável',
  improcedente: 'Tipicamente desfavorável',
  condenacao: 'Tendência condenatória',
  absolvicao: 'Tendência absolutória',
  misto: 'Desfecho incerto',
}

const NOME_SOLIDEZ: Record<CenarioAPI['solidez'], string> = {
  elevada: 'Solidez elevada',
  media: 'Solidez média',
  baixa: 'Solidez baixa',
}


const NOME_ETAPA: Record<string, string> = {
  entrada: 'Receção do caso',
  recuperacao_de_normas: 'Pesquisa das normas no corpus',
  geracao_das_lentes: 'Análise pelas três lentes',
  validacao_anti_alucinacao: 'Validação de todas as citações',
  regras_de_apresentacao: 'Regras de viabilidade e convergência',
  saida_dupla: 'Derivação da linguagem clara',
}

// ── Página ───────────────────────────────────────────────────────────────────

export default function PaginaCenarios() {
  const { utilizador } = useAuthStore()
  const ehProfissional = utilizador?.role === 'advogado' || utilizador?.role === 'magistrado'
  const location = useLocation() as { state?: { texto?: string; caso_id?: string; contraditorio?: boolean } }
  const navigate = useNavigate()

  const [texto, setTexto] = useState(location.state?.texto ?? '')
  const [resultado, setResultado] = useState<CenariosAPI | null>(null)
  const [registoTecnico, setRegistoTecnico] = useState(ehProfissional)
  const [carregando, setCarregando] = useState(false)
  const [mostrarPercurso, setMostrarPercurso] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const gerar = async (t?: string) => {
    const corpo = (t ?? texto).trim()
    if (corpo.length < 20 || carregando) return
    setCarregando(true); setErro(null); setResultado(null)
    try {
      const res = await api.post<CenariosAPI>('/cenarios', { texto: corpo, explicar: true, caso_id: location.state?.caso_id ?? null, contraditorio: location.state?.contraditorio ?? false })
      setResultado(res.data)
    } catch (e) { setErro(tratarErroAPI(e)) }
    finally { setCarregando(false) }
  }

  // Se veio do Instrutor com texto, gera automaticamente
  useEffect(() => {
    if (location.state?.texto) gerar(location.state.texto)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Estilos base (design system SNAJI) ─────────────────────────────────

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

  const etiqueta: React.CSSProperties = {
    fontSize: 11, padding: '3px 10px', borderRadius: 20,
    background: 'var(--color-background-secondary)',
    border: '0.5px solid var(--color-border-tertiary)',
    color: 'var(--color-text-secondary)',
  }

  const Solidez = ({ nivel }: { nivel: CenarioAPI['solidez'] }) => {
    const n = nivel === 'elevada' ? 3 : nivel === 'media' ? 2 : 1
    return (
      <span style={{ display: 'inline-flex', gap: 3, alignItems: 'center' }}
            title={NOME_SOLIDEZ[nivel]}>
        {[0, 1, 2].map(i => (
          <span key={i} style={{
            width: 7, height: 7, borderRadius: '50%',
            background: i < n ? '#c4960a' : 'var(--color-border-tertiary)',
          }} />
        ))}
        <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)', marginLeft: 4 }}>
          {NOME_SOLIDEZ[nivel]}
        </span>
      </span>
    )
  }

  const CartaoCenario = ({ c }: { c: CenarioAPI }) => (
    <div style={{ ...cartao, display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <span style={{
          fontSize: 11, fontWeight: 600, textTransform: 'uppercase',
          letterSpacing: '0.08em', color: '#0a2342',
        }}>
          Lente {NOME_LENTE[c.lente]}
        </span>
        <Solidez nivel={c.solidez} />
      </div>

      <div style={{ fontSize: 12, color: 'var(--color-text-tertiary)', fontStyle: 'italic' }}>
        {registoTecnico ? c.lente_descricao_tecnica : c.lente_descricao_cidada}
      </div>

      <div style={{ fontSize: 14.5, fontWeight: 500, color: 'var(--color-text-primary)' }}>
        {c.titulo}
      </div>

      <span style={{ ...etiqueta, alignSelf: 'flex-start' }}>
        {NOME_SENTIDO[c.sentido] ?? c.sentido}
      </span>

      <div style={{ fontSize: 13.5, lineHeight: 1.65, color: 'var(--color-text-primary)', whiteSpace: 'pre-wrap' }}>
        {registoTecnico ? c.solucao_tecnica : c.solucao_cidada}
      </div>

      {(registoTecnico ? c.riscos : c.riscos_cidadao) && (
        <div style={{
          fontSize: 12.5, lineHeight: 1.6, color: 'var(--color-text-secondary)',
          borderLeft: '3px solid #c4960a', paddingLeft: 10,
        }}>
          <strong style={{ color: 'var(--color-text-primary)' }}>
            {registoTecnico ? 'Riscos e contra-argumentos: ' : 'O que pode correr de outra forma: '}
          </strong>
          {registoTecnico ? c.riscos : c.riscos_cidadao}
        </div>
      )}

      {c.fundamentacao_normas.length > 0 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)' }}>
            {registoTecnico ? 'Normas validadas no corpus:' : 'Artigos de lei verificados:'}
          </span>
          {c.fundamentacao_normas.map(n => (
            <span key={n} style={etiqueta}>{n.replace('-', ' art. ')}</span>
          ))}
        </div>
      )}

      {c.normas_rejeitadas.length > 0 && (
        <div style={{ fontSize: 11.5, color: 'var(--color-text-danger)' }}>
          ⚠ Citações rejeitadas pelo validador (não constam do corpus):{' '}
          {c.normas_rejeitadas.join(', ')}
        </div>
      )}
    </div>
  )

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: 860 }}>

      {location.state?.contraditorio && (
        <div style={{
          padding: '8px 14px', borderRadius: 'var(--border-radius-md)',
          background: '#f7ead9', color: '#7a3b0a', fontSize: 12.5, fontWeight: 500,
        }}>
          ⇄ Análise do contraditório — estes cenários adotam a perspetiva da parte contrária,
          para preparar os argumentos que virão contra si.
        </div>
      )}
      {location.state?.caso_id && (
        <button
          onClick={() => navigate('/instrutor', { state: { retomar_caso_id: location.state!.caso_id } })}
          style={{
            alignSelf: 'flex-start', background: 'transparent', border: 'none', cursor: 'pointer',
            fontFamily: 'inherit', fontSize: 12.5, color: 'var(--color-text-secondary)', padding: 0,
          }}
        >
          ← Voltar ao caso instruído
        </button>
      )}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <h1 style={{
          fontFamily: "'Cormorant Garamond', serif",
          fontSize: 22, fontWeight: 500, color: 'var(--color-text-primary)',
        }}>
          Cenários de resolução
        </h1>
        <small style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>
          O mesmo caso analisado por três abordagens da prática judiciária
        </small>
      </div>

      {erro && (
        <div style={{ ...cartao, borderLeft: '3px solid var(--color-text-danger)', fontSize: 13 }}>
          {erro}
        </div>
      )}

      <div style={{ ...cartao, display: 'flex', flexDirection: 'column', gap: 10 }}>
        <textarea
          rows={4}
          value={texto}
          onChange={e => setTexto(e.target.value)}
          placeholder="Descreva o caso (ou chegue aqui a partir da Instrução do caso, que envia a Ficha de Factos automaticamente)…"
          style={{
            border: '0.5px solid var(--color-border-secondary)',
            borderRadius: 'var(--border-radius-md)', padding: '10px 12px',
            fontSize: 13.5, fontFamily: 'inherit', resize: 'vertical', lineHeight: 1.6,
          }}
        />
        <div>
          <button style={botaoPrimario} disabled={carregando || texto.trim().length < 20}
                  onClick={() => gerar()}>
            {carregando ? 'A analisar pelas três lentes…' : 'Gerar cenários'}
          </button>
        </div>
      </div>

      {resultado && (
        <>
          {/* Interruptor de registo */}
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <div style={{
              display: 'inline-flex', border: '0.5px solid var(--color-border-secondary)',
              borderRadius: 20, overflow: 'hidden',
            }}>
              {(['clara', 'tecnico'] as const).map(m => {
                const ativo = (m === 'tecnico') === registoTecnico
                return (
                  <button key={m}
                    onClick={() => setRegistoTecnico(m === 'tecnico')}
                    style={{
                      border: 'none', padding: '6px 14px', fontSize: 12,
                      fontFamily: 'inherit', cursor: 'pointer',
                      background: ativo ? '#0a2342' : 'transparent',
                      color: ativo ? '#fff' : 'var(--color-text-secondary)',
                    }}>
                    {m === 'clara' ? 'Linguagem clara' : 'Registo técnico'}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Faixa de convergência */}
          {resultado.convergencia && (
            <div style={{
              ...cartao, borderLeft: '3px solid #1a7a4a',
              fontSize: 13, lineHeight: 1.6, color: 'var(--color-text-primary)',
            }}>
              <strong>As três abordagens convergem.</strong>{' '}
              {registoTecnico
                ? 'Indicador de caso juridicamente claro: as lentes garantista, legalista e consequencialista apontam no mesmo sentido.'
                : 'As três formas de olhar para o seu caso chegam à mesma conclusão — é sinal de que a lei é clara nesta situação.'}
            </div>
          )}

          {/* Cartões dos cenários */}
          <div style={{
            display: 'grid', gap: 12,
            gridTemplateColumns: resultado.cenarios.length > 1
              ? 'repeat(auto-fit, minmax(260px, 1fr))' : '1fr',
          }}>
            {resultado.cenarios.map(c => <CartaoCenario key={c.lente} c={c} />)}
          </div>

          {/* Síntese */}
          {(registoTecnico ? resultado.sintese_tecnica : resultado.sintese_cidada) && (
            <div style={{ ...cartao, fontSize: 13, lineHeight: 1.65 }}>
              <strong style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-tertiary)' }}>
                Síntese comparativa
              </strong>
              <div style={{ marginTop: 6, color: 'var(--color-text-primary)' }}>
                {registoTecnico ? resultado.sintese_tecnica : resultado.sintese_cidada}
              </div>
            </div>
          )}

          {/* Explicabilidade: porquê esta análise? */}
          {resultado.percurso && (
            <div style={cartao}>
              <button
                onClick={() => setMostrarPercurso(v => !v)}
                style={{
                  background: 'transparent', border: 'none', cursor: 'pointer',
                  fontFamily: 'inherit', fontSize: 12.5, fontWeight: 600,
                  color: '#0a2342', padding: 0,
                }}
              >
                {mostrarPercurso ? '▾' : '▸'} Porquê esta análise? (percurso do sistema, {resultado.percurso.length} etapas)
              </button>
              {mostrarPercurso && (
                <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 0 }}>
                  {resultado.percurso.map((p, i) => (
                    <div key={p.etapa} style={{ display: 'flex', gap: 12 }}>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                        <div style={{
                          width: 22, height: 22, borderRadius: '50%', background: '#0a2342',
                          color: '#fff', fontSize: 11, display: 'flex',
                          alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                        }}>{p.etapa}</div>
                        {i < resultado.percurso!.length - 1 && (
                          <div style={{ width: 1, flex: 1, background: 'var(--color-border-secondary)', minHeight: 14 }} />
                        )}
                      </div>
                      <div style={{ paddingBottom: 14 }}>
                        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--color-text-primary)' }}>
                          {NOME_ETAPA[p.nome] ?? p.nome}
                        </div>
                        <div style={{ fontSize: 12, lineHeight: 1.55, color: 'var(--color-text-secondary)' }}>
                          {p.descricao}
                        </div>
                        {p.nome === 'recuperacao_de_normas' && Array.isArray((p.dados as any).normas_recuperadas) && (
                          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginTop: 5 }}>
                            {((p.dados as any).normas_recuperadas as any[]).slice(0, 8).map(n => (
                              <span key={n.norma} style={etiqueta} title={`relevância ${n.relevancia}`}>
                                {String(n.norma).replace('-', ' art. ')}
                              </span>
                            ))}
                          </div>
                        )}
                        {p.nome === 'validacao_anti_alucinacao' &&
                          Object.keys((p.dados as any).rejeitadas_por_lente ?? {}).length > 0 && (
                          <div style={{ fontSize: 11.5, color: 'var(--color-text-danger)', marginTop: 4 }}>
                            Citações rejeitadas: {Object.values((p.dados as any).rejeitadas_por_lente).flat().join(', ')}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Ressalva legal */}
          <div style={{
            fontSize: 11.5, lineHeight: 1.55, color: 'var(--color-text-tertiary)',
            borderTop: '0.5px solid var(--color-border-tertiary)', paddingTop: 10,
          }}>
            {resultado.ressalva}
          </div>
        </>
      )}
    </div>
  )
}
