/**
 * Os meus casos — SNAJI
 *
 * Histórico persistente dos casos instruídos pelo utilizador:
 * lista (mais recentes primeiro) → detalhe com Ficha de Factos, alertas
 * e todas as análises de cenários feitas ao longo do tempo.
 * Daqui pode lançar-se nova análise sobre um caso antigo — que fica
 * igualmente guardada no histórico.
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BotoesImprimir, DocumentoImprimivel } from '../utils/imprimir'
import { api, tratarErroAPI } from '../services/api'

interface CasoResumo {
  caso_id: string
  titulo: string
  criado_em: string
  areas: string[]
  papel: string
  numero_processo?: string
  n_alertas: number
  n_analises: number
}

interface AnaliseGuardada {
  analisado_em: string
  perspetiva?: string
  convergencia: boolean
  sintese_cidada: string
  cenarios: { titulo: string; solidez: string; fundamentacao_normas: string[] }[]
}

interface AnaliseJuridica {
  analisado_em: string
  qualificacao_juridica: string
  conclusao: string
  audit?: { modelo?: string; grounded?: boolean }
}

interface CasoCompleto extends CasoResumo {
  relato: string
  texto_para_analise: string
  alertas: { gravidade: string; mensagem_cidada: string }[]
  ficha: Record<string, unknown>
  analises_cenarios: AnaliseGuardada[]
  analises_juridicas?: AnaliseJuridica[]
}

const NOME_AREA: Record<string, string> = {
  laboral: 'Trabalho', penal: 'Penal', civil: 'Civil', consumo: 'Consumo',
  familia: 'Família', dados_pessoais: 'Dados pessoais', administrativo: 'Administrativo',
}
const NOME_PAPEL: Record<string, string> = {
  demandante: 'A apresentar queixa/reclamação', demandado: 'A defender-se de um processo',
}

export default function PaginaMeusCasos() {
  const navigate = useNavigate()
  const [casos, setCasos] = useState<CasoResumo[]>([])
  const [caso, setCaso] = useState<CasoCompleto | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(false)

  const carregarLista = async () => {
    setCarregando(true); setErro(null)
    try { setCasos((await api.get<CasoResumo[]>('/casos')).data) }
    catch (e) { setErro(tratarErroAPI(e)) }
    finally { setCarregando(false) }
  }

  const abrir = async (id: string) => {
    setCarregando(true); setErro(null)
    try { setCaso((await api.get<CasoCompleto>(`/casos/${id}`)).data) }
    catch (e) { setErro(tratarErroAPI(e)) }
    finally { setCarregando(false) }
  }

  useEffect(() => { carregarLista() }, [])

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
  const dataPt = (iso: string) =>
    new Date(iso).toLocaleDateString('pt-PT', { day: 'numeric', month: 'long', year: 'numeric' }) +
    ' às ' + new Date(iso).toLocaleTimeString('pt-PT', { hour: '2-digit', minute: '2-digit' })

  // ── Detalhe de um caso ────────────────────────────────────────────────
  if (caso) {
    const docCaso: DocumentoImprimivel = {
      titulo: caso.titulo,
      subtitulo: `Áreas: ${caso.areas.join(', ')}${caso.papel ? ' · ' + (NOME_PAPEL[caso.papel] ?? caso.papel) : ''}`,
      meta: [`Instruído a ${dataPt(caso.criado_em)}`],
      seccoes: [
        { titulo: 'Relato', paragrafos: [caso.relato] },
        ...(caso.alertas.length ? [{ titulo: 'Alertas', itens: caso.alertas.map(a => a.mensagem_cidada) }] : []),
        ...(caso.analises_juridicas?.length ? [{
          titulo: 'Análises jurídicas',
          paragrafos: caso.analises_juridicas.map(a => `${a.qualificacao_juridica}\n${a.conclusao}`),
        }] : []),
        ...caso.analises_cenarios.map((an, i) => ({
          titulo: `Análise de cenários ${i + 1} (${an.convergencia ? 'convergente' : 'em confronto'})`,
          paragrafos: [an.sintese_cidada],
          itens: an.cenarios.map(c => `${c.titulo} (solidez ${c.solidez}) — ${c.fundamentacao_normas.map(n => n.replace('-',' art. ')).join(', ')}`),
        })),
      ],
      rodape: 'Apoio à decisão gerado pelo SNAJI — sem valor oficial. Não substitui aconselhamento jurídico profissional.',
    }

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.9rem', maxWidth: 760 }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
        <button onClick={() => setCaso(null)} style={{
          alignSelf: 'flex-start', background: 'transparent', border: 'none', cursor: 'pointer',
          fontFamily: 'inherit', fontSize: 12.5, color: 'var(--color-text-secondary)', padding: 0,
        }}>← Todos os casos</button>
        <div style={{ marginLeft: 'auto' }}><BotoesImprimir doc={docCaso} nomeFicheiro={`caso-${caso.caso_id.slice(0,8)}`} /></div>
        </div>

        <h1 style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 21, fontWeight: 500, lineHeight: 1.3 }}>
          {caso.titulo}
        </h1>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
          {caso.areas.map(a => <span key={a} style={etiqueta}>{NOME_AREA[a] ?? a}</span>)}
          {caso.papel && <span style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>{NOME_PAPEL[caso.papel] ?? ''}</span>}
          <span style={{ fontSize: 12, color: 'var(--color-text-tertiary)', marginLeft: 'auto' }}>
            Instruído a {dataPt(caso.criado_em)}
          </span>
        </div>

        {caso.alertas.length > 0 && (
          <div style={{ ...cartao, borderLeft: '3px solid #8a1d1d' }}>
            <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', color: '#8a1d1d', marginBottom: 6 }}>
              Alertas registados na instrução
            </div>
            {caso.alertas.map((al, i) => (
              <div key={i} style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--color-text-primary)', marginBottom: 4 }}>
                {al.mensagem_cidada}
              </div>
            ))}
          </div>
        )}

        <div style={cartao}>
          <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-tertiary)', marginBottom: 6 }}>
            O relato original
          </div>
          <div style={{ fontSize: 13.5, lineHeight: 1.65, color: 'var(--color-text-primary)', whiteSpace: 'pre-wrap' }}>{caso.relato}</div>
        </div>

        {(caso.analises_juridicas?.length ?? 0) > 0 && (
          <>
            <h2 style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 17, fontWeight: 500 }}>
              Análises jurídicas ({caso.analises_juridicas!.length})
            </h2>
            {[...caso.analises_juridicas!].reverse().map((aj, i) => (
              <div key={i} style={cartao}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <span style={etiqueta}>{aj.audit?.grounded ? 'Fundamentada no corpus' : 'Análise'}</span>
                  <span style={{ fontSize: 11.5, color: 'var(--color-text-tertiary)', marginLeft: 'auto' }}>{dataPt(aj.analisado_em)}</span>
                </div>
                <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>{aj.qualificacao_juridica}</div>
                <div style={{ fontSize: 12.5, lineHeight: 1.6, color: 'var(--color-text-secondary)' }}>{aj.conclusao}</div>
              </div>
            ))}
          </>
        )}

        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
          <h2 style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 17, fontWeight: 500 }}>
            Análises deste caso ({caso.analises_cenarios.length})
          </h2>
          <button
            onClick={() => navigate('/cenarios', { state: { texto: caso.texto_para_analise, caso_id: caso.caso_id } })}
            style={{
              marginLeft: 'auto', padding: '7px 14px', background: '#0a2342', color: '#fff',
              border: 'none', borderRadius: 'var(--border-radius-md)', fontSize: 12.5,
              fontWeight: 500, cursor: 'pointer', fontFamily: 'inherit',
            }}
          >
            Nova análise deste caso ↗
          </button>
          <button
            onClick={() => navigate('/cenarios', { state: { texto: caso.texto_para_analise, caso_id: caso.caso_id, contraditorio: true } })}
            title="Gera os cenários adotando a perspetiva da parte contrária — para preparar a contestação que virá"
            style={{
              padding: '7px 14px', background: 'transparent', color: '#7a3b0a',
              border: '0.5px solid #7a3b0a', borderRadius: 'var(--border-radius-md)',
              fontSize: 12.5, fontWeight: 500, cursor: 'pointer', fontFamily: 'inherit',
            }}
          >
            ⇄ Analisar pelo lado contrário
          </button>
        </div>

        {caso.analises_cenarios.length === 0 && (
          <div style={{ fontSize: 13, color: 'var(--color-text-tertiary)' }}>
            Ainda sem análises guardadas — use o botão acima para gerar a primeira.
          </div>
        )}
        {[...caso.analises_cenarios].reverse().map((an, i) => (
          <div key={i} style={cartao}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <span style={{
                ...etiqueta,
                background: an.convergencia ? 'var(--color-background-success)' : 'var(--color-background-info)',
                color: an.convergencia ? 'var(--color-text-success)' : 'var(--color-text-info)',
              }}>
                {an.convergencia ? 'Abordagens convergentes' : 'Leituras em confronto'}
              </span>
              {an.perspetiva === 'contraparte' && (
                <span style={{ ...etiqueta, background: '#f7ead9', color: '#7a3b0a' }}>⇄ Contraditório</span>
              )}
              <span style={{ fontSize: 11.5, color: 'var(--color-text-tertiary)', marginLeft: 'auto' }}>{dataPt(an.analisado_em)}</span>
            </div>
            <div style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--color-text-primary)', marginBottom: 8 }}>{an.sintese_cidada}</div>
            {an.cenarios.map((c, j) => (
              <div key={j} style={{ fontSize: 12.5, color: 'var(--color-text-secondary)', lineHeight: 1.55 }}>
                • {c.titulo} <em>(solidez {c.solidez})</em> — {c.fundamentacao_normas.map(n => n.replace('-', ' art. ')).join(', ')}
              </div>
            ))}
          </div>
        ))}
      </div>
    )
  }

  // ── Lista de casos ────────────────────────────────────────────────────
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.9rem', maxWidth: 760 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
        <h1 style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 22, fontWeight: 500 }}>Os meus casos</h1>
        <small style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>
          Cada instrução concluída fica aqui guardada, com todas as análises que lhe fizer.
        </small>
      </div>

      {erro && <div style={{ ...cartao, borderLeft: '3px solid var(--color-text-danger)', fontSize: 13 }}>{erro}</div>}
      {!carregando && casos.length === 0 && !erro && (
        <div style={cartao}>
          <div style={{ fontSize: 13.5, lineHeight: 1.65, color: 'var(--color-text-secondary)' }}>
            Ainda não tem casos guardados. Comece por instruir um caso em <strong>Instrução do caso</strong> —
            ao concluir, ele aparecerá aqui automaticamente e poderá voltar-lhe quando quiser.
          </div>
        </div>
      )}

      {casos.map(c => (
        <div
          key={c.caso_id}
          onClick={() => abrir(c.caso_id)}
          style={{ ...cartao, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 12 }}
        >
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 13.5, fontWeight: 500, color: 'var(--color-text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {c.titulo}
            </div>
            <div style={{ fontSize: 11.5, color: 'var(--color-text-tertiary)', marginTop: 3 }}>
              {c.numero_processo ? `Proc. ${c.numero_processo} · ` : ''}{new Date(c.criado_em).toLocaleDateString('pt-PT', { day: 'numeric', month: 'long', year: 'numeric' })}
              {' · '}{c.n_analises} análise{c.n_analises === 1 ? '' : 's'}
              {c.n_alertas > 0 && <span style={{ color: '#8a1d1d' }}>{' · '}{c.n_alertas} alerta{c.n_alertas === 1 ? '' : 's'}</span>}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 5, flexShrink: 0 }}>
            {c.areas.map(a => <span key={a} style={etiqueta}>{NOME_AREA[a] ?? a}</span>)}
          </div>
          <span style={{ color: 'var(--color-text-tertiary)', fontSize: 15, flexShrink: 0 }}>›</span>
        </div>
      ))}
    </div>
  )
}
