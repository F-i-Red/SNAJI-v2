/**
 * Contactos — SNAJI (todos os perfis; o administrador edita aqui mesmo)
 *
 * Uma única página: todos veem os contactos institucionais; o administrador
 * técnico edita-os diretamente aqui. O carimbo "última gravação no servidor"
 * é escrito pelo próprio servidor — prova de que a gravação persistiu.
 */

import { useEffect, useState } from 'react'
import { api, tratarErroAPI } from '../services/api'
import { useRole } from '../auth/session'

interface Config {
  email_suporte: string
  telefone_suporte: string
  horario: string
  mensagem_casos_extensos: string
  atualizado_em?: string
}

export default function PaginaContactos() {
  const role = useRole()
  const ehAdmin = role === 'admin'
  const [cfg, setCfg] = useState<Config | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [guardado, setGuardado] = useState(false)
  const [aGuardar, setAGuardar] = useState(false)

  const carregar = () => {
    api.get<Config>('/config')
      .then(r => setCfg(r.data))
      .catch(e => setErro(tratarErroAPI(e)))
  }
  useEffect(carregar, [])

  const guardar = async () => {
    if (!cfg) return
    setAGuardar(true); setErro(null); setGuardado(false)
    try {
      await api.put('/config', cfg)
      const conf = await api.get<Config>('/config')   // confirmação real
      setCfg(conf.data)
      if (cfg.email_suporte && !conf.data.email_suporte) {
        setErro('O servidor não persistiu os valores. Verifique no terminal do backend '
          + 'a linha do pedido PUT /api/v1/config e se o ficheiro backend/app/db/config.json foi criado.')
      } else {
        setGuardado(true); setTimeout(() => setGuardado(false), 3000)
      }
    } catch (e) { setErro(tratarErroAPI(e)) }
    finally { setAGuardar(false) }
  }

  const cartao: React.CSSProperties = {
    background: 'var(--color-background-primary)',
    border: '0.5px solid var(--color-border-tertiary)',
    borderRadius: 'var(--border-radius-lg)', padding: '18px',
  }

  const campoEdicao = (rotulo: string, chave: keyof Config, placeholder: string, area = false) => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--color-text-secondary)' }}>{rotulo}</label>
      {area ? (
        <textarea rows={3} value={cfg?.[chave] ?? ''} placeholder={placeholder}
          onChange={e => cfg && setCfg({ ...cfg, [chave]: e.target.value })}
          style={{ border: '0.5px solid var(--color-border-secondary)', borderRadius: 'var(--border-radius-md)', padding: '8px 10px', fontSize: 13.5, fontFamily: 'inherit', resize: 'vertical', lineHeight: 1.5 }} />
      ) : (
        <input type="text" value={cfg?.[chave] ?? ''} placeholder={placeholder}
          onChange={e => cfg && setCfg({ ...cfg, [chave]: e.target.value })}
          style={{ border: '0.5px solid var(--color-border-secondary)', borderRadius: 'var(--border-radius-md)', padding: '8px 10px', fontSize: 13.5, fontFamily: 'inherit' }} />
      )}
    </div>
  )

  const linhaLeitura = (icone: string, rotulo: string, valor?: string) => (
    <div style={{ display: 'flex', gap: 12, alignItems: 'baseline', padding: '10px 0', borderBottom: '0.5px solid var(--color-border-tertiary)' }}>
      <i className={`ti ${icone}`} aria-hidden="true" style={{ color: '#0a2342', fontSize: 16, width: 20 }} />
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--color-text-tertiary)' }}>{rotulo}</div>
        <div style={{ fontSize: 14, color: valor ? 'var(--color-text-primary)' : 'var(--color-text-tertiary)' }}>
          {valor || 'ainda não definido pelo administrador'}
        </div>
      </div>
    </div>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: 620 }}>
      <div>
        <h1 style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 22, fontWeight: 500 }}>
          Contactos
        </h1>
        <small style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>
          {ehAdmin
            ? 'Edite aqui os contactos institucionais — ficam visíveis a todos os utilizadores e nos rodapés dos documentos.'
            : 'Apoio institucional do SNAJI — para dúvidas, problemas de acesso ou pedidos especiais.'}
        </small>
      </div>

      {erro && <div style={{ ...cartao, borderLeft: '3px solid var(--color-text-danger)', fontSize: 13, lineHeight: 1.6 }}>{erro}</div>}

      {cfg?.atualizado_em && (
        <div style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>
          Última gravação no servidor: {new Date(cfg.atualizado_em).toLocaleDateString('pt-PT')}{' '}
          {new Date(cfg.atualizado_em).toLocaleTimeString('pt-PT', { hour: '2-digit', minute: '2-digit' })}
        </div>
      )}

      {cfg && !ehAdmin && (
        <div style={cartao}>
          {linhaLeitura('ti-mail', 'Email de suporte', cfg.email_suporte)}
          {linhaLeitura('ti-phone', 'Telefone', cfg.telefone_suporte)}
          {linhaLeitura('ti-clock', 'Horário de atendimento', cfg.horario)}
          <div style={{ paddingTop: 12, fontSize: 13, lineHeight: 1.6, color: 'var(--color-text-secondary)' }}>
            {cfg.mensagem_casos_extensos}
          </div>
        </div>
      )}

      {cfg && ehAdmin && (
        <div style={{ ...cartao, display: 'flex', flexDirection: 'column', gap: 14 }}>
          {campoEdicao('Email de suporte', 'email_suporte', 'ex.: apoio@snaji.gov.pt')}
          {campoEdicao('Telefone de suporte', 'telefone_suporte', 'ex.: 213 000 000')}
          {campoEdicao('Horário de atendimento', 'horario', 'ex.: dias úteis, 9h–17h')}
          {campoEdicao('Mensagem para casos extensos', 'mensagem_casos_extensos',
            'Texto mostrado quando um processo excede a análise automática', true)}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <button onClick={guardar} disabled={aGuardar}
              style={{ padding: '9px 18px', background: '#0a2342', color: '#fff', border: 'none', borderRadius: 'var(--border-radius-md)', fontSize: 13, fontWeight: 500, cursor: 'pointer', fontFamily: 'inherit' }}>
              {aGuardar ? 'A guardar…' : 'Guardar contactos'}
            </button>
            {guardado && <span style={{ fontSize: 13, color: 'var(--color-text-success)' }}>✓ Guardado e confirmado no servidor</span>}
          </div>
        </div>
      )}
    </div>
  )
}
