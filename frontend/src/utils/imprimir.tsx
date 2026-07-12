/**
 * Utilitário de impressão e exportação — SNAJI
 *
 * Um único ponto para "imprimir / guardar PDF" e "descarregar .txt" a partir
 * de qualquer ecrã, para qualquer perfil. Recebe um documento estruturado
 * (título + secções) e trata da apresentação — os ecrãs só descrevem o que
 * querem imprimir, não o *como*.
 *
 * Uso:
 *   import { imprimirDocumento, descarregarTxt } from '../utils/imprimir'
 *   const doc = { titulo: 'Análise do caso', subtitulo: '...', seccoes: [...] }
 *   imprimirDocumento(doc)   // abre a janela de impressão do browser
 *   descarregarTxt(doc)      // descarrega um .txt
 */

export interface SeccaoDoc {
  titulo?: string
  // linhas de texto (parágrafos) e/ou itens de lista
  paragrafos?: string[]
  itens?: string[]
}

export interface DocumentoImprimivel {
  titulo: string
  subtitulo?: string
  meta?: string[]          // linhas de cabeçalho (data, perfil, etc.)
  seccoes: SeccaoDoc[]
  rodape?: string
}

// ── Texto simples (.txt) ────────────────────────────────────────────────

const ASSINATURA_SNAJI = 'SNAJI — Serviço Nacional de Assistência Jurídica Inteligente'

function contactosInstitucionais(): string {
  try {
    const raw = sessionStorage.getItem('snaji_contactos')
    if (!raw) return ''
    const c = JSON.parse(raw)
    const partes = [c.email_suporte, c.telefone_suporte, c.horario].filter(Boolean)
    return partes.length ? 'Apoio: ' + partes.join(' · ') : ''
  } catch { return '' }
}

export function documentoParaTexto(doc: DocumentoImprimivel): string {
  const L: string[] = []
  const sep = '='.repeat(66)
  L.push(sep)
  L.push(centrar(doc.titulo, 66))
  L.push(sep)
  if (doc.subtitulo) L.push(doc.subtitulo)
  ;(doc.meta ?? []).forEach(m => L.push(m))
  L.push('')
  for (const s of doc.seccoes) {
    if (s.titulo) {
      L.push(s.titulo.toUpperCase())
      L.push('-'.repeat(66))
    }
    for (const p of s.paragrafos ?? []) {
      quebrar(p, 66).forEach(l => L.push(l))
      L.push('')
    }
    for (const it of s.itens ?? []) {
      const linhas = quebrar(it, 62)
      L.push('  • ' + (linhas[0] ?? ''))
      linhas.slice(1).forEach(l => L.push('    ' + l))
    }
    if (s.itens?.length) L.push('')
  }
  L.push(sep)
  if (doc.rodape) {
    quebrar(doc.rodape, 66).forEach(l => L.push(l))
    L.push('')
  }
  L.push(ASSINATURA_SNAJI)
  const ct = contactosInstitucionais()
  if (ct) L.push(ct)
  return L.join('\n')
}

export function descarregarTxt(doc: DocumentoImprimivel, nomeFicheiro?: string) {
  const texto = documentoParaTexto(doc)
  const blob = new Blob([texto], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = (nomeFicheiro ?? slug(doc.titulo)) + '.txt'
  link.click()
  URL.revokeObjectURL(url)
}

// ── Impressão / PDF (via janela do browser) ─────────────────────────────

export function documentoParaHTML(doc: DocumentoImprimivel): string {
  const esc = (t: string) =>
    t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const seccoes = doc.seccoes.map(s => {
    const h = s.titulo ? `<h2>${esc(s.titulo)}</h2>` : ''
    const par = (s.paragrafos ?? []).map(p => `<p>${esc(p)}</p>`).join('')
    const it = s.itens?.length
      ? `<ul>${s.itens.map(i => `<li>${esc(i)}</li>`).join('')}</ul>`
      : ''
    return h + par + it
  }).join('')
  const meta = (doc.meta ?? []).map(m => esc(m)).join('<br>')
  return `<!DOCTYPE html><html lang="pt"><head><meta charset="utf-8">
<title>${esc(doc.titulo)}</title>
<style>
  body { font-family: Georgia, 'Times New Roman', serif; max-width: 800px;
         margin: 32px auto; padding: 0 24px; color: #1a1a1a; line-height: 1.6; }
  h1 { font-size: 24px; border-bottom: 2px solid #0a2342; padding-bottom: 8px; }
  h2 { font-size: 17px; color: #0a2342; margin-top: 22px; }
  .sub { color: #333; font-size: 15px; margin-top: 4px; }
  .meta { color: #555; font-size: 13px; margin: 6px 0 16px; }
  ul { padding-left: 20px; } li { margin: 3px 0; }
  .rodape { color: #777; font-size: 12px; margin-top: 24px;
            border-top: 1px solid #ddd; padding-top: 10px; font-style: italic; }
  @media print { .noprint { display: none; } body { margin: 0; } }
</style></head><body>
<button class="noprint" onclick="window.print()" style="float:right;padding:8px 16px;
  background:#0a2342;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:14px">
  🖨 Imprimir / Guardar PDF</button>
<h1>${esc(doc.titulo)}</h1>
${doc.subtitulo ? `<div class="sub">${esc(doc.subtitulo)}</div>` : ''}
${meta ? `<div class="meta">${meta}</div>` : ''}
${seccoes}
<div class="rodape">${doc.rodape ? esc(doc.rodape) + '<br>' : ''}${esc(ASSINATURA_SNAJI)}${contactosInstitucionais() ? '<br>' + esc(contactosInstitucionais()) : ''}</div>
</body></html>`
}

export function imprimirDocumento(doc: DocumentoImprimivel) {
  const html = documentoParaHTML(doc)
  const w = window.open('', '_blank')
  if (w) { w.document.write(html); w.document.close() }
}

// ── Auxiliares ──────────────────────────────────────────────────────────

function centrar(t: string, larg: number): string {
  const esp = Math.max(0, Math.floor((larg - t.length) / 2))
  return ' '.repeat(esp) + t
}

function quebrar(texto: string, larg: number): string[] {
  const palavras = String(texto).split(/\s+/)
  const linhas: string[] = []
  let atual = ''
  for (const p of palavras) {
    if ((atual + ' ' + p).trim().length > larg) {
      if (atual) linhas.push(atual)
      atual = p
    } else {
      atual = (atual + ' ' + p).trim()
    }
  }
  if (atual) linhas.push(atual)
  return linhas.length ? linhas : ['']
}

function slug(t: string): string {
  return t.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40) || 'documento'
}

// ── Componente de botões reutilizável ───────────────────────────────────

import React from 'react'

export function BotoesImprimir({ doc, nomeFicheiro }: { doc: DocumentoImprimivel; nomeFicheiro?: string }) {
  const base: React.CSSProperties = {
    padding: '7px 12px', borderRadius: 'var(--border-radius-md)', fontSize: 12,
    cursor: 'pointer', fontFamily: 'inherit', whiteSpace: 'nowrap',
  }
  return (
    <div style={{ display: 'flex', gap: 6 }}>
      <button onClick={() => imprimirDocumento(doc)} title="Imprimir ou guardar como PDF"
        style={{ ...base, background: 'transparent', border: '0.5px solid #0a2342', color: '#0a2342' }}>
        🖨 Imprimir
      </button>
      <button onClick={() => descarregarTxt(doc, nomeFicheiro)} title="Descarregar em texto simples"
        style={{ ...base, background: 'transparent', border: '0.5px solid var(--color-border-secondary)', color: 'var(--color-text-secondary)' }}>
        ⬇ .txt
      </button>
    </div>
  )
}
