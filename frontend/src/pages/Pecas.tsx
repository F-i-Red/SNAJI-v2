/**
 * Análise de Peças Processuais — SNAJI
 *
 * O assistente de litígio para advogado e magistrado: arrasta-se uma peça
 * (petição, contestação, sentença…) e o SNAJI verifica todas as citações
 * contra o corpus, deteta a estrutura, os prazos que a peça faz correr e
 * resume-a. As citações inexistentes surgem A VERMELHO.
 */

import { useState, useRef } from 'react'
import { api, tratarErroAPI } from '../services/api'
import { imprimirDocumento, descarregarTxt, DocumentoImprimivel } from '../utils/imprimir'

interface Citacao { norma: string; diploma: string; artigo: string; contexto: string }
interface Seccao { nome: string; presente: boolean; posicao: number }
interface Analise {
  nome_ficheiro: string
  num_paginas: number
  num_caracteres: number
  tipo_provavel: string
  resumo: string
  total_citacoes: number
  citacoes_validas: Citacao[]
  citacoes_invalidas: Citacao[]
  seccoes: Seccao[]
  prazos_desencadeados: string[]
  avisos: string[]
}

const NOME_SECCAO: Record<string, string> = {
  factos: 'Factos', direito: 'Direito', pedido: 'Pedido', prova: 'Prova',
}

export default function PaginaPecas() {
  const [analise, setAnalise] = useState<Analise | null>(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [arrastar, setArrastar] = useState(false)
  const [nomeFicheiro, setNomeFicheiro] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const enviar = async (file: File) => {
    setCarregando(true); setErro(null); setAnalise(null); setNomeFicheiro(file.name)
    try {
      const fd = new FormData()
      fd.append('ficheiro', file)
      const r = await api.post<Analise>('/pecas/analisar', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setAnalise(r.data)
    } catch (e) { setErro(tratarErroAPI(e)) }
    finally { setCarregando(false) }
  }

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault(); setArrastar(false)
    const f = e.dataTransfer.files?.[0]
    if (f) enviar(f)
  }

  const cartao: React.CSSProperties = {
    background: 'var(--color-background-primary)',
    border: '0.5px solid var(--color-border-tertiary)',
    borderRadius: 'var(--border-radius-lg)', padding: '14px 16px',
  }
  const titulo: React.CSSProperties = {
    fontSize: 11, fontWeight: 600, textTransform: 'uppercase',
    letterSpacing: '0.08em', color: 'var(--color-text-tertiary)', marginBottom: 10,
  }

  const docImprimivel = (): DocumentoImprimivel | null => {
    if (!analise) return null
    return {
      titulo: `Análise da peça: ${analise.nome_ficheiro}`,
      subtitulo: `${analise.tipo_provavel} · ${analise.num_paginas} páginas`,
      meta: [`Analisado pelo SNAJI em ${new Date().toLocaleDateString('pt-PT')}`],
      seccoes: [
        { titulo: 'Resumo', paragrafos: [analise.resumo] },
        ...(analise.citacoes_invalidas.length ? [{
          titulo: `⚠ Citações a verificar (${analise.citacoes_invalidas.length})`,
          itens: analise.citacoes_invalidas.map(c => `${c.diploma} art. ${c.artigo} — NÃO consta do corpus. Contexto: ${c.contexto}`),
        }] : []),
        { titulo: `Citações verificadas (${analise.citacoes_validas.length})`,
          itens: analise.citacoes_validas.map(c => `${c.diploma} art. ${c.artigo} ✓`) },
        ...(analise.prazos_desencadeados.length ? [{
          titulo: 'Prazos desencadeados', itens: analise.prazos_desencadeados,
        }] : []),
        { titulo: 'Estrutura detetada',
          itens: analise.seccoes.filter(s => s.presente).map(s => NOME_SECCAO[s.nome] ?? s.nome) },
      ],
      rodape: 'Análise gerada pelo SNAJI — apoio ao trabalho jurídico, sem valor oficial. A verificação de citações é feita contra o corpus atual; uma norma fora do corpus aparece como "a verificar" sem que isso signifique que não existe.',
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: 820 }}>
      <div>
        <h1 style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 22, fontWeight: 500 }}>
          Análise de peças
        </h1>
        <small style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>
          Arraste uma peça processual (PDF, Word ou texto) — o SNAJI lê-a por
          inteiro, verifica todas as citações contra o corpus e assinala os erros.
        </small>
      </div>

      {/* Zona de arrastar */}
      <div
        onDragOver={e => { e.preventDefault(); setArrastar(true) }}
        onDragLeave={() => setArrastar(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        style={{
          border: `2px dashed ${arrastar ? '#0a2342' : 'var(--color-border-secondary)'}`,
          borderRadius: 'var(--border-radius-lg)', padding: '32px 20px',
          textAlign: 'center', cursor: 'pointer',
          background: arrastar ? 'var(--color-background-info)' : 'transparent',
          transition: 'all 0.15s',
        }}
      >
        <div style={{ fontSize: 28, marginBottom: 6 }}>📄</div>
        <div style={{ fontSize: 14, color: 'var(--color-text-primary)', fontWeight: 500 }}>
          {carregando ? 'A analisar o documento…' : 'Arraste aqui a peça, ou clique para escolher'}
        </div>
        <div style={{ fontSize: 12, color: 'var(--color-text-tertiary)', marginTop: 4 }}>
          PDF, DOCX ou TXT · o documento é lido por inteiro, sem limite de páginas
        </div>
        <input ref={inputRef} type="file" accept=".pdf,.docx,.txt" style={{ display: 'none' }}
          onChange={e => { const f = e.target.files?.[0]; if (f) enviar(f) }} />
      </div>

      {erro && <div style={{ ...cartao, borderLeft: '3px solid var(--color-text-danger)', fontSize: 13 }}>{erro}</div>}

      {analise && (
        <>
          {/* Cabeçalho da análise + imprimir */}
          <div style={{ ...cartao, display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: 200 }}>
              <div style={{ fontSize: 15, fontWeight: 500 }}>{analise.tipo_provavel}</div>
              <div style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>
                {analise.nome_ficheiro} · {analise.num_paginas} páginas · {analise.total_citacoes} citações
              </div>
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <button onClick={() => imprimirDocumento(docImprimivel()!)} style={{ padding: '7px 12px', background: 'transparent', border: '0.5px solid #0a2342', borderRadius: 'var(--border-radius-md)', fontSize: 12, color: '#0a2342', cursor: 'pointer', fontFamily: 'inherit' }}>🖨 Imprimir</button>
              <button onClick={() => descarregarTxt(docImprimivel()!)} style={{ padding: '7px 12px', background: 'transparent', border: '0.5px solid var(--color-border-secondary)', borderRadius: 'var(--border-radius-md)', fontSize: 12, color: 'var(--color-text-secondary)', cursor: 'pointer', fontFamily: 'inherit' }}>⬇ .txt</button>
            </div>
          </div>

          {/* Avisos */}
          {analise.avisos.map((a, i) => (
            <div key={i} style={{ ...cartao, borderLeft: '3px solid #c4960a', fontSize: 13, color: 'var(--color-text-primary)' }}>
              ⚠ {a}
            </div>
          ))}

          {/* Resumo */}
          <div style={cartao}>
            <div style={titulo}>Resumo</div>
            <div style={{ fontSize: 13.5, lineHeight: 1.65, color: 'var(--color-text-primary)' }}>{analise.resumo}</div>
          </div>

          {/* Citações inválidas — A VERMELHO */}
          {analise.citacoes_invalidas.length > 0 && (
            <div style={{ ...cartao, borderLeft: '3px solid #8a1d1d' }}>
              <div style={{ ...titulo, color: '#8a1d1d' }}>
                ✘ Citações a verificar ({analise.citacoes_invalidas.length}) — não constam do corpus
              </div>
              {analise.citacoes_invalidas.map((c, i) => (
                <div key={i} style={{ marginBottom: 8, paddingBottom: 8, borderBottom: i < analise.citacoes_invalidas.length - 1 ? '0.5px solid var(--color-border-tertiary)' : 'none' }}>
                  <span style={{ fontWeight: 600, color: '#8a1d1d', fontSize: 13 }}>
                    {c.diploma} art. {c.artigo}
                  </span>
                  <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', marginTop: 2, fontStyle: 'italic' }}>{c.contexto}</div>
                </div>
              ))}
              <div style={{ fontSize: 11.5, color: 'var(--color-text-tertiary)', marginTop: 6 }}>
                Pode ser erro de citação da peça, ou uma norma de diploma ainda não incluído no corpus. Verificar caso a caso.
              </div>
            </div>
          )}

          {/* Citações válidas + estrutura + prazos */}
          <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))' }}>
            <div style={cartao}>
              <div style={{ ...titulo, color: '#1a7a3a' }}>✓ Citações verificadas ({analise.citacoes_validas.length})</div>
              <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                {analise.citacoes_validas.map((c, i) => (
                  <span key={i} style={{ fontSize: 11.5, padding: '2px 9px', borderRadius: 20, background: 'var(--color-background-success)', color: 'var(--color-text-success)', fontWeight: 500 }}>
                    {c.diploma} art. {c.artigo}
                  </span>
                ))}
                {analise.citacoes_validas.length === 0 && <span style={{ fontSize: 12.5, color: 'var(--color-text-tertiary)' }}>Nenhuma.</span>}
              </div>
            </div>
            <div style={cartao}>
              <div style={titulo}>Estrutura detetada</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {analise.seccoes.map(s => (
                  <div key={s.nome} style={{ fontSize: 12.5, display: 'flex', alignItems: 'center', gap: 6, color: s.presente ? 'var(--color-text-primary)' : 'var(--color-text-tertiary)' }}>
                    <span>{s.presente ? '●' : '○'}</span> {NOME_SECCAO[s.nome] ?? s.nome}
                    {s.presente && <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)' }}>(~{s.posicao}%)</span>}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Prazos desencadeados */}
          {analise.prazos_desencadeados.length > 0 && (
            <div style={{ ...cartao, borderLeft: '3px solid #0a2342' }}>
              <div style={titulo}>⏱ Prazos que esta peça pode desencadear</div>
              {analise.prazos_desencadeados.map((p, i) => (
                <div key={i} style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--color-text-primary)', marginBottom: 4 }}>{p}</div>
              ))}
              <div style={{ fontSize: 11.5, color: 'var(--color-text-tertiary)', marginTop: 6 }}>
                Prazos indicativos — confirmar sempre a contagem concreta no processo.
              </div>
            </div>
          )}
        </>
      )}

      <div style={{ fontSize: 11.5, lineHeight: 1.55, color: 'var(--color-text-tertiary)', borderTop: '0.5px solid var(--color-border-tertiary)', paddingTop: 10 }}>
        A verificação de citações é determinística, feita contra o corpus de 6.602 artigos.
        O SNAJI é apoio ao trabalho jurídico — não substitui a leitura profissional da peça.
      </div>
    </div>
  )
}
