import { useState, useRef, useEffect } from 'react'
import { api, tratarErroAPI } from '../services/api'
import { useAuthStore } from '../auth/session'

type Fase = 'abertura' | 'acusacao_pedido' | 'defesa' | 'replica' | 'prova' | 'perguntas_juiz' | 'alegacoes_finais' | 'deliberacao' | 'decisao'
type Papel = 'juiz' | 'acusacao' | 'defesa' | 'perito' | 'assistente'

const FASES_ORDEM: Fase[] = ['abertura','acusacao_pedido','defesa','replica','prova','perguntas_juiz','alegacoes_finais','deliberacao','decisao']
const FASE_LABELS: Record<Fase, string> = {
  abertura: 'Abertura', acusacao_pedido: 'Acusação', defesa: 'Defesa',
  replica: 'Réplica', prova: 'Prova', perguntas_juiz: 'Perguntas',
  alegacoes_finais: 'Alegações', deliberacao: 'Deliberação', decisao: 'Decisão',
}
const PAPEL_COR: Record<Papel, string> = {
  juiz: '#0a2342', acusacao: '#C0392B', defesa: '#0F6E56',
  perito: '#6B4C9A', assistente: '#BA7517',
}
const PAPEL_LABEL: Record<Papel, string> = {
  juiz: 'Juiz', acusacao: 'Acusação', defesa: 'Defesa',
  perito: 'Perito', assistente: 'Assistente',
}

interface Intervencao {
  id: string; ronda: number; papel: Papel; tipo: string
  conteudo: string; normas_citadas: string[]
  timestamp: string; hash_integridade: string
}
interface Prova {
  id: string; apresentada_por: Papel; tipo: string
  descricao: string; nome_ficheiro?: string; timestamp: string
  hash_integridade: string
}
interface Audiencia {
  id: string; tipo: string; tipo_processo: string
  descricao_caso: string; estado: string
  fase_actual: Fase; fase_descricao: string
  papel_criador: Papel
  aguarda_intervencao_de: Papel | null
  loops_contraditorio: number; max_loops: number
  participantes: { papel: Papel; nome: string }[]
  intervencoes: Intervencao[]; provas: Prova[]
  decisao: { sumario: string; fundamentacao: string; normas_aplicadas: string[]; dispositivo: string; recursos_possiveis: string[] } | null
}

export default function PaginaAudiencias() {
  const { utilizador } = useAuthStore()
  const [vista, setVista] = useState<'lista' | 'criar' | 'audiencia'>('lista')
  const [audiencias, setAudiencias] = useState<Audiencia[]>([])
  const [audienciaActual, setAudienciaActual] = useState<Audiencia | null>(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [textoIntervencao, setTextoIntervencao] = useState('')
  const [papelSeleccionado, setPapelSeleccionado] = useState<Papel>('juiz')
  const [formNovo, setFormNovo] = useState({ descricao_caso: '', tipo_audiencia: 'julgamento', papel_criador: 'acusacao', com_perito: false, max_loops: 3 })
  const [areasSel, setAreasSel] = useState<string[]>(['laboral'])
  const intervencaoRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (vista === 'lista') carregarLista()
  }, [vista])

  const carregarLista = async () => {
    try {
      const r = await api.get('/audiencias')
      setAudiencias(r.data.audiencias)
    } catch (e) { setErro(tratarErroAPI(e)) }
  }

  const abrirAudiencia = async (id: string) => {
    setCarregando(true)
    try {
      const r = await api.get(`/audiencias/${id}`)
      setAudienciaActual(r.data)
      if ((r.data as any).papel_sugerido) setPapelSeleccionado((r.data as any).papel_sugerido)
      setVista('audiencia')
    } catch (e) { setErro(tratarErroAPI(e)) }
    finally { setCarregando(false) }
  }

  const criarAudiencia = async () => {
    setCarregando(true); setErro(null)
    try {
      const payload = {
        ...formNovo,
        areas: areasSel,
        // penal comanda a ordem das fases; senão, a primeira área escolhida
        tipo_processo: areasSel.includes('penal') ? 'penal' : (areasSel[0] ?? 'civil'),
      }
      const r = await api.post('/audiencias', payload)
      await abrirAudiencia(r.data.id)
    } catch (e) { setErro(tratarErroAPI(e)); setCarregando(false) }
  }

  const submeterIntervencao = async (ia = false) => {
    if (!audienciaActual) return
    setCarregando(true); setErro(null)
    try {
      if (ia) {
        await api.post(`/audiencias/${audienciaActual.id}/intervencao-ia`, { papel: papelSeleccionado })
      } else {
        if (!textoIntervencao.trim()) return
        await api.post(`/audiencias/${audienciaActual.id}/intervencao`, {
          papel: papelSeleccionado, conteudo: textoIntervencao, tipo: 'alegacao'
        })
        setTextoIntervencao('')
      }
      const r = await api.get(`/audiencias/${audienciaActual.id}`)
      setAudienciaActual(r.data)
      if ((r.data as any).papel_sugerido) setPapelSeleccionado((r.data as any).papel_sugerido)
      setTimeout(() => intervencaoRef.current?.scrollIntoView({ behavior: 'smooth' }), 100)
    } catch (e) { setErro(tratarErroAPI(e)) }
    finally { setCarregando(false) }
  }

  const proferirDecisao = async () => {
    if (!audienciaActual) return
    setCarregando(true); setErro(null)
    try {
      await api.post(`/audiencias/${audienciaActual.id}/decidir`)
      const r = await api.get(`/audiencias/${audienciaActual.id}`)
      setAudienciaActual(r.data)
      if ((r.data as any).papel_sugerido) setPapelSeleccionado((r.data as any).papel_sugerido)
    } catch (e) { setErro(tratarErroAPI(e)) }
    finally { setCarregando(false) }
  }

  const faseIdx = audienciaActual ? FASES_ORDEM.indexOf(audienciaActual.fase_actual) : -1

  // ── Vista: Lista ───────────────────────────────────────────────────────────
  const BASE = (import.meta as any).env?.VITE_API_URL ?? 'http://localhost:8000/api/v1'

  const abrirAtaHTML = async () => {
    if (!audienciaActual) return
    try {
      const tok = sessionStorage.getItem('snaji_token')
      const r = await fetch(`${BASE}/audiencias/${audienciaActual.id}/ata.html`, {
        headers: { Authorization: `Bearer ${tok}` },
      })
      const html = await r.text()
      const w = window.open('', '_blank')
      if (w) { w.document.write(html); w.document.close() }
    } catch { setErro('Não foi possível gerar a ata.') }
  }

  const descarregarAta = async (formato: 'md' | 'txt') => {
    if (!audienciaActual) return
    try {
      const tok = sessionStorage.getItem('snaji_token')
      const r = await fetch(`${BASE}/audiencias/${audienciaActual.id}/ata.${formato}`, {
        headers: { Authorization: `Bearer ${tok}` },
      })
      const blob = await r.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `ata-audiencia.${formato}`
      link.click()
      URL.revokeObjectURL(url)
    } catch { setErro('Não foi possível descarregar a ata.') }
  }

  if (vista === 'lista') return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <h1 style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 22, fontWeight: 500 }}>Audiências</h1>
        <button onClick={() => setVista('criar')} style={{ padding: '6px 14px', background: '#0a2342', color: '#fff', border: 'none', borderRadius: 'var(--border-radius-md)', fontSize: 12, fontWeight: 500, cursor: 'pointer', fontFamily: 'inherit' }}>
          + Nova audiência
        </button>
      </div>
      {erro && <div style={{ padding: '8px 12px', background: 'var(--color-background-danger)', border: '0.5px solid var(--color-border-danger)', borderRadius: 'var(--border-radius-md)', fontSize: 13, color: 'var(--color-text-danger)' }}>{erro}</div>}
      {audiencias.length === 0 ? (
        <div style={{ background: 'var(--color-background-primary)', border: '0.5px solid var(--color-border-tertiary)', borderRadius: 'var(--border-radius-lg)', padding: '3rem', textAlign: 'center' }}>
          <i className="ti ti-gavel" aria-hidden="true" style={{ fontSize: 32, color: 'var(--color-text-tertiary)', display: 'block', marginBottom: 8 }} />
          <div style={{ fontSize: 14, color: 'var(--color-text-secondary)' }}>Nenhuma audiência ainda</div>
          <div style={{ fontSize: 12, color: 'var(--color-text-tertiary)', marginTop: 4 }}>Crie uma audiência para simular um debate jurídico completo</div>
          <button onClick={() => setVista('criar')} style={{ marginTop: 16, padding: '8px 20px', background: '#0a2342', color: '#fff', border: 'none', borderRadius: 'var(--border-radius-md)', fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>
            Criar primeira audiência
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {audiencias.map(a => (
            <div key={a.id} onClick={() => abrirAudiencia(a.id)} style={{ background: 'var(--color-background-primary)', border: '0.5px solid var(--color-border-tertiary)', borderRadius: 'var(--border-radius-lg)', padding: '12px 16px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 12 }}>
              <i className="ti ti-gavel" aria-hidden="true" style={{ fontSize: 18, color: '#0a2342', flexShrink: 0 }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--color-text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.descricao_caso}</div>
                <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', marginTop: 2 }}>{(a as any).areas?.join(' + ') ?? a.tipo_processo} · {FASE_LABELS[a.fase_actual]} · {a.intervencoes?.length ?? 0} intervenções · {a.provas?.length ?? 0} provas</div>
              </div>
              <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 20, background: a.estado === 'concluida' ? 'var(--color-background-success)' : 'var(--color-background-info)', color: a.estado === 'concluida' ? 'var(--color-text-success)' : 'var(--color-text-info)', fontWeight: 500, flexShrink: 0 }}>{a.estado}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )

  // ── Vista: Criar ───────────────────────────────────────────────────────────
  if (vista === 'criar') return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: 600 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <button onClick={() => setVista('lista')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-secondary)', fontSize: 20, fontFamily: 'inherit' }}>←</button>
        <h1 style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 22, fontWeight: 500 }}>Nova audiência</h1>
      </div>
      {erro && <div style={{ padding: '8px 12px', background: 'var(--color-background-danger)', border: '0.5px solid var(--color-border-danger)', borderRadius: 'var(--border-radius-md)', fontSize: 13, color: 'var(--color-text-danger)' }}>{erro}</div>}
      <div style={{ background: 'var(--color-background-primary)', border: '0.5px solid var(--color-border-tertiary)', borderRadius: 'var(--border-radius-lg)', padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div>
          <label style={{ display: 'block', fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-secondary)', marginBottom: 6 }}>
            Áreas do caso (pode combinar — ex.: penal + civil)
          </label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 14px' }}>
            {['laboral','penal','civil','administrativo','familia','dados_pessoais','consumo'].map(ar => (
              <label key={ar} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 13, color: 'var(--color-text-primary)', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={areasSel.includes(ar)}
                  onChange={() => setAreasSel(p => p.includes(ar) ? p.filter(x => x !== ar) : [...p, ar])}
                />
                {ar.replace('_', ' ')}
              </label>
            ))}
          </div>
          {areasSel.includes('penal') && areasSel.includes('civil') && (
            <div style={{ fontSize: 11.5, color: 'var(--color-text-info)', marginTop: 5 }}>
              ⚖ Caso misto: o pedido de indemnização civil segue dentro do processo penal — regime de adesão (art. 71.º CPP). O tribunal constitui automaticamente demandante e demandado civis.
            </div>
          )}
        </div>
        {[
          { label: 'Tipo de audiência', field: 'tipo_audiencia', type: 'select', opts: ['julgamento','audiencia_preliminar','contraditorio','simulacao'] },
          { label: 'O seu papel processual', field: 'papel_criador', type: 'select', opts: ['acusacao','defesa','juiz','perito','assistente'], help: 'Quem é você nesta audiência? Vítima/Autor → Acusação; Arguido/Réu → Defesa' },
          { label: 'Loops máximos de contraditório', field: 'max_loops', type: 'select', opts: ['1','2','3','5'], help: 'Quantas rondas de troca de argumentos o juiz pode pedir' },
        ].map(f => (
          <div key={f.field}>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-secondary)', marginBottom: 4 }}>{f.label}</label>
            <select value={(formNovo as any)[f.field]} onChange={e => setFormNovo(p => ({ ...p, [f.field]: f.field === 'max_loops' ? Number(e.target.value) : e.target.value }))} style={{ width: '100%' }}>
              {f.opts?.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
            {(f as any).help && <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', marginTop: 3 }}>{(f as any).help}</div>}
          </div>
        ))}
        <div>
          <label style={{ display: 'block', fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-secondary)', marginBottom: 4 }}>Descrição do caso</label>
          <textarea value={formNovo.descricao_caso} onChange={e => setFormNovo(p => ({ ...p, descricao_caso: e.target.value }))} placeholder="Descreva os factos do caso. Ex: Trabalhador despedido sem justa causa após 5 anos de serviço..." rows={4} style={{ width: '100%' }} />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <input type="checkbox" id="com_perito" checked={formNovo.com_perito} onChange={e => setFormNovo(p => ({ ...p, com_perito: e.target.checked }))} />
          <label htmlFor="com_perito" style={{ fontSize: 13, color: 'var(--color-text-secondary)', cursor: 'pointer' }}>Incluir perito judicial</label>
        </div>
        <button onClick={criarAudiencia} disabled={carregando || !formNovo.descricao_caso.trim() || areasSel.length === 0} style={{ padding: '10px', background: '#0a2342', color: '#fff', border: 'none', borderRadius: 'var(--border-radius-md)', fontSize: 13, fontWeight: 500, cursor: carregando || !formNovo.descricao_caso.trim() ? 'not-allowed' : 'pointer', opacity: carregando || !formNovo.descricao_caso.trim() ? 0.6 : 1, fontFamily: 'inherit' }}>
          {carregando ? 'A criar...' : 'Iniciar audiência ↗'}
        </button>
      </div>
    </div>
  )

  // ── Vista: Audiência activa ────────────────────────────────────────────────
  if (!audienciaActual) return null
  const a = audienciaActual

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>

      {/* Cabeçalho */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
        <button onClick={() => { setVista('lista'); setAudienciaActual(null) }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-secondary)', fontSize: 20, marginTop: 2 }}>←</button>
        <div style={{ flex: 1 }}>
          <h1 style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 20, fontWeight: 500 }}>{a.descricao_caso}</h1>
          <div style={{ fontSize: 12, color: 'var(--color-text-tertiary)', marginTop: 2 }}>
            {a.tipo_processo} · Loop {a.loops_contraditorio}/{a.max_loops} · {a.intervencoes.length} intervenções · {a.provas.length} provas
          </div>
        </div>
        {a.fase_actual === 'decisao' && !a.decisao && (
          <button onClick={proferirDecisao} disabled={carregando} style={{ padding: '7px 16px', background: '#c4960a', color: '#0a2342', border: 'none', borderRadius: 'var(--border-radius-md)', fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}>
            ⚖ Proferir decisão
          </button>
        )}
        <div style={{ display: 'flex', gap: 6 }}>
          <button onClick={abrirAtaHTML} title="Ata completa da sessão — imprimir ou guardar PDF"
            style={{ padding: '7px 12px', background: 'transparent', border: '0.5px solid #0a2342', borderRadius: 'var(--border-radius-md)', fontSize: 12, color: '#0a2342', cursor: 'pointer', fontFamily: 'inherit', whiteSpace: 'nowrap' }}>
            🖨 Ata / Imprimir
          </button>
          <button onClick={() => descarregarAta('txt')} title="Descarregar a ata em texto simples"
            style={{ padding: '7px 10px', background: 'transparent', border: '0.5px solid var(--color-border-secondary)', borderRadius: 'var(--border-radius-md)', fontSize: 12, color: 'var(--color-text-secondary)', cursor: 'pointer', fontFamily: 'inherit' }}>
            ⬇ .txt
          </button>
          <button onClick={() => descarregarAta('md')} title="Descarregar a ata em Markdown"
            style={{ padding: '7px 10px', background: 'transparent', border: '0.5px solid var(--color-border-secondary)', borderRadius: 'var(--border-radius-md)', fontSize: 12, color: 'var(--color-text-secondary)', cursor: 'pointer', fontFamily: 'inherit' }}>
            ⬇ .md
          </button>
        </div>
      </div>

      {erro && <div style={{ padding: '8px 12px', background: 'var(--color-background-danger)', border: '0.5px solid var(--color-border-danger)', borderRadius: 'var(--border-radius-md)', fontSize: 13, color: 'var(--color-text-danger)' }}>{erro}</div>}

      {/* Timeline de fases */}
      <div style={{ background: 'var(--color-background-primary)', border: '0.5px solid var(--color-border-tertiary)', borderRadius: 'var(--border-radius-lg)', padding: '12px 16px' }}>
        <div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-tertiary)', fontWeight: 500, marginBottom: 10 }}>Fase processual</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 0, flexWrap: 'wrap', rowGap: 8 }}>
          {FASES_ORDEM.map((fase, i) => {
            const passada = i < faseIdx; const actual = i === faseIdx
            return (
              <span key={fase} style={{ display: 'flex', alignItems: 'center' }}>
                <span style={{ fontSize: 11, padding: '3px 10px', borderRadius: 20, fontWeight: actual ? 600 : 400, background: passada ? 'var(--color-background-success)' : actual ? '#0a2342' : 'var(--color-background-secondary)', color: passada ? 'var(--color-text-success)' : actual ? '#fff' : 'var(--color-text-tertiary)', border: `0.5px solid ${actual ? '#0a2342' : 'var(--color-border-tertiary)'}` }}>
                  {FASE_LABELS[fase]}
                </span>
                {i < FASES_ORDEM.length - 1 && <span style={{ color: 'var(--color-text-tertiary)', fontSize: 10, margin: '0 2px' }}>›</span>}
              </span>
            )
          })}
        </div>
        <div style={{ marginTop: 8, fontSize: 12, color: 'var(--color-text-secondary)' }}>
          <strong>{FASE_LABELS[a.fase_actual]}:</strong> {a.fase_descricao}
          {a.aguarda_intervencao_de && (
            <span style={{ marginLeft: 8, fontSize: 11, padding: '2px 8px', borderRadius: 20, background: `${PAPEL_COR[a.aguarda_intervencao_de]}15`, color: PAPEL_COR[a.aguarda_intervencao_de], fontWeight: 500 }}>
              Aguarda: {PAPEL_LABEL[a.aguarda_intervencao_de]}
            </span>
          )}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 10, alignItems: 'start' }}>

        {/* Intervenções */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-tertiary)' }}>Debate ({a.intervencoes.length})</div>
          <div style={{ maxHeight: 400, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 6 }}>
            {a.intervencoes.length === 0 ? (
              <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--color-text-tertiary)', fontSize: 13, background: 'var(--color-background-primary)', borderRadius: 'var(--border-radius-lg)', border: '0.5px solid var(--color-border-tertiary)' }}>
                O juiz deve dar início à audiência
              </div>
            ) : a.intervencoes.map(iv => (
              <div key={iv.id} style={{ background: 'var(--color-background-primary)', border: `0.5px solid var(--color-border-tertiary)`, borderLeft: `3px solid ${PAPEL_COR[iv.papel] ?? '#ccc'}`, borderRadius: 'var(--border-radius-md)', padding: '10px 12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                  <span style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: PAPEL_COR[iv.papel] ?? 'var(--color-text-secondary)' }}>{PAPEL_LABEL[iv.papel]}</span>
                  <span style={{ fontSize: 10, color: 'var(--color-text-tertiary)' }}>· ronda {iv.ronda}</span>
                  {iv.normas_citadas.length > 0 && iv.normas_citadas.map(n => (
                    <span key={n} style={{ fontSize: 9, padding: '1px 5px', background: 'var(--color-background-info)', color: 'var(--color-text-info)', borderRadius: 3, fontWeight: 500 }}>{n}</span>
                  ))}
                </div>
                <div style={{ fontSize: 13, color: 'var(--color-text-primary)', lineHeight: 1.6 }}>{iv.conteudo}</div>
                <div style={{ fontSize: 9, color: 'var(--color-text-tertiary)', marginTop: 4, fontFamily: 'monospace' }}>#{iv.hash_integridade.slice(0, 12)}</div>
              </div>
            ))}
            <div ref={intervencaoRef} />
          </div>

          {/* Painel de nova intervenção */}
          {!a.decisao && a.estado !== 'concluida' && (
            <div style={{ background: 'var(--color-background-primary)', border: '0.5px solid var(--color-border-tertiary)', borderRadius: 'var(--border-radius-lg)', overflow: 'hidden' }}>
              <div style={{ padding: '8px 12px', borderBottom: '0.5px solid var(--color-border-tertiary)', display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {(a.participantes ?? []).map(p => (
                  <button key={p.papel} onClick={() => setPapelSeleccionado(p.papel as Papel)} style={{ padding: '3px 10px', borderRadius: 20, fontSize: 11, fontWeight: 500, cursor: 'pointer', fontFamily: 'inherit', border: '0.5px solid', borderColor: papelSeleccionado === p.papel ? PAPEL_COR[p.papel as Papel] : 'var(--color-border-secondary)', background: papelSeleccionado === p.papel ? `${PAPEL_COR[p.papel as Papel]}15` : 'transparent', color: papelSeleccionado === p.papel ? PAPEL_COR[p.papel as Papel] : 'var(--color-text-secondary)' }}>
                    {PAPEL_LABEL[p.papel as Papel]}
                  </button>
                ))}
              </div>
              <textarea value={textoIntervencao} onChange={e => setTextoIntervencao(e.target.value)} placeholder={`Escreva o argumento do ${PAPEL_LABEL[papelSeleccionado]}... (ou use IA abaixo)`} rows={3} style={{ width: '100%', padding: '8px 12px', fontFamily: 'inherit', fontSize: 13, background: 'transparent', border: 'none', resize: 'none', outline: 'none', color: 'var(--color-text-primary)' }} />
              <div style={{ padding: '6px 12px', borderTop: '0.5px solid var(--color-border-tertiary)', display: 'flex', gap: 6 }}>
                <button onClick={() => submeterIntervencao(false)} disabled={carregando || !textoIntervencao.trim()} style={{ padding: '5px 14px', background: PAPEL_COR[papelSeleccionado], color: '#fff', border: 'none', borderRadius: 'var(--border-radius-md)', fontSize: 12, fontWeight: 500, cursor: 'pointer', fontFamily: 'inherit', opacity: !textoIntervencao.trim() ? 0.5 : 1 }}>
                  Submeter ↗
                </button>
                <button onClick={() => submeterIntervencao(true)} disabled={carregando} style={{ padding: '5px 14px', background: 'var(--color-background-secondary)', border: '0.5px solid var(--color-border-secondary)', borderRadius: 'var(--border-radius-md)', fontSize: 12, cursor: 'pointer', fontFamily: 'inherit', color: 'var(--color-text-secondary)' }}>
                  <i className="ti ti-robot" aria-hidden="true" /> Gerar com IA
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Painel lateral: provas + decisão */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>

          {/* Provas */}
          <div style={{ background: 'var(--color-background-primary)', border: '0.5px solid var(--color-border-tertiary)', borderRadius: 'var(--border-radius-lg)', overflow: 'hidden' }}>
            <div style={{ padding: '8px 12px', borderBottom: '0.5px solid var(--color-border-tertiary)' }}>
              <span style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-secondary)' }}>Provas ({a.provas.length})</span>
            </div>
            <div style={{ padding: '0 12px', maxHeight: 180, overflowY: 'auto' }}>
              {a.provas.length === 0 ? (
                <div style={{ padding: '0.75rem 0', fontSize: 12, color: 'var(--color-text-tertiary)', textAlign: 'center' }}>Nenhuma prova apresentada</div>
              ) : a.provas.map(pr => (
                <div key={pr.id} style={{ padding: '6px 0', borderBottom: '0.5px solid var(--color-border-tertiary)', fontSize: 12 }}>
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <span style={{ fontSize: 10, color: PAPEL_COR[pr.apresentada_por] ?? 'var(--color-text-secondary)', fontWeight: 500 }}>{PAPEL_LABEL[pr.apresentada_por]}</span>
                    <span style={{ fontSize: 10, padding: '1px 5px', background: 'var(--color-background-secondary)', borderRadius: 3, color: 'var(--color-text-tertiary)' }}>{pr.tipo}</span>
                  </div>
                  <div style={{ color: 'var(--color-text-primary)', marginTop: 2 }}>{pr.descricao}</div>
                  {pr.nome_ficheiro && <div style={{ color: 'var(--color-text-tertiary)', fontSize: 11 }}>📎 {pr.nome_ficheiro}</div>}
                </div>
              ))}
            </div>
          </div>

          {/* Decisão */}
          {a.decisao && (
            <div style={{ background: '#0a2342', borderRadius: 'var(--border-radius-lg)', overflow: 'hidden' }}>
              <div style={{ padding: '10px 14px', borderBottom: '2px solid #c4960a' }}>
                <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', color: '#c4960a' }}>⚖ Decisão</span>
              </div>
              <div style={{ padding: 14 }}>
                <div style={{ fontSize: 13, fontWeight: 500, color: '#fff', marginBottom: 8 }}>{a.decisao.sumario}</div>
                <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.7)', lineHeight: 1.7, marginBottom: 10 }}>{a.decisao.dispositivo}</div>
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 8 }}>
                  {a.decisao.normas_aplicadas.map(n => (
                    <span key={n} style={{ fontSize: 10, padding: '2px 6px', background: 'rgba(196,150,10,0.2)', color: '#e8b820', borderRadius: 3, fontWeight: 500 }}>{n}</span>
                  ))}
                </div>
                <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)' }}>Recursos: {a.decisao.recursos_possiveis.join(' · ')}</div>
              </div>
            </div>
          )}

          {/* Participantes */}
          <div style={{ background: 'var(--color-background-primary)', border: '0.5px solid var(--color-border-tertiary)', borderRadius: 'var(--border-radius-lg)', padding: '10px 12px' }}>
            <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-tertiary)', marginBottom: 8 }}>Participantes</div>
            {(a.participantes ?? []).map(p => (
              <div key={p.papel} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0', fontSize: 12 }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: PAPEL_COR[p.papel as Papel], flexShrink: 0 }} />
                <span style={{ color: 'var(--color-text-secondary)' }}>{p.nome}</span>
                <span style={{ fontSize: 10, color: 'var(--color-text-tertiary)', marginLeft: 'auto' }}>{PAPEL_LABEL[p.papel as Papel]}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
