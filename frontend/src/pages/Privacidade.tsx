/**
 * Privacidade e Dados — SNAJI (todos os perfis)
 *
 * A política de dados do sistema, escrita para pessoas: o que o SNAJI guarda,
 * porquê, por quanto tempo, e os direitos de quem o usa. Numa PoC, documenta;
 * em produção, cada compromisso aqui descrito tem de estar implementado.
 */

export default function PaginaPrivacidade() {
  const cartao: React.CSSProperties = {
    background: 'var(--color-background-primary)',
    border: '0.5px solid var(--color-border-tertiary)',
    borderRadius: 'var(--border-radius-lg)', padding: '18px',
    fontSize: 13.5, lineHeight: 1.7, color: 'var(--color-text-secondary)',
  }
  const titulo: React.CSSProperties = {
    fontSize: 12, fontWeight: 600, textTransform: 'uppercase',
    letterSpacing: '0.07em', color: '#0a2342', marginBottom: 6,
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: 680 }}>
      <div>
        <h1 style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 22, fontWeight: 500 }}>
          Privacidade e dados
        </h1>
        <small style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>
          O que o SNAJI guarda, porquê, e os seus direitos — em linguagem clara.
        </small>
      </div>

      <div style={cartao}>
        <div style={titulo}>O que guardamos</div>
        Os relatos e documentos que submete para análise, os casos e processos que
        cria, e a sua conta (nome, email, perfil). Estes dados existem para uma
        única finalidade: prestar-lhe o apoio jurídico informativo que pediu.
      </div>

      <div style={cartao}>
        <div style={titulo}>O que nunca fazemos</div>
        Não vendemos nem partilhamos os seus dados. As estatísticas do Observatório
        são <strong>anonimizadas por desenho</strong>: o registo analítico não guarda nomes,
        emails, nem textos de casos — apenas categorias e contagens, com proteção
        de anonimato em grupos pequenos (contagens inferiores a 3 são mascaradas).
      </div>

      <div style={cartao}>
        <div style={titulo}>Integridade dos registos</div>
        Os registos de atividade do sistema são protegidos por uma cadeia de
        verificação criptográfica: alterar um único caractere de um registo antigo
        é detetável. Correções a processos nunca apagam o valor anterior — fica
        sempre o rasto de quem corrigiu, quando, e o que lá estava.
      </div>

      <div style={cartao}>
        <div style={titulo}>Os seus direitos (RGPD)</div>
        Tem direito a aceder aos seus dados, a corrigi-los, a pedir a sua
        eliminação e a recebê-los em formato portátil. Nos registos onde a
        eliminação comprometeria a integridade da auditoria, aplica-se
        <strong> anonimização</strong>: a sua identidade é removida, o rasto estatístico
        permanece. Para exercer qualquer destes direitos, use os contactos
        institucionais na página <strong>Contactos</strong>.
      </div>

      <div style={cartao}>
        <div style={titulo}>Retenção</div>
        Nesta fase de demonstração, os dados persistem apenas no servidor de
        testes e podem ser repostos a qualquer momento. Em produção, a política
        de retenção será definida pelo Ministério da Justiça e publicada aqui,
        com prazos concretos por tipo de dado.
      </div>

      <div style={{ fontSize: 11.5, color: 'var(--color-text-tertiary)', lineHeight: 1.6 }}>
        SNAJI — Serviço Nacional de Assistência Jurídica Inteligente. Sistema de
        apoio cognitivo: informa, organiza e verifica — nunca decide. Documento
        de política de dados da fase de demonstração.
      </div>
    </div>
  )
}
