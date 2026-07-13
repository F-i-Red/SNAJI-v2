/**
 * Compilador de Dossiê — SNAJI (advogado e magistrado)
 *
 * Arrastam-se vários documentos de um processo (petição, contestação, sentença,
 * requerimentos) e o SNAJI organiza-os: identifica o papel de cada peça, ordena
 * pela marcha processual, e consolida as citações — assinalando as inexistentes.
 */

import { useState } from 'react'
import { api, tratarErroAPI } from '../services/api'
import { imprimirDocumento, descarregarTxt, DocumentoImprimivel } from '../utils/imprimir'

interface DocDossie {
  nome_ficheiro: string
  tipo: string
  papel: string
  ordem: number
  num_paginas: number
  resumo: string
  citacoes_validas: string[]
  citacoes_invalidas: string[]
  prazos: string[]
}
interface Dossie {
  num_documentos: number
  total_paginas: number
  documentos: DocDossie[]
  citacoes_validas_unicas: string[]
  citacoes_invalidas_unicas: string[]
  total_citacoes_invalidas: number
  avisos: string[]
}

export default function PaginaDossie() {
  const [dossie, setDossie] = useState<Dossie | null>(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [arrastar, setArrastar] = useState(false)

  const compilar = async (files: FileList) => {
    if (!files.length) return
    setCarregando(true); setErro(null); setDossie(null)
    try {
      const fd = new FormData()
      Array.from(files).forEach(f => fd.append('ficheiros', f))
      const r = await api.post<Dossie>('/dossie/compilar', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setDossie(r.data)
    } catch (e) { setErro(tratarErroAPI(e)) }
    finally { setCarregando(false) }
  }

  const cartao: React.CSSProperties = {
    background: 'var(--color-background-primary)',
    border: '0.5px solid var(--color-border-tertiary)',
    borderRadius: 'var(--border-radius-lg)', padding: '14px 16px',
  }

  const docImprimivel = (): DocumentoImprimivel | null => {
    if (!dossie) return null
    return {
      titulo: 'Dossiê do processo',
      subtitulo: `${dossie.num_documentos} documentos · ${dossie.total_paginas} páginas`,
      meta: [`Compilado pelo SNAJI em ${new Date().toLocaleDateString('pt-PT')}`],
      seccoes: [
        ...dossie.documentos.map((d, i) => ({
          titulo: `${i + 1}. ${d.papel} — ${d.tipo}`,
          paragrafos: [d.resumo].filter(Boolean),
          itens: [
            ...(d.citacoes_validas.length ? [`Citações verificadas: ${d.citacoes_validas.join(', ')}`] : []),
            ...(d.citacoes_invalidas.length ? [`Citações a verificar: ${d.citacoes_invalidas.join(', ')}`] : []),
            ...d.prazos,
          ],
        })),
        ...(dossie.citacoes_invalidas_unicas.length ? [{
          titulo: 'Citações a verificar em todo o dossiê',
          itens: dossie.citacoes_invalidas_unicas,
        }] : []),
      ],
      rodape: 'Dossiê organizado pelo SNAJI — apoio ao trabalho jurídico, sem valor oficial. A ordenação segue a marcha processual típica; confirmar caso a caso.',
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: 820 }}>
      <div>
        <h1 style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 22, fontWeight: 500 }}>
          Compilador de dossiê
        </h1>
        <small style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>
          Largue vários documentos de um processo — o SNAJI identifica o papel de
          cada peça, ordena-os pela marcha processual e consolida as citações.
        </small>
      </div>

      <div
        onDragOver={e => { e.preventDefault(); setArrastar(true) }}
        onDragLeave={() => setArrastar(false)}
        onDrop={e => { e.preventDefault(); setArrastar(false); if (e.dataTransfer.files.length) compilar(e.dataTransfer.files) }}
        onClick={() => document.getElementById('docs-dossie')?.click()}
        style={{
          border: `2px dashed ${arrastar ? '#0a2342' : 'var(--color-border-secondary)'}`,
          borderRadius: 'var(--border-radius-lg)', padding: '32px 20px', textAlign: 'center',
          cursor: 'pointer', background: arrastar ? 'var(--color-background-info)' : 'transparent',
        }}
      >
        <div style={{ fontSize: 28, marginBottom: 6 }}>🗂️</div>
        <div style={{ fontSize: 14, fontWeight: 500 }}>
          {carregando ? 'A organizar o dossiê…' : 'Arraste os documentos do processo (vários de uma vez)'}
        </div>
        <div style={{ fontSize: 12, color: 'var(--color-text-tertiary)', marginTop: 4 }}>
          PDF, Word ou texto — petição, contestação, sentença, requerimentos…
        </div>
        <input id="docs-dossie" type="file" accept=".pdf,.docx,.txt,.jpg,.jpeg,.png,.tif,.tiff,.bmp,.webp" multiple style={{ display: 'none' }}
          onChange={e => e.target.files && compilar(e.target.files)} />
      </div>

      {erro && <div style={{ ...cartao, borderLeft: '3px solid var(--color-text-danger)', fontSize: 13 }}>{erro}</div>}

      {dossie && (
        <>
          <div style={{ ...cartao, display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: 200 }}>
              <div style={{ fontSize: 15, fontWeight: 500 }}>{dossie.num_documentos} documentos organizados</div>
              <div style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>
                {dossie.total_paginas} páginas · {dossie.citacoes_validas_unicas.length} normas verificadas
                {dossie.total_citacoes_invalidas > 0 && ` · ${dossie.total_citacoes_invalidas} a verificar`}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <button onClick={() => imprimirDocumento(docImprimivel()!)} style={{ padding: '7px 12px', background: 'transparent', border: '0.5px solid #0a2342', borderRadius: 'var(--border-radius-md)', fontSize: 12, color: '#0a2342', cursor: 'pointer', fontFamily: 'inherit' }}>🖨 Imprimir</button>
              <button onClick={() => descarregarTxt(docImprimivel()!)} style={{ padding: '7px 12px', background: 'transparent', border: '0.5px solid var(--color-border-secondary)', borderRadius: 'var(--border-radius-md)', fontSize: 12, color: 'var(--color-text-secondary)', cursor: 'pointer', fontFamily: 'inherit' }}>⬇ .txt</button>
            </div>
          </div>

          {dossie.avisos.map((a, i) => (
            <div key={i} style={{ ...cartao, borderLeft: '3px solid #c4960a', fontSize: 13 }}>⚠ {a}</div>
          ))}

          {/* Linha do tempo do processo */}
          <div style={cartao}>
            <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-tertiary)', marginBottom: 12 }}>
              Marcha processual (ordenada)
            </div>
            {dossie.documentos.map((d, i) => (
              <div key={i} style={{ display: 'flex', gap: 12, marginBottom: 14, paddingBottom: 14, borderBottom: i < dossie.documentos.length - 1 ? '0.5px solid var(--color-border-tertiary)' : 'none' }}>
                <div style={{ flexShrink: 0, width: 26, height: 26, borderRadius: '50%', background: '#0a2342', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 600 }}>{i + 1}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
                    <span style={{ fontWeight: 600, fontSize: 13.5, color: '#0a2342' }}>{d.papel}</span>
                    <span style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>{d.tipo}</span>
                    <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)' }}>· {d.nome_ficheiro}</span>
                  </div>
                  {d.resumo && <div style={{ fontSize: 12.5, color: 'var(--color-text-secondary)', marginTop: 3, lineHeight: 1.5 }}>{d.resumo}</div>}
                  <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginTop: 5 }}>
                    {d.citacoes_validas.map(c => (
                      <span key={c} style={{ fontSize: 11, padding: '1px 7px', borderRadius: 10, background: 'var(--color-background-success)', color: 'var(--color-text-success)' }}>{c.replace('-', ' art. ')}</span>
                    ))}
                    {d.citacoes_invalidas.map(c => (
                      <span key={c} style={{ fontSize: 11, padding: '1px 7px', borderRadius: 10, background: '#f5dede', color: '#8a1d1d' }}>{c.replace('-', ' art. ')} ⚠</span>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      <div style={{ fontSize: 11.5, lineHeight: 1.55, color: 'var(--color-text-tertiary)', borderTop: '0.5px solid var(--color-border-tertiary)', paddingTop: 10 }}>
        A ordenação segue a marcha processual típica (petição/acusação → contestação/defesa → decisão).
        O SNAJI é apoio ao trabalho jurídico — confirme sempre a organização caso a caso.
      </div>
    </div>
  )
}
