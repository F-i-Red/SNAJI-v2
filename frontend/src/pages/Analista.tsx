/**
 * Painel do Analista — SNAJI (Especificação V8, §8)
 *
 * Três blocos alimentados pelos endpoints do módulo Analista:
 *  - Observatório da conflitualidade (volumes, áreas, alertas, série diária)
 *  - Zonas cinzentas da lei (índice de incerteza jurídica)
 *  - Qualidade e operação (groundedness, LLM, instrução)
 *
 * Os valores mascarados por k-anonimato chegam como "<3" e são exibidos
 * tal como vêm — a privacidade é visível, não escondida.
 */

import { useEffect, useState } from 'react'
import { api, tratarErroAPI } from '../services/api'

type Num = number | string // contagens podem vir mascaradas ("<3")

interface Observatorio {
  periodo_dias: number
  total_instrucoes: Num
  volumes_por_area: Record<string, Num>
  serie_diaria: Record<string, Num>
  alertas_por_tipo: Record<string, Num>
  alertas_por_gravidade: Record<string, Num>
  prazos_urgentes_detectados: Num
  nota_privacidade: string
}

interface ZonasCinzentas {
  total_analises_de_cenarios: Num
  casos_convergentes: Num
  casos_divergentes: Num
  indice_de_incerteza_juridica: number | null
  distribuicao_de_solidez: Record<string, Num>
  leitura: string
}

interface Governacao {
  funil: { instrucoes_iniciadas: Num; instrucoes_concluidas: Num; taxa_de_conclusao: number | null }
  equidade_de_acesso: { por_papel_processual: Record<string, Num>; leitura: string }
  territorio: { instrucoes_por_distrito: Record<string, Num>; nota: string }
  prazos: { direitos_em_risco_sinalizados_a_tempo: Record<string, Num>
            chegaram_com_prazo_expirado: Record<string, Num>; leitura: string }
  normas_mais_invocadas: Record<string, Num>
}

interface Qualidade {
  taxa_utilizacao_llm: number | null
  groundedness: {
    analises_sem_citacoes_rejeitadas: Num
    total_citacoes_rejeitadas_pelo_validador: Num
  }
  perguntas_medias_por_instrucao: number | null
  leitura: string
}

const NOME_AREA: Record<string, string> = {
  laboral: 'Trabalho', penal: 'Penal', civil: 'Civil', consumo: 'Consumo',
  familia: 'Família', dados_pessoais: 'Dados pessoais',
  administrativo: 'Administrativo', outro: 'Outra',
}
const NOME_ALERTA: Record<string, string> = {
  prazo: 'Prazos', via_nao_judicial: 'Via não judicial', apoio_judiciario: 'Apoio judiciário',
}

const NOME_PAPEL: Record<string, string> = {
  demandante: 'A reclamar', demandado: 'A defender-se', desconhecido: 'Não indicado', nao_sei: 'Não sabia',
}

export default function PaginaAnalista() {
  const [dias, setDias] = useState(30)
  const [obs, setObs] = useState<Observatorio | null>(null)
  const [zc, setZc] = useState<ZonasCinzentas | null>(null)
  const [q, setQ] = useState<Qualidade | null>(null)
  const [g, setG] = useState<Governacao | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(false)

  const carregar = async (d: number) => {
    setCarregando(true); setErro(null)
    try {
      const [r1, r2, r3, r4] = await Promise.all([
        api.get<Observatorio>(`/analista/observatorio?dias=${d}`),
        api.get<ZonasCinzentas>(`/analista/zonas-cinzentas?dias=${d}`),
        api.get<Qualidade>(`/analista/qualidade?dias=${d}`),
        api.get<Governacao>(`/analista/governacao?dias=${d}`),
      ])
      setObs(r1.data); setZc(r2.data); setQ(r3.data); setG(r4.data)
    } catch (e) { setErro(tratarErroAPI(e)) }
    finally { setCarregando(false) }
  }

  useEffect(() => { carregar(dias) }, [dias]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Estilos base (design system SNAJI) ─────────────────────────────────

  const cartao: React.CSSProperties = {
    background: 'var(--color-background-primary)',
    border: '0.5px solid var(--color-border-tertiary)',
    borderRadius: 'var(--border-radius-lg)',
    padding: '14px 16px',
  }
  const titulo: React.CSSProperties = {
    fontSize: 11, fontWeight: 600, textTransform: 'uppercase',
    letterSpacing: '0.08em', color: 'var(--color-text-tertiary)', marginBottom: 10,
  }

  const numerico = (v: Num | null | undefined): string =>
    v === null || v === undefined ? '—' : String(v)

  const maximo = (d: Record<string, Num>): number =>
    Math.max(1, ...Object.values(d).map(v => (typeof v === 'number' ? v : 1)))

  const Kpi = ({ rotulo, valor, destaque }: { rotulo: string; valor: string; destaque?: boolean }) => (
    <div style={{ ...cartao, textAlign: 'center', minWidth: 150, flex: 1 }}>
      <div style={{
        fontFamily: "'Cormorant Garamond', serif", fontSize: 30, fontWeight: 500,
        color: destaque ? '#8a1d1d' : 'var(--color-text-primary)', lineHeight: 1.1,
      }}>
        {valor}
      </div>
      <div style={{ fontSize: 11.5, color: 'var(--color-text-tertiary)', marginTop: 4 }}>{rotulo}</div>
    </div>
  )

  const Barras = ({ dados, nomes }: { dados: Record<string, Num>; nomes?: Record<string, string> }) => {
    const max = maximo(dados)
    const entradas = Object.entries(dados)
    if (!entradas.length) {
      return <div style={{ fontSize: 12.5, color: 'var(--color-text-tertiary)' }}>Sem dados no período.</div>
    }
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {entradas.map(([chave, v]) => {
          const num = typeof v === 'number' ? v : 1
          return (
            <div key={chave} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 12, width: 120, color: 'var(--color-text-secondary)' }}>
                {(nomes ?? {})[chave] ?? chave}
              </span>
              <div style={{ flex: 1, background: 'var(--color-background-secondary)', borderRadius: 4, height: 14 }}>
                <div style={{
                  width: `${(num / max) * 100}%`, height: '100%', borderRadius: 4,
                  background: typeof v === 'number' ? '#0a2342' : 'var(--color-border-secondary)',
                }} />
              </div>
              <span style={{ fontSize: 12, width: 34, textAlign: 'right', color: 'var(--color-text-primary)' }}>
                {String(v)}
              </span>
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: 900 }}>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <h1 style={{
          fontFamily: "'Cormorant Garamond', serif",
          fontSize: 22, fontWeight: 500, color: 'var(--color-text-primary)',
        }}>
          Observatório da conflitualidade
        </h1>
        <small style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>
          Indicadores agregados e anonimizados (k-anonimato: contagens &lt;3 mascaradas)
        </small>
        <div style={{ marginLeft: 'auto', display: 'inline-flex', border: '0.5px solid var(--color-border-secondary)', borderRadius: 20, overflow: 'hidden' }}>
          {[7, 30, 90].map(d => (
            <button key={d} onClick={() => setDias(d)} disabled={carregando}
              style={{
                border: 'none', padding: '6px 14px', fontSize: 12, fontFamily: 'inherit', cursor: 'pointer',
                background: dias === d ? '#0a2342' : 'transparent',
                color: dias === d ? '#fff' : 'var(--color-text-secondary)',
              }}>
              {d} dias
            </button>
          ))}
        </div>
      </div>

      {erro && (
        <div style={{ ...cartao, borderLeft: '3px solid var(--color-text-danger)', fontSize: 13 }}>{erro}</div>
      )}

      {obs && zc && q && (
        <>
          {/* KPIs */}
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <Kpi rotulo="Instruções concluídas" valor={numerico(obs.total_instrucoes)} />
            <Kpi rotulo="Alertas urgentes de prazo" valor={numerico(obs.prazos_urgentes_detectados)} destaque />
            <Kpi rotulo="Índice de incerteza jurídica"
                 valor={zc.indice_de_incerteza_juridica === null ? '—' : String(zc.indice_de_incerteza_juridica)} />
            <Kpi rotulo="Perguntas médias / instrução"
                 valor={q.perguntas_medias_por_instrucao === null ? '—' : String(q.perguntas_medias_por_instrucao)} />
          </div>

          {/* Observatório */}
          <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}>
            <div style={cartao}>
              <div style={titulo}>Volumes por área jurídica</div>
              <Barras dados={obs.volumes_por_area} nomes={NOME_AREA} />
            </div>
            <div style={cartao}>
              <div style={titulo}>Alertas emitidos por tipo</div>
              <Barras dados={obs.alertas_por_tipo} nomes={NOME_ALERTA} />
              <div style={{ ...titulo, marginTop: 14 }}>Por gravidade</div>
              <Barras dados={obs.alertas_por_gravidade} />
            </div>
          </div>

          {/* Série diária */}
          <div style={cartao}>
            <div style={titulo}>Evolução diária das instruções</div>
            {Object.keys(obs.serie_diaria).length === 0 ? (
              <div style={{ fontSize: 12.5, color: 'var(--color-text-tertiary)' }}>Sem dados no período.</div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 70 }}>
                {Object.entries(obs.serie_diaria).map(([dia, v]) => {
                  const num = typeof v === 'number' ? v : 1
                  const max = maximo(obs.serie_diaria)
                  return (
                    <div key={dia} title={`${dia}: ${v}`} style={{
                      flex: 1, minWidth: 6, borderRadius: '3px 3px 0 0',
                      height: `${(num / max) * 100}%`,
                      background: typeof v === 'number' ? '#0a2342' : 'var(--color-border-secondary)',
                    }} />
                  )
                })}
              </div>
            )}
          </div>

          {/* Zonas cinzentas + Qualidade */}
          <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}>
            <div style={cartao}>
              <div style={titulo}>Zonas cinzentas da lei</div>
              <div style={{ fontSize: 13, lineHeight: 1.7, color: 'var(--color-text-primary)' }}>
                Análises de cenários: <strong>{numerico(zc.total_analises_de_cenarios)}</strong><br />
                Lentes convergentes: <strong>{numerico(zc.casos_convergentes)}</strong> · divergentes:{' '}
                <strong>{numerico(zc.casos_divergentes)}</strong>
              </div>
              <div style={{ ...titulo, marginTop: 12 }}>Distribuição de solidez</div>
              <Barras dados={zc.distribuicao_de_solidez} />
              <div style={{ fontSize: 11.5, lineHeight: 1.55, color: 'var(--color-text-tertiary)', marginTop: 10 }}>
                {zc.leitura}
              </div>
            </div>
            <div style={cartao}>
              <div style={titulo}>Qualidade e operação</div>
              <div style={{ fontSize: 13, lineHeight: 1.8, color: 'var(--color-text-primary)' }}>
                Taxa de utilização do motor LLM:{' '}
                <strong>{q.taxa_utilizacao_llm === null ? '—' : `${Math.round(q.taxa_utilizacao_llm * 100)}%`}</strong><br />
                Análises sem citações rejeitadas:{' '}
                <strong>{numerico(q.groundedness.analises_sem_citacoes_rejeitadas)}</strong><br />
                Citações rejeitadas pelo validador:{' '}
                <strong>{numerico(q.groundedness.total_citacoes_rejeitadas_pelo_validador)}</strong>
              </div>
              <div style={{ fontSize: 11.5, lineHeight: 1.55, color: 'var(--color-text-tertiary)', marginTop: 10 }}>
                {q.leitura}
              </div>
            </div>
          </div>

          {/* Governação do sistema */}
          {g && (
            <>
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                <Kpi rotulo="Instruções iniciadas" valor={numerico(g.funil.instrucoes_iniciadas)} />
                <Kpi rotulo="Concluídas" valor={numerico(g.funil.instrucoes_concluidas)} />
                <Kpi rotulo="Taxa de conclusão"
                     valor={g.funil.taxa_de_conclusao === null ? '—' : `${Math.round(g.funil.taxa_de_conclusao * 100)}%`} />
              </div>
              <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}>
                <div style={cartao}>
                  <div style={titulo}>Equidade de acesso (papel processual)</div>
                  <Barras dados={g.equidade_de_acesso.por_papel_processual} nomes={NOME_PAPEL} />
                  <div style={{ fontSize: 11.5, lineHeight: 1.55, color: 'var(--color-text-tertiary)', marginTop: 10 }}>
                    {g.equidade_de_acesso.leitura}
                  </div>
                </div>
                <div style={cartao}>
                  <div style={titulo}>Conflitualidade por distrito</div>
                  <Barras dados={g.territorio.instrucoes_por_distrito} />
                  <div style={{ fontSize: 11.5, color: 'var(--color-text-tertiary)', marginTop: 10 }}>
                    {g.territorio.nota}
                  </div>
                </div>
              </div>
              <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}>
                <div style={cartao}>
                  <div style={titulo}>Prazos — sinalizados a tempo (direitos salvos)</div>
                  <Barras dados={g.prazos.direitos_em_risco_sinalizados_a_tempo} />
                  <div style={{ ...titulo, marginTop: 14, color: '#8a1d1d' }}>Chegaram com o prazo expirado</div>
                  <Barras dados={g.prazos.chegaram_com_prazo_expirado} />
                  <div style={{ fontSize: 11.5, lineHeight: 1.55, color: 'var(--color-text-tertiary)', marginTop: 10 }}>
                    {g.prazos.leitura}
                  </div>
                </div>
                <div style={cartao}>
                  <div style={titulo}>Artigos de lei mais invocados</div>
                  <Barras dados={Object.fromEntries(Object.entries(g.normas_mais_invocadas).map(
                    ([k, v]) => [k.replace('-', ' art. '), v]
                  ))} />
                </div>
              </div>
            </>
          )}

          <div style={{
            fontSize: 11.5, lineHeight: 1.55, color: 'var(--color-text-tertiary)',
            borderTop: '0.5px solid var(--color-border-tertiary)', paddingTop: 10,
          }}>
            {obs.nota_privacidade} Nenhum dado pessoal é recolhido ou exibido — o registo analítico
            contém apenas categorias e contagens (anonimização por desenho, RGPD).
          </div>
        </>
      )}
    </div>
  )
}
