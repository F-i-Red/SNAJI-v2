/**
 * Jurisprudência — SNAJI
 *
 * O palco dos Acórdãos Uniformizadores reais do STJ:
 *  - pesquisa livre por factos ou questão jurídica (BM25 sobre a base local)
 *  - cruzamento inverso: "que acórdãos interpretam o art. X do diploma Y?"
 *  - as normas citadas em cada acórdão são clicáveis e disparam o cruzamento
 *
 * Todos os acórdãos exibidos são reais, com o segmento uniformizador integral
 * e ligação à fonte oficial.
 */

import { useState } from 'react'
import { api, tratarErroAPI } from '../services/api'

interface Acordao {
  id: string
  tribunal: string
  numero_processo: string
  data: string
  sumario: string
  descritores: string[]
  normas_citadas: string[]
  url: string
}

const DIPLOMAS = ['CT', 'CC', 'CPC', 'CP', 'CPP', 'CRP', 'CPA', 'CIRE', 'CSC', 'LDC']

const NOME_DIPLOMA: Record<string, string> = {
  CT: 'Código do Trabalho', CC: 'Código Civil', CPC: 'Cód. Processo Civil',
  CP: 'Código Penal', CPP: 'Cód. Processo Penal', CRP: 'Constituição',
  CPA: 'Cód. Proc. Administrativo', CIRE: 'CIRE', CSC: 'Cód. Sociedades', LDC: 'Lei Defesa Consumidor',
}

const EXEMPLOS = [
  'despedimento ilícito retribuições intercalares',
  'prescrição prestações de crédito',
  'ocupação ilícita de imóvel indemnização',
  'investigação de paternidade prazo',
]

export default function PaginaJurisprudencia() {
  const [query, setQuery] = useState('')
  const [arrastar, setArrastar] = useState(false)
  const [porDoc, setPorDoc] = useState<any | null>(null)
  const [aLerDoc, setALerDoc] = useState(false)
  const [diploma, setDiploma] = useState('CT')
  const [artigo, setArtigo] = useState('')
  const [acordaos, setAcordaos] = useState<Acordao[] | null>(null)
  const [contexto, setContexto] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(false)
  const [expandido, setExpandido] = useState<string | null>(null)

  const pesquisar = async (q?: string) => {
    const termo = (q ?? query).trim()
    if (termo.length < 3) return
    setQuery(termo); setCarregando(true); setErro(null)
    try {
      const r = await api.get(`/integracoes/jurisprudencia?q=${encodeURIComponent(termo)}&top_k=6`)
      setAcordaos(r.data.acordaos)
      setContexto(`Pesquisa: "${termo}"`)
    } catch (e) { setErro(tratarErroAPI(e)) }
    finally { setCarregando(false) }
  }

  const porNorma = async (dip?: string, art?: string) => {
    const d = dip ?? diploma
    // tolerância ao erro humano: "art. 498.º" → "498"
    const a = (art ?? artigo).trim().toLowerCase()
      .replace(/artigo|art\.?/g, '').replace(/\.?º|°/g, '').trim().replace(/\.$/, '').toUpperCase()
    if (!a) return
    setDiploma(d); setArtigo(a); setCarregando(true); setErro(null)
    try {
      const r = await api.get(`/integracoes/jurisprudencia/norma?diploma=${d}&artigo=${encodeURIComponent(a)}`)
      setAcordaos(r.data.acordaos)
      setContexto(`Acórdãos que interpretam o art. ${a}.º do ${NOME_DIPLOMA[d] ?? d}`)
    } catch (e) { setErro(tratarErroAPI(e)) }
    finally { setCarregando(false) }
  }

  const cruzarDocumentos = async (files: FileList) => {
    if (!files.length) return
    setALerDoc(true); setErro(null); setPorDoc(null)
    try {
      const fd = new FormData()
      Array.from(files).forEach(f => fd.append('ficheiros', f))
      const r = await api.post('/integracoes/jurisprudencia/por-documento', fd,
        { headers: { 'Content-Type': 'multipart/form-data' } })
      setPorDoc(r.data)
    } catch (e) { setErro(tratarErroAPI(e)) }
    finally { setALerDoc(false) }
  }

  const clicarNorma = (ref: string) => {
    const [d, a] = ref.split('-')
    if (d && a) porNorma(d, a)
  }

  // ── Estilos (design system SNAJI) ─────────────────────────────────────
  const cartao: React.CSSProperties = {
    background: 'var(--color-background-primary)',
    border: '0.5px solid var(--color-border-tertiary)',
    borderRadius: 'var(--border-radius-lg)',
    padding: '14px 16px',
  }
  const etiqueta: React.CSSProperties = {
    fontSize: 11, padding: '2px 9px', borderRadius: 20,
    background: 'var(--color-background-info)', color: 'var(--color-text-info)', fontWeight: 500,
  }
  const botao: React.CSSProperties = {
    padding: '8px 16px', background: '#0a2342', color: '#fff', border: 'none',
    borderRadius: 'var(--border-radius-md)', fontSize: 13, fontWeight: 500,
    cursor: 'pointer', fontFamily: 'inherit',
  }

  const eAUJ = (a: Acordao) =>
    a.descritores.some(d => d.toUpperCase().includes('UNIFORMIZA'))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: 780 }}>
      <div>
        <h1 style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 22, fontWeight: 500 }}>
          Jurisprudência
        </h1>
        <small style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>
          Acórdãos Uniformizadores reais do Supremo Tribunal de Justiça, com o segmento
          uniformizador integral e cruzamento com as normas do corpus.
        </small>
      </div>

      {/* Pesquisa livre */}
      <div style={cartao}>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            type="text" value={query}
            placeholder="Descreva os factos ou a questão jurídica…"
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && pesquisar()}
            style={{ flex: 1 }}
          />
          <button style={botao} disabled={carregando || query.trim().length < 3} onClick={() => pesquisar()}>
            Pesquisar
          </button>
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8, alignItems: 'center' }}>
          <span style={{ fontSize: 11.5, color: 'var(--color-text-tertiary)' }}>Experimente:</span>
          {EXEMPLOS.map(ex => (
            <button key={ex} onClick={() => pesquisar(ex)} style={{
              ...etiqueta, border: 'none', cursor: 'pointer', fontFamily: 'inherit',
              background: 'var(--color-background-secondary)', color: 'var(--color-text-secondary)',
            }}>
              {ex}
            </button>
          ))}
        </div>
      </div>

      {/* Cruzamento por DOCUMENTO — largar a peça e obter jurisprudência aplicável */}
      <div
        onDragOver={e => { e.preventDefault(); setArrastar(true) }}
        onDragLeave={() => setArrastar(false)}
        onDrop={e => { e.preventDefault(); setArrastar(false); if (e.dataTransfer.files.length) cruzarDocumentos(e.dataTransfer.files) }}
        onClick={() => document.getElementById('docs-juris')?.click()}
        style={{
          border: `2px dashed ${arrastar ? '#0a2342' : 'var(--color-border-secondary)'}`,
          borderRadius: 'var(--border-radius-lg)', padding: '18px', textAlign: 'center', cursor: 'pointer',
          background: arrastar ? 'var(--color-background-info)' : 'transparent', fontSize: 13, color: 'var(--color-text-secondary)',
        }}
      >
        {aLerDoc ? 'A ler os documentos e a cruzar as normas…'
          : '📎 Largue aqui uma peça (PDF, Word, texto) — o SNAJI extrai as normas citadas e mostra os acórdãos do STJ relevantes para cada uma.'}
        <input id="docs-juris" type="file" accept=".pdf,.docx,.txt,.jpg,.jpeg,.png,.tif,.tiff,.bmp,.webp" multiple style={{ display: 'none' }}
          onChange={e => e.target.files && cruzarDocumentos(e.target.files)} />
      </div>

      {/* Resultados do cruzamento por documento */}
      {porDoc && (
        <div style={cartao}>
          <div style={{ fontSize: 13, marginBottom: 10 }}>
            <strong>{porDoc.total_normas}</strong> norma(s) detetada(s) no documento;{' '}
            <strong>{porDoc.normas_com_acordaos}</strong> com acórdãos do STJ.
          </div>
          {porDoc.resultados.filter((r: any) => r.total_acordaos > 0).map((r: any) => (
            <div key={r.norma} style={{ marginBottom: 12, paddingBottom: 12, borderBottom: '0.5px solid var(--color-border-tertiary)' }}>
              <div style={{ fontWeight: 600, fontSize: 13, color: '#0a2342', marginBottom: 4 }}>
                {r.diploma} art. {r.artigo} — {r.total_acordaos} acórdão(s)
              </div>
              {r.acordaos.map((a: any) => (
                <div key={a.id} style={{ fontSize: 12.5, color: 'var(--color-text-secondary)', marginBottom: 4, paddingLeft: 8 }}>
                  <span style={{ fontFamily: 'monospace' }}>{a.numero_processo}</span> · {a.data}
                  {a.url && <> · <a href={a.url} target="_blank" rel="noreferrer" style={{ color: '#0a2342' }}>fonte ↗</a></>}
                </div>
              ))}
            </div>
          ))}
          {porDoc.normas_com_acordaos === 0 && (
            <div style={{ fontSize: 12.5, color: 'var(--color-text-tertiary)' }}>
              As normas detetadas não têm acórdãos uniformizadores na base atual. Normas encontradas: {porDoc.normas_encontradas.join(', ') || 'nenhuma'}.
            </div>
          )}
        </div>
      )}

      {/* Cruzamento por norma */}
      <div style={cartao}>
        <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-tertiary)', marginBottom: 8 }}>
          Que acórdãos interpretam uma norma?
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ fontSize: 13 }}>Artigo</span>
          <input type="text" value={artigo} placeholder="ex.: 498" onChange={e => setArtigo(e.target.value)}
                 onKeyDown={e => e.key === 'Enter' && porNorma()} style={{ width: 90 }} />
          <span style={{ fontSize: 13 }}>do</span>
          <select value={diploma} onChange={e => setDiploma(e.target.value)}>
            {DIPLOMAS.map(d => <option key={d} value={d}>{NOME_DIPLOMA[d] ?? d}</option>)}
          </select>
          <button style={botao} disabled={carregando || !artigo.trim()} onClick={() => porNorma()}>
            Cruzar
          </button>
        </div>
      </div>

      {erro && <div style={{ ...cartao, borderLeft: '3px solid var(--color-text-danger)', fontSize: 13 }}>{erro}</div>}

      {/* Resultados */}
      {acordaos !== null && (
        <>
          <div style={{ fontSize: 12.5, color: 'var(--color-text-secondary)' }}>
            {contexto} — <strong>{acordaos.length}</strong> resultado{acordaos.length === 1 ? '' : 's'}
          </div>
          {acordaos.length === 0 && (
            <div style={cartao}>
              <div style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--color-text-secondary)' }}>
                Sem acórdãos na base para esta pesquisa. O SNAJI só apresenta jurisprudência
                real e verificada — quando não há, di-lo com clareza em vez de inventar.
              </div>
            </div>
          )}
          {acordaos.map(a => (
            <div key={a.id} style={cartao}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                {eAUJ(a) && (
                  <span style={{ ...etiqueta, background: '#f5ead1', color: '#7a5c07' }}>★ Uniformização de Jurisprudência</span>
                )}
                <span style={{ ...etiqueta }}>{a.tribunal}</span>
                <span style={{ fontSize: 12, color: 'var(--color-text-tertiary)', marginLeft: 'auto' }}>{a.data}</span>
              </div>
              <div style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 16.5, fontWeight: 500, margin: '8px 0 4px' }}>
                {a.numero_processo}
              </div>
              <div style={{
                fontSize: 13, lineHeight: 1.65, color: 'var(--color-text-primary)', whiteSpace: 'pre-wrap',
                ...(expandido === a.id ? {} : { display: '-webkit-box', WebkitLineClamp: 4, WebkitBoxOrient: 'vertical' as const, overflow: 'hidden' }),
              }}>
                {a.sumario}
              </div>
              {a.sumario.length > 320 && (
                <button onClick={() => setExpandido(expandido === a.id ? null : a.id)} style={{
                  background: 'transparent', border: 'none', cursor: 'pointer', padding: 0,
                  fontFamily: 'inherit', fontSize: 12, color: '#0a2342', fontWeight: 600, marginTop: 4,
                }}>
                  {expandido === a.id ? '▾ Recolher' : '▸ Ler o segmento integral'}
                </button>
              )}
              <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginTop: 10, alignItems: 'center' }}>
                {a.normas_citadas.length > 0 && (
                  <span style={{ fontSize: 11.5, color: 'var(--color-text-tertiary)' }}>Interpreta:</span>
                )}
                {a.normas_citadas.map(n => (
                  <button key={n} onClick={() => clicarNorma(n)} title="Ver todos os acórdãos que interpretam esta norma"
                    style={{ ...etiqueta, border: 'none', cursor: 'pointer', fontFamily: 'inherit' }}>
                    {n.replace('-', ' art. ')}
                  </button>
                ))}
                {a.url && (
                  <a href={a.url} target="_blank" rel="noreferrer"
                     style={{ fontSize: 11.5, color: '#0a2342', marginLeft: 'auto' }}>
                    fonte oficial ↗
                  </a>
                )}
              </div>
            </div>
          ))}
        </>
      )}

      <div style={{
        fontSize: 11.5, lineHeight: 1.55, color: 'var(--color-text-tertiary)',
        borderTop: '0.5px solid var(--color-border-tertiary)', paddingTop: 10,
      }}>
        Base atual: Acórdãos Uniformizadores do STJ recolhidos e verificados manualmente
        (segmento integral; normas validadas contra o corpus). A cobertura alarga-se com o
        acesso institucional às bases do dgsi (IGFEJ).
      </div>
    </div>
  )
}
