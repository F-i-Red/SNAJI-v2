/**
 * Glossário jurídico — SNAJI (todos os perfis)
 *
 * Os termos de direito que aparecem num processo, explicados em linguagem
 * simples e ancorados nas normas do corpus. Pesquisável. Para o cidadão que
 * "não sabe bem o que é" — e para toda a gente confirmar depressa.
 */

import { useState } from 'react'

interface Termo {
  termo: string
  explicacao: string
  norma: string
  exemplo?: string
}

const TERMOS: Termo[] = [
  {
    termo: 'Objeto do litígio',
    explicacao: 'Aquilo que se discute no processo: o pedido (o que se quer que o tribunal decida) mais a causa de pedir (os factos que o fundamentam). A sentença tem de o identificar.',
    norma: 'CPC art. 596.º · LJP art. 60.º',
    exemplo: '«Condenação do réu no pagamento de 4.800 € de rendas em atraso.»',
  },
  {
    termo: 'Causa de pedir',
    explicacao: 'Os factos concretos de onde nasce o direito que se invoca. Não basta pedir — é preciso dizer porquê.',
    norma: 'CPC art. 581.º',
    exemplo: '«O réu não paga a renda desde janeiro» é a causa de pedir do pedido de pagamento.',
  },
  {
    termo: 'Valor da causa',
    explicacao: 'Quanto vale, em euros, aquilo que se discute. Toda a ação tem de o indicar — e ele decide onde o processo corre (julgados de paz até 15.000 €), se a decisão admite recurso, e as custas.',
    norma: 'CPC art. 296.º · LJP art. 8.º',
  },
  {
    termo: 'Alçada',
    explicacao: 'O limite de valor até ao qual um tribunal decide sem recurso. Só se pode recorrer quando o valor da causa ultrapassa a alçada do tribunal que decidiu. Nos julgados de paz, há recurso quando o valor excede metade da alçada da 1.ª instância.',
    norma: 'CPC art. 629.º · LJP art. 62.º',
  },
  {
    termo: 'Legitimidade',
    explicacao: 'Quem pode estar no processo: só o titular do interesse em causa pode demandar, e só quem o contradiz pode ser demandado. Não posso processar o senhorio do meu vizinho por um problema que é do meu vizinho.',
    norma: 'CPC art. 30.º',
  },
  {
    termo: 'Citação',
    explicacao: 'O ato pelo qual o réu fica a saber, oficialmente, que foi posto um processo contra ele — e a partir do qual correm os prazos para se defender. Ignorá-la tem consequências graves (ver Revelia).',
    norma: 'CPC art. 219.º · LJP art. 45.º',
  },
  {
    termo: 'Revelia',
    explicacao: 'O que acontece quando o réu, devidamente citado, não contesta: os factos alegados pelo autor consideram-se confessados — perde-se por silêncio. Quem recebe uma citação nunca a deve ignorar.',
    norma: 'CPC art. 566.º · LJP art. 58.º',
  },
  {
    termo: 'Ónus da prova',
    explicacao: 'Quem tem de provar o quê: quem invoca um direito prova os factos que o sustentam; quem alega que o direito já não existe (pagou, prescreveu) prova esses. Ter razão não chega — é preciso conseguir mostrá-la.',
    norma: 'CC art. 342.º',
  },
  {
    termo: 'Prescrição',
    explicacao: 'O prazo a partir do qual um direito deixa de poder ser exigido em tribunal, por ter passado tempo demais. Os prazos variam: 3 anos na responsabilidade civil (acidentes, danos), 1 ano nos créditos laborais após o fim do contrato, 5 anos em rendas e juros, 20 anos na regra geral.',
    norma: 'CC arts. 309.º, 310.º, 498.º · CT art. 337.º',
    exemplo: 'Um acidente de 2021 pode já não dar direito a indemnização em 2026.',
  },
  {
    termo: 'Litispendência',
    explicacao: 'Repetir a mesma ação (mesmas partes, mesmo pedido, mesma causa de pedir) enquanto a primeira ainda corre. Não é permitido — a segunda ação é travada.',
    norma: 'CPC art. 580.º',
  },
  {
    termo: 'Caso julgado',
    explicacao: 'Quando uma decisão se torna definitiva, o que foi decidido não pode voltar a ser discutido entre as mesmas partes. É a paz jurídica: os conflitos têm um fim.',
    norma: 'CPC arts. 580.º e 619.º',
  },
  {
    termo: 'Trânsito em julgado',
    explicacao: 'O momento em que a decisão se torna definitiva — quando já não cabe recurso, ou o prazo para recorrer passou sem ninguém o fazer. É quando "acabou mesmo".',
    norma: 'CPC art. 628.º',
  },
  {
    termo: 'Providência cautelar',
    explicacao: 'Uma medida urgente, pedida antes ou durante o processo, para evitar um prejuízo grave que não pode esperar pela decisão final (ex.: impedir a venda de um bem em disputa).',
    norma: 'CPC art. 362.º · LJP art. 41.º-A',
  },
  {
    termo: 'Apoio judiciário',
    explicacao: 'O sistema que paga (total ou parcialmente) as custas e o advogado a quem não tem meios económicos. Pede-se na Segurança Social, não no tribunal.',
    norma: 'Lei n.º 34/2004 (regime de acesso ao direito)',
  },
  {
    termo: 'Mediação',
    explicacao: 'A tentativa de resolver o conflito por acordo, com a ajuda de um terceiro imparcial (o mediador), antes de ir a julgamento. Nos julgados de paz é oferecida logo no início — mais rápida e barata que o julgamento.',
    norma: 'LJP arts. 16.º e 49.º a 56.º',
  },
  {
    termo: 'Contestação',
    explicacao: 'A resposta do réu à ação: onde impugna os factos, conta a sua versão e apresenta a sua defesa. Tem prazo — perdê-lo leva à revelia.',
    norma: 'CPC art. 569.º · LJP art. 47.º',
  },
]

export default function PaginaGlossario() {
  const [filtro, setFiltro] = useState('')
  const f = filtro.trim().toLowerCase()
  const visiveis = TERMOS.filter(t =>
    !f || t.termo.toLowerCase().includes(f) || t.explicacao.toLowerCase().includes(f))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: 680 }}>
      <div>
        <h1 style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 22, fontWeight: 500 }}>
          Termos de direito
        </h1>
        <small style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>
          Os conceitos que aparecem num processo, explicados em linguagem simples.
          Cada um indica a norma onde vive — pesquisável na Jurisprudência e na Consulta.
        </small>
      </div>

      <input
        type="text" value={filtro} onChange={e => setFiltro(e.target.value)}
        placeholder="Pesquisar um termo (ex.: prescrição, revelia…)"
        aria-label="Pesquisar termo"
        style={{ padding: '9px 12px', border: '0.5px solid var(--color-border-secondary)', borderRadius: 'var(--border-radius-md)', fontSize: 13.5, fontFamily: 'inherit' }}
      />

      {visiveis.map(t => (
        <div key={t.termo} style={{ background: 'var(--color-background-primary)', border: '0.5px solid var(--color-border-tertiary)', borderRadius: 'var(--border-radius-lg)', padding: '14px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 600, fontSize: 14.5, color: '#0a2342' }}>{t.termo}</span>
            <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)' }}>{t.norma}</span>
          </div>
          <div style={{ fontSize: 13, lineHeight: 1.65, color: 'var(--color-text-secondary)', marginTop: 4 }}>
            {t.explicacao}
          </div>
          {t.exemplo && (
            <div style={{ fontSize: 12, color: 'var(--color-text-tertiary)', marginTop: 4, fontStyle: 'italic' }}>
              {t.exemplo}
            </div>
          )}
        </div>
      ))}
      {visiveis.length === 0 && (
        <div style={{ fontSize: 13, color: 'var(--color-text-tertiary)' }}>
          Nenhum termo corresponde à pesquisa.
        </div>
      )}

      <div style={{ fontSize: 11.5, lineHeight: 1.55, color: 'var(--color-text-tertiary)', borderTop: '0.5px solid var(--color-border-tertiary)', paddingTop: 10 }}>
        Explicações simplificadas para orientação — não substituem a leitura das
        normas nem o aconselhamento profissional. SNAJI — apoio cognitivo, nunca decisão.
      </div>
    </div>
  )
}
