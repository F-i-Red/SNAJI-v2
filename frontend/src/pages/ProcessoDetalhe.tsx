/**
 * Janela do processo.
 *
 * Reúne num só sítio o que estava disperso: a descrição do processo, as
 * análises já feitas, qual delas vale como apreciação corrente, e as que
 * foram postas de lado.
 *
 * Um processo em carteira precisa de uma apreciação estável. Antes, cada
 * regresso obrigava a repetir a análise e o processo ficava eternamente «por
 * ler»; e as leituras anteriores desapareciam, quando é justamente a
 * comparação entre elas que mostra como a apreciação evoluiu.
 *
 * Um caso pode ter várias análises — refeitas, do contraditório, com factos
 * novos — mas só uma é a activa. As outras ficam em apreciação ou no arquivo,
 * sempre recuperáveis.
 */
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, tratarErroAPI } from '../services/api'
import { BotoesImprimir, DocumentoImprimivel } from '../utils/imprimir'

interface CenarioResumo {
  titulo: string
  solidez: string
  sentido?: string
  fundamentacao_normas: string[]
}

interface Analise {
  analisado_em: string
  activa?: boolean
  perspetiva?: string
  convergencia: boolean
  sintese_tecnica?: string
  sintese_cidada?: string
  cenarios: CenarioResumo[]
  descartada_em?: string
  descarte_motivo?: string
}

interface Processo {
  id: string
  numero_interno: string
  tipo: string
  descricao: string
  assunto?: string
  estado: string
  nome_autor?: string
  nome_reu?: string
  caso_id_analise?: string | null
  prazos: { descricao: string; data_limite: string; urgente: boolean; cumprido: boolean }[]
}

const NOME_SOLIDEZ: Record<string, string> = {
  elevada: 'elevada', media: 'média', baixa: 'baixa',
}

const COR_SOLIDEZ: Record<string, string> = {
  elevada: '#1a7f37', media: '#b58900', baixa: '#c62828',
}

export default function ProcessoDetalhe() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [processo, setProcesso] = useState<Processo | null>(null)
  const [analises, setAnalises] = useState<Analise[]>([])
  const [arquivo, setArquivo] = useState<Analise[]>([])
  const [motivos, setMotivos] = useState<Record<string, string>>({})
  const [motivo, setMotivo] = useState('falhada')
  const [aDescartar, setADescartar] = useState<number | null>(null)
  const [verArquivo, setVerArquivo] = useState(false)
  const [comparar, setComparar] = useState<number[]>([])
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(false)

  const carregar = async () => {
    if (!id) return
    setCarregando(true)
    try {
      const p = (await api.get<Processo>(`/processos/${id}`)).data
      setProcesso(p)
      if (p.caso_id_analise) {
        const c = (await api.get(`/casos/${p.caso_id_analise}`)).data
        setAnalises(c.analises_cenarios ?? [])
        setArquivo(c.analises_cenarios_descartadas ?? [])
      } else {
        setAnalises([]); setArquivo([])
      }
    } catch (e) { setErro(tratarErroAPI(e)) }
    finally { setCarregando(false) }
  }

  useEffect(() => { carregar() /* eslint-disable-next-line */ }, [id])
  useEffect(() => {
    api.get('/casos/motivos-descarte').then(r => setMotivos(r.data)).catch(() => {})
  }, [])

  const caso = processo?.caso_id_analise

  const activar = async (i: number) => {
    if (!caso) return
    try { await api.post(`/casos/${caso}/analises/${i}/activar`); carregar() }
    catch (e) { setErro(tratarErroAPI(e)) }
  }

  const descartar = async (i: number) => {
    if (!caso) return
    try {
      await api.post(`/casos/${caso}/analises/${i}/descartar`, { motivo })
      setADescartar(null); carregar()
    } catch (e) { setErro(tratarErroAPI(e)) }
  }

  const restaurar = async (i: number) => {
    if (!caso) return
    try { await api.post(`/casos/${caso}/arquivo/${i}/restaurar`); carregar() }
    catch (e) { setErro(tratarErroAPI(e)) }
  }

  const analisar = (contraditorio = false) =>
    navigate('/cenarios', {
      state: {
        texto: processo?.descricao,
        caso_id: processo?.caso_id_analise ?? null,
        processo_id: processo?.id,
        contraditorio,
      },
    })

  const dataHora = (s: string) =>
    new Date(s).toLocaleString('pt-PT', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })

  const cartao: React.CSSProperties = {
    background: 'var(--color-background-primary)',
    border: '0.5px solid var(--color-border-tertiary)',
    borderRadius: 'var(--border-radius-lg)',
    padding: '14px 16px',
  }

  const docImprimivel = (): DocumentoImprimivel | null => {
    if (!processo) return null
    const activa = analises.find(a => a.activa) ?? analises[0]
    return {
      titulo: `Processo ${processo.numero_interno}`,
      subtitulo: processo.descricao,
      meta: [
        `Estado: ${processo.estado}`,
        `Analisado em ${activa ? dataHora(activa.analisado_em) : '—'}`,
      ],
      seccoes: [
        { titulo: 'Descrição do processo', paragrafos: [processo.descricao] },
        ...(activa ? [{
          titulo: 'Apreciação corrente',
          paragrafos: [
            activa.sintese_tecnica ?? activa.sintese_cidada ?? '',
            ...activa.cenarios.map(c =>
              `${c.titulo} — solidez ${NOME_SOLIDEZ[c.solidez] ?? c.solidez}`
              + (c.fundamentacao_normas.length
                ? ` (${c.fundamentacao_normas.map(n => n.replace('-', ' art. ')).join('; ')})`
                : '')),
          ].filter(Boolean),
        }] : []),
      ],
    }
  }

  const CartaoAnalise = ({ a, i, arquivada }:
    { a: Analise; i: number; arquivada?: boolean }) => (
    <div style={{
      ...cartao,
      borderLeft: a.activa ? '3px solid #1a7f37' : cartao.border as string,
      opacity: arquivada ? 0.75 : 1,
      marginBottom: 10,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        {a.activa && (
          <span style={{
            background: '#e7f6ec', color: '#1a7f37', fontSize: 11, fontWeight: 600,
            padding: '2px 9px', borderRadius: 999,
          }}>apreciação corrente</span>
        )}
        <strong style={{ fontSize: 13 }}>{dataHora(a.analisado_em)}</strong>
        {a.perspetiva === 'contraparte' && (
          <span style={{
            background: '#f7ead9', color: '#7a3b0a', fontSize: 11,
            padding: '2px 9px', borderRadius: 999,
          }}>⇄ contraditório</span>
        )}
        <span style={{ fontSize: 11.5, color: 'var(--color-text-tertiary)' }}>
          {a.convergencia ? 'lentes convergentes' : 'leituras em confronto'}
        </span>
        {arquivada && a.descarte_motivo && (
          <span style={{ fontSize: 11.5, color: 'var(--color-text-tertiary)' }}>
            · descartada: {motivos[a.descarte_motivo] ?? a.descarte_motivo}
            {a.descartada_em ? ` em ${dataHora(a.descartada_em)}` : ''}
          </span>
        )}
      </div>

      <div style={{ marginTop: 8, fontSize: 12.5, lineHeight: 1.6 }}>
        {a.cenarios.map((c, j) => (
          <div key={j} style={{ marginBottom: 3 }}>
            <span style={{
              display: 'inline-block', width: 7, height: 7, borderRadius: '50%',
              background: COR_SOLIDEZ[c.solidez] ?? '#999', marginRight: 7,
            }} />
            {c.titulo}
            <span style={{ color: 'var(--color-text-tertiary)' }}>
              {' '}— solidez {NOME_SOLIDEZ[c.solidez] ?? c.solidez}
            </span>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
        {arquivada ? (
          <button onClick={() => restaurar(i)} style={botaoLeve}>
            ↩ Repor na lista
          </button>
        ) : (
          <>
            {!a.activa && (
              <button onClick={() => activar(i)} style={botaoLeve}>
                ✓ Tornar apreciação corrente
              </button>
            )}
            <label style={{
              display: 'flex', alignItems: 'center', gap: 5, fontSize: 11.5,
              color: 'var(--color-text-tertiary)', cursor: 'pointer',
            }}>
              <input
                type="checkbox"
                checked={comparar.includes(i)}
                onChange={e => setComparar(c =>
                  e.target.checked ? [...c, i] : c.filter(x => x !== i))}
              />
              comparar
            </label>
            {aDescartar === i ? (
              <span style={{ display: 'flex', gap: 6, alignItems: 'center', marginLeft: 'auto' }}>
                <select value={motivo} onChange={e => setMotivo(e.target.value)}
                  style={{ fontSize: 11, fontFamily: 'inherit', padding: '2px 4px' }}>
                  {Object.entries(motivos).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
                <button onClick={() => descartar(i)} style={{
                  ...botaoLeve, background: '#7a3b0a', color: '#fff', border: 'none',
                }}>descartar</button>
                <button onClick={() => setADescartar(null)} style={botaoTexto}>cancelar</button>
              </span>
            ) : (
              <button onClick={() => setADescartar(i)}
                title="Descartar apenas esta análise — fica no arquivo, com data e motivo"
                style={{ ...botaoTexto, marginLeft: 'auto' }}>
                descartar esta análise
              </button>
            )}
          </>
        )}
      </div>
    </div>
  )

  if (!processo) {
    return (
      <div style={{ maxWidth: 920 }}>
        {carregando ? 'A carregar o processo…' : (erro ?? 'Processo não encontrado.')}
      </div>
    )
  }

  const seleccionadas = comparar.map(i => analises[i]).filter(Boolean)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: 920 }}>
      <button onClick={() => navigate('/processos')} style={botaoTexto}>
        ← Voltar aos processos em carteira
      </button>

      {erro && <div style={{ ...cartao, color: '#c62828' }}>{erro}</div>}

      {/* Identificação e descrição */}
      <div style={cartao}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <h2 style={{ margin: 0, fontSize: 17, color: '#0a2342' }}>
            {processo.numero_interno}
          </h2>
          <button
            onClick={async () => {
              const novo = window.prompt(
                'Assunto do processo — a linha que o identifica na carteira.\n' +
                'O relato dos factos mantém-se intacto.',
                processo.assunto ?? '')
              if (novo === null || !novo.trim()) return
              try {
                await api.patch(`/processos/${processo.id}/assunto`, { assunto: novo })
                carregar()
              } catch (e) { setErro(tratarErroAPI(e)) }
            }}
            title="Corrigir o assunto — não altera o relato dos factos"
            style={botaoTexto}>
            ✎ assunto
          </button>
          <span style={{
            fontSize: 11.5, color: 'var(--color-text-tertiary)',
            textTransform: 'uppercase', letterSpacing: '0.06em',
          }}>{processo.tipo} · {processo.estado}</span>
          {docImprimivel() && (
            <div style={{ marginLeft: 'auto' }}>
              <BotoesImprimir doc={docImprimivel()!} />
            </div>
          )}
        </div>
        {(processo.nome_autor || processo.nome_reu) && (
          <div style={{ fontSize: 12.5, color: 'var(--color-text-secondary)', marginTop: 4 }}>
            {processo.nome_autor} <span style={{ opacity: 0.6 }}>contra</span> {processo.nome_reu}
          </div>
        )}
        {processo.assunto && (
          <div style={{
            marginTop: 8, fontSize: 14, fontWeight: 600, color: '#0a2342',
          }}>{processo.assunto}</div>
        )}
        <div style={{
          fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.07em',
          color: 'var(--color-text-tertiary)', marginTop: 12, marginBottom: 4,
        }}>Relato dos factos — é este texto que alimenta a análise</div>
        <div style={{
          fontSize: 13.5, lineHeight: 1.65, whiteSpace: 'pre-wrap',
        }}>{processo.descricao}</div>
      </div>

      {/* Análises */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
          <h3 style={{ margin: 0, fontSize: 14, color: '#0a2342' }}>
            Análises deste processo ({analises.length})
          </h3>
          {arquivo.length > 0 && (
            <button onClick={() => setVerArquivo(v => !v)} style={botaoTexto}>
              {verArquivo ? 'ocultar' : 'ver'} arquivo ({arquivo.length})
            </button>
          )}
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
            <button onClick={() => analisar(false)} style={botaoLeve}>
              ⚖ {analises.length ? 'Nova análise' : 'Analisar pelas três lentes'}
            </button>
            {analises.length > 0 && (
              <button onClick={() => analisar(true)} style={{
                ...botaoLeve, color: '#7a3b0a', borderColor: '#7a3b0a',
              }}>⇄ Pelo lado contrário</button>
            )}
          </div>
        </div>

        {analises.length === 0 && (
          <div style={{ ...cartao, fontSize: 13, color: 'var(--color-text-secondary)' }}>
            Este processo ainda não tem análise. A análise é feita sobre a descrição
            acima — quanto mais completa for, mais fundamentada será a leitura.
          </div>
        )}

        {analises.map((a, i) => <CartaoAnalise key={i} a={a} i={i} />)}

        {verArquivo && arquivo.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <div style={{
              fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.07em',
              color: 'var(--color-text-tertiary)', marginBottom: 6,
            }}>Arquivo — análises descartadas</div>
            {arquivo.map((a, i) => <CartaoAnalise key={i} a={a} i={i} arquivada />)}
          </div>
        )}
      </div>

      {/* Comparação */}
      {seleccionadas.length >= 2 && (
        <div style={cartao}>
          <h3 style={{ margin: '0 0 8px', fontSize: 14, color: '#0a2342' }}>
            Comparação de {seleccionadas.length} análises
          </h3>
          <div style={{
            display: 'grid', gap: 12,
            gridTemplateColumns: `repeat(${Math.min(seleccionadas.length, 2)}, 1fr)`,
          }}>
            {seleccionadas.map((a, i) => (
              <div key={i} style={{ fontSize: 12.5, lineHeight: 1.6 }}>
                <strong>{dataHora(a.analisado_em)}</strong>
                {a.perspetiva === 'contraparte' && ' · contraditório'}
                <div style={{ marginTop: 6, color: 'var(--color-text-secondary)' }}>
                  {a.sintese_tecnica ?? a.sintese_cidada}
                </div>
              </div>
            ))}
          </div>
          <button onClick={() => setComparar([])} style={{ ...botaoTexto, marginTop: 8 }}>
            fechar comparação
          </button>
        </div>
      )}

      {/* Prazos */}
      {processo.prazos.length > 0 && (
        <div style={cartao}>
          <h3 style={{ margin: '0 0 8px', fontSize: 14, color: '#0a2342' }}>Prazos</h3>
          {processo.prazos.map((pr, i) => (
            <div key={i} style={{ fontSize: 12.5, lineHeight: 1.7 }}>
              {pr.urgente && !pr.cumprido && <span style={{ color: '#c62828' }}>● </span>}
              {pr.descricao}: {new Date(pr.data_limite).toLocaleDateString('pt-PT')}
              {pr.cumprido && <span style={{ color: 'var(--color-text-tertiary)' }}> — cumprido</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const botaoLeve: React.CSSProperties = {
  padding: '6px 12px', background: 'transparent',
  border: '0.5px solid #0a2342', borderRadius: 'var(--border-radius-md)',
  fontSize: 12, color: '#0a2342', cursor: 'pointer', fontFamily: 'inherit',
}

const botaoTexto: React.CSSProperties = {
  background: 'none', border: 'none', padding: 0,
  fontSize: 11.5, color: 'var(--color-text-tertiary)',
  cursor: 'pointer', fontFamily: 'inherit', textDecoration: 'underline',
}
