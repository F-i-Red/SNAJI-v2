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

import { useEffect, useRef, useState } from 'react'
import { BotoesImprimir, DocumentoImprimivel } from '../utils/imprimir'
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

interface LenteOmitidaAPI {
  lente: CenarioAPI['lente']
  motivo: string
}

interface CenariosAPI {
  cenarios: CenarioAPI[]
  lentes_omitidas?: LenteOmitidaAPI[]
  cenarios_convergentes?: CenarioAPI[]
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

/** Nota curta que acompanha a solidez, no ecrã e na impressão. */
/**
 * Nota curta que acompanha a solidez, no ecrã e na impressão.
 * Deliberadamente breve: entra num título de secção, e uma frase longa
 * partia-se em duas linhas no documento impresso.
 */
const NOTA_SOLIDEZ: Record<CenarioAPI['solidez'], string> = {
  elevada: 'bem fundamentada',
  media: 'com lacunas',
  baixa: 'base insuficiente',
}

/** Versão longa, para o texto explicativo e para a dica do rato. */
const NOTA_SOLIDEZ_LONGA: Record<CenarioAPI['solidez'], string> = {
  elevada: 'as normas disponíveis sustentam a conclusão',
  media: 'faltam normas para fechar o raciocínio',
  baixa: 'base documental insuficiente, tipicamente por falta de jurisprudência',
}

const NOME_SOLIDEZ: Record<CenarioAPI['solidez'], string> = {
  elevada: 'Solidez elevada',
  media: 'Solidez média',
  baixa: 'Solidez baixa',
}

/** Mantém o ecrã e a impressão coerentes na forma de nomear o desfecho. */


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
  const location = useLocation() as { state?: { texto?: string; caso_id?: string; processo_id?: string; contraditorio?: boolean } }
  const navigate = useNavigate()

  const [texto, setTexto] = useState(location.state?.texto ?? '')
  const [arrastar, setArrastar] = useState(false)
  const [aExtrair, setAExtrair] = useState(false)
  const [docsAnexados, setDocsAnexados] = useState<string[]>([])
  const [resultado, setResultado] = useState<CenariosAPI | null>(null)
  const [registoTecnico, setRegistoTecnico] = useState(ehProfissional)
  const [carregando, setCarregando] = useState(false)
  const [mostrarPercurso, setMostrarPercurso] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const extrairDocs = async (files: FileList) => {
    if (!files.length) return
    setAExtrair(true); setErro(null)
    try {
      const nomes = Array.from(files).map(f => f.name)
      const fd = new FormData()
      Array.from(files).forEach(f => fd.append('ficheiros', f))
      const r = await api.post<{ texto: string }>('/documentos/extrair-texto', fd,
        { headers: { 'Content-Type': 'multipart/form-data' } })
      if (!r.data.texto || !r.data.texto.trim()) {
        const avs = (r.data as any).avisos as string[] | undefined
        setErro(avs && avs.length
          ? 'O documento não continha texto legível: ' + avs.join(' · ')
          : 'O documento não continha texto legível (PDF digitalizado sem OCR, ou ficheiro vazio).')
        return
      }
      setTexto(prev => (prev.trim() ? prev.trim() + '\n\n' : '') + r.data.texto)
      setDocsAnexados(prev => [...prev, ...nomes])
    } catch (e) { setErro(tratarErroAPI(e)) }
    finally { setAExtrair(false) }
  }

  // Modo em que o resultado apresentado foi produzido. Guardado em estado
  // próprio, e não lido da navegação, porque o contraditório passa a poder
  // ser pedido a partir desta mesma página, sem mudar de rota.
  const [emContraditorio, setEmContraditorio] = useState(
    location.state?.contraditorio ?? false)

  /**
   * As duas análises do mesmo caso — a própria e a do contraditório — ficam
   * guardadas em conjunto, e alternar entre elas não repete a chamada.
   *
   * Cada análise leva minutos e custa tokens: descartá-la ao mudar de lado
   * era deitar fora trabalho já feito e já pago. E ter os dois lados
   * disponíveis lado a lado é, para um magistrado ou para o Ministério
   * Público, o próprio caso de uso — não um extra.
   */
  const [analises, setAnalises] = useState<{
    propria?: CenariosAPI; contraditorio?: CenariosAPI; texto?: string
  }>({})

  const chave = (contra: boolean) => (contra ? 'contraditorio' : 'propria') as const

  /**
   * Bloqueio de pedidos simultâneos.
   *
   * O estado `carregando` só fica visível na renderização seguinte, pelo que
   * duas chamadas disparadas no mesmo instante — como acontece quando um
   * efeito de arranque é executado duas vezes — passavam ambas pela guarda e
   * geravam duas análises em paralelo, ao dobro do custo. Uma referência é
   * actualizada de imediato e fecha essa janela.
   */
  const aGerar = useRef(false)

  const gerar = async (t?: string, contra?: boolean, forcar = false) => {
    const corpo = (t ?? texto).trim()
    if (corpo.length < 20 || carregando || aGerar.current) return
    aGerar.current = true
    const modo = contra ?? location.state?.contraditorio ?? false

    // Já existe para este texto: mostra sem repetir a chamada.
    const guardada = analises.texto === corpo ? analises[chave(modo)] : undefined
    if (guardada && !forcar) {
      setResultado(guardada)
      setEmContraditorio(modo)
      setErro(null)
      aGerar.current = false
      return
    }

    setCarregando(true); setErro(null); setResultado(null)
    try {
      const res = await api.post<CenariosAPI>('/cenarios', { texto: corpo, explicar: true, caso_id: location.state?.caso_id ?? null, processo_id: location.state?.processo_id ?? null, contraditorio: modo })
      setResultado(res.data)
      setEmContraditorio(modo)
      setAnalises(a => ({
        // Texto diferente do guardado: recomeça, para não misturar casos.
        ...(a.texto === corpo ? a : {}),
        texto: corpo,
        [chave(modo)]: res.data,
      }))
    } catch (e) { setErro(tratarErroAPI(e)) }
    finally { setCarregando(false); aGerar.current = false }
  }

  // Se veio do Instrutor com texto, gera automaticamente
  // Geração automática ao chegar de outra página, uma única vez.
  // Em desenvolvimento os efeitos correm duas vezes; sem esta marca, chegar
  // aqui a partir de um processo disparava duas análises em paralelo — com o
  // dobro do tempo e do custo, para o mesmo resultado.
  const jaArrancou = useRef(false)
  useEffect(() => {
    if (jaArrancou.current) return
    jaArrancou.current = true
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

  /**
   * Indicador de solidez.
   *
   * As lentes são sempre apresentadas pela mesma ordem — garantista,
   * legalista, consequencialista — porque essa ordem é pedagógica e
   * previsível, e porque ordenar por força equivaleria a recomendar uma
   * leitura sem o assumir. A diferença entre leituras é dada aqui, no
   * indicador: cor e legenda distintas por nível, para que o leitor a veja
   * sem que o sistema escolha por ele.
   */
  const Solidez = ({ nivel }: { nivel: CenarioAPI['solidez'] }) => {
    // Cores de semáforo, por serem imediatamente legíveis. Atenção ao que
    // significam: o vermelho indica FALTA DE BASE DOCUMENTAL — tipicamente
    // ausência de jurisprudência — e NÃO que a leitura esteja errada. No teste
    // contra o acórdão da Relação do Porto, a lente que acertou não era a de
    // solidez mais alta. Daí a legenda explicar sempre o que o nível quer dizer.
    const cfg = {
      elevada: { n: 3, cor: '#1a7f37', fundo: '#e7f6ec', nota: NOTA_SOLIDEZ.elevada },
      media:   { n: 2, cor: '#b58900', fundo: '#fdf6e0', nota: NOTA_SOLIDEZ.media },
      baixa:   { n: 1, cor: '#c62828', fundo: '#fdeaea', nota: NOTA_SOLIDEZ.baixa },
    }[nivel]
    return (
      <span
        title={`${NOME_SOLIDEZ[nivel]} — ${NOTA_SOLIDEZ_LONGA[nivel]}`}
        style={{
          display: 'inline-flex', gap: 4, alignItems: 'center',
          background: cfg.fundo, border: `1px solid ${cfg.cor}33`,
          borderRadius: 999, padding: '2px 9px 2px 7px',
        }}>
        {[0, 1, 2].map(i => (
          <span key={i} style={{
            width: 7, height: 7, borderRadius: '50%',
            background: i < cfg.n ? cfg.cor : 'var(--color-border-tertiary)',
          }} />
        ))}
        <span style={{ fontSize: 11, fontWeight: 600, color: cfg.cor, marginLeft: 2 }}>
          {NOME_SOLIDEZ[nivel]}
        </span>
        <span style={{ fontSize: 10.5, color: 'var(--color-text-tertiary)' }}>
          · {cfg.nota}
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

  const docImprimivel = (): DocumentoImprimivel | null => {
    if (!resultado) return null
    const caso = (texto ?? '').trim()
    const seccoes = [
      ...(caso
        ? [{
            titulo: 'Caso analisado',
            paragrafos: caso.split(/\n{2,}/).map(p => p.replace(/\s*\n\s*/g, ' ').trim()).filter(Boolean),
          }]
        : []),
      // Em papel não há como abrir nada: as lentes que convergiram são
      // impressas por extenso, a seguir à principal.
      ...[...resultado.cenarios, ...(resultado.cenarios_convergentes ?? [])].map(cn => {
        const riscos = registoTecnico ? cn.riscos : cn.riscos_cidadao
        const normas = cn.fundamentacao_normas.map(n => n.replace('-', ' art. ')).join('; ')
        return {
          titulo: `Lente ${NOME_LENTE[cn.lente]} — ${NOME_SOLIDEZ[cn.solidez].toLowerCase()}`
            + ` (${NOTA_SOLIDEZ[cn.solidez]})`,
          paragrafos: [
            registoTecnico ? cn.lente_descricao_tecnica : cn.lente_descricao_cidada,
            `${cn.titulo} — ${NOME_SENTIDO[cn.sentido] ?? cn.sentido}`,
            registoTecnico ? cn.solucao_tecnica : cn.solucao_cidada,
            riscos ? `Riscos e contra-argumentos: ${riscos}` : '',
            normas ? `Normas validadas no corpus: ${normas}` : '',
          ].filter(Boolean) as string[],
        }
      }),
      ...((resultado.lentes_omitidas?.length ?? 0) > 0
        ? [{
            titulo: 'Abordagens sem solução sustentável neste caso',
            paragrafos: [
              ...resultado.lentes_omitidas!.map(o => `Lente ${NOME_LENTE[o.lente]} — ${o.motivo}`),
              'Estas abordagens não foram apresentadas como cenário por não sustentarem uma '
              + 'solução juridicamente defensável — e não por falha do sistema.',
            ],
          }]
        : []),
      {
        titulo: 'Síntese comparativa',
        paragrafos: [
          registoTecnico ? resultado.sintese_tecnica : resultado.sintese_cidada,
          ...(resultado.convergencia
            ? ['As três abordagens interpretativas convergem no mesmo sentido — indicador de caso juridicamente claro.']
            : []),
        ],
      },
    ]
    return {
      titulo: 'Cenários de resolução',
      subtitulo: emContraditorio ? 'Análise do contraditório (perspetiva da parte contrária)' : 'O mesmo caso analisado por três abordagens da prática judiciária',
      meta: [
        `Gerado pelo SNAJI em ${new Date().toLocaleDateString('pt-PT')}`,
        // O registo é dito por extenso: um documento arquivado deve declarar
        // para quem foi escrito, e a menção curta passava despercebida a quem
        // imprimia sem reparar em que separador estava.
        registoTecnico
          ? 'Registo técnico — redigido para profissionais do direito'
          : 'Linguagem clara — redigido para o cidadão',
      ],
      seccoes,
      rodape: resultado.ressalva || 'Apoio à decisão gerado pelo SNAJI — sem valor oficial. Não substitui aconselhamento jurídico profissional.',
    }
  }

  return (
    // 920 px: com as leituras em coluna única, a linha ganha largura sem
    // passar do limite a partir do qual o olho perde a mudança de linha.
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: 920 }}>

      {emContraditorio && (
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
        {resultado && (
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 11.5, color: 'var(--color-text-tertiary)' }}>
              Vai imprimir em <strong>{registoTecnico ? 'registo técnico' : 'linguagem clara'}</strong>
            </span>
            <BotoesImprimir doc={docImprimivel()!} />
          </div>
        )}
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
        <div
          onDragOver={e => { e.preventDefault(); setArrastar(true) }}
          onDragLeave={() => setArrastar(false)}
          onDrop={e => { e.preventDefault(); setArrastar(false); if (e.dataTransfer.files.length) extrairDocs(e.dataTransfer.files) }}
          onClick={() => document.getElementById('docs-cenarios')?.click()}
          style={{
            border: `2px dashed ${arrastar ? '#0a2342' : 'var(--color-border-tertiary)'}`,
            borderRadius: 'var(--border-radius-md)', padding: '12px', textAlign: 'center', cursor: 'pointer',
            background: arrastar ? 'var(--color-background-info)' : 'transparent',
            fontSize: 12.5, color: 'var(--color-text-secondary)',
          }}
        >
          {aExtrair ? 'A ler os documentos…'
            : '📎 Arraste documentos do caso (PDF, Word, texto) — pode largar vários. O SNAJI lê-os e junta ao texto.'}
          <input id="docs-cenarios" type="file" accept=".pdf,.docx,.txt,.jpg,.jpeg,.png,.tif,.tiff,.bmp,.webp" multiple style={{ display: 'none' }}
            onChange={e => e.target.files && extrairDocs(e.target.files)} />
        </div>
        {docsAnexados.length > 0 && (
          <div style={{ fontSize: 11.5, color: 'var(--color-text-tertiary)' }}>
            {docsAnexados.length} documento(s) anexado(s): {docsAnexados.join(', ')}
          </div>
        )}
        <div style={{
          display: 'flex', gap: 8, alignItems: 'flex-start',
          fontSize: 11.5, lineHeight: 1.5,
          color: 'var(--color-text-tertiary)',
          background: 'var(--color-background-secondary)',
          border: '1px solid var(--color-border-default)',
          borderRadius: 6, padding: '8px 10px',
        }}>
          <span aria-hidden="true">🔒</span>
          <span>
            <strong>Como são tratados os seus dados.</strong> O texto que escrever é
            analisado por um modelo de inteligência artificial executado por um
            fornecedor externo. Antes do envio, o SNAJI substitui automaticamente
            identificadores como NIF, telefone, email, IBAN, matrícula e código
            postal por marcadores — mas <strong>nomes e outros detalhes que escreva
            não são removidos</strong>. Não inclua informação que não queira ver
            processada fora do sistema.
          </span>
        </div>
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

          {/* Cartões dos cenários — coluna única.
              Três colunas numa página de 860 px davam ~275 px cada, largura a
              que texto jurídico, com citações e incisos, se torna penoso de
              ler. Em sequência, cada leitura ocupa a largura toda e lê-se
              como se lê qualquer peça. */}
          <div style={{ display: 'grid', gap: 14, gridTemplateColumns: '1fr' }}>
            {resultado.cenarios.map(c => <CartaoCenario key={c.lente} c={c} />)}
          </div>

          {/* Lentes que convergiram, disponíveis para consulta */}
          {(resultado.cenarios_convergentes?.length ?? 0) > 0 && (
            <details style={{
              border: '1px solid var(--color-border-default)', borderRadius: 8,
              padding: '10px 12px', background: 'var(--color-background-secondary)',
            }}>
              <summary style={{ cursor: 'pointer', fontSize: 12.5, fontWeight: 600 }}>
                Ver as outras {resultado.cenarios_convergentes!.length} leituras que
                convergiram
                <span style={{ fontWeight: 400, color: 'var(--color-text-tertiary)' }}>
                  {' '}— {resultado.cenarios_convergentes!.map(c => NOME_LENTE[c.lente]).join(' e ')}
                </span>
              </summary>
              <div style={{ marginTop: 10, display: 'grid', gap: 14, gridTemplateColumns: '1fr' }}>
                {resultado.cenarios_convergentes!.map(c => (
                  <CartaoCenario key={c.lente} c={c} />
                ))}
              </div>
            </details>
          )}

          {/* Alternar entre os dois lados do caso.
              Ambas as análises ficam guardadas: mudar de lado não repete a
              chamada nem descarta o que já foi gerado. */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
            border: '0.5px solid #7a3b0a44', borderRadius: 'var(--border-radius-md)',
            background: '#fdf8f2', padding: '10px 14px',
          }}>
            <span style={{ fontSize: 12.5, color: 'var(--color-text-secondary)' }}>
              Ver este caso:
            </span>
            {([false, true] as const).map(contra => {
              const activo = emContraditorio === contra
              const pronta = analises.texto === texto.trim() && analises[chave(contra)]
              return (
                <button
                  key={String(contra)}
                  onClick={() => gerar(texto, contra)}
                  disabled={carregando || activo}
                  title={contra
                    ? 'Os mesmos factos, argumentados por quem se opõe — para preparar a resposta que virá'
                    : 'A análise na perspetiva de quem relata o caso'}
                  style={{
                    padding: '7px 14px', fontSize: 12.5, fontWeight: 500,
                    fontFamily: 'inherit', borderRadius: 'var(--border-radius-md)',
                    border: `0.5px solid ${activo ? '#7a3b0a' : '#7a3b0a55'}`,
                    background: activo ? '#7a3b0a' : 'transparent',
                    color: activo ? '#fff' : '#7a3b0a',
                    cursor: carregando ? 'wait' : activo ? 'default' : 'pointer',
                    opacity: carregando ? 0.5 : 1,
                  }}>
                  {contra ? '⇄ Pelo lado contrário' : 'O seu lado'}
                  {pronta && !activo && (
                    <span style={{ marginLeft: 6, fontSize: 11 }} title="já analisado">✓</span>
                  )}
                </button>
              )
            })}
            <span style={{ fontSize: 11.5, color: 'var(--color-text-tertiary)', marginLeft: 'auto' }}>
              {analises.propria && analises.contraditorio
                ? 'Ambos os lados analisados — alterne sem esperar.'
                : 'A análise de cada lado é feita uma só vez e fica guardada.'}
            </span>
          </div>

          {/* O que a solidez significa — e o que não significa */}
          <div style={{
            fontSize: 11.5, lineHeight: 1.55, color: 'var(--color-text-tertiary)',
            paddingLeft: 2,
          }}>
            A <strong>solidez</strong> indica quanta base documental sustenta cada leitura, e não
            a probabilidade de ela vir a proceder. Uma leitura com base limitada pode estar
            correcta: assinala apenas que faltam normas ou jurisprudência para a fundamentar
            por inteiro.
          </div>

          {/* Lentes que se abstiveram */}
          {(resultado.lentes_omitidas?.length ?? 0) > 0 && (
            <div style={{ ...cartao, fontSize: 12.5, lineHeight: 1.6, borderStyle: 'dashed' }}>
              <strong style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-tertiary)' }}>
                Abordagens sem solução sustentável neste caso
              </strong>
              <div style={{ marginTop: 6, color: 'var(--color-text-secondary)' }}>
                {resultado.lentes_omitidas!.map(o => (
                  <div key={o.lente} style={{ marginBottom: 6 }}>
                    <span style={{ fontWeight: 600 }}>Lente {NOME_LENTE[o.lente]}</span>
                    {' — '}
                    <span>{o.motivo}</span>
                  </div>
                ))}
                <div style={{ fontSize: 11.5, color: 'var(--color-text-tertiary)', marginTop: 8 }}>
                  Estas abordagens não foram apresentadas como cenário por não sustentarem
                  uma solução juridicamente defensável — e não por falha do sistema.
                </div>
              </div>
            </div>
          )}

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
                            {/* Todas as normas entregues, não as primeiras oito:
                                o corte era um resto de quando eram oito, e
                                escondia metade do que o modelo recebeu — o que
                                impedia perceber se uma norma em falta na
                                análise fora ou não recuperada. */}
                            {((p.dados as any).normas_recuperadas as any[]).map(n => (
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
