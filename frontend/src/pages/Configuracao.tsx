/**
 * Configuração do Sistema — SNAJI (administrador técnico)
 *
 * Onde o admin edita os contactos institucionais que os utilizadores veem
 * quando precisam de apoio ou de um pedido especial (ex.: um processo
 * demasiado extenso para a análise automática). Editável sem tocar no código.
 */

import { useEffect, useState } from 'react'
import { api, tratarErroAPI } from '../services/api'

interface Config {
  email_suporte: string
  telefone_suporte: string
  horario: string
  mensagem_casos_extensos: string
}

export default function PaginaConfiguracao() {
  const [cfg, setCfg] = useState<Config | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [guardado, setGuardado] = useState(false)
  const [aGuardar, setAGuardar] = useState(false)

  useEffect(() => {
    api.get<Config>('/config')
      .then(r => setCfg(r.data))
      .catch(e => setErro(tratarErroAPI(e)))
  }, [])

  const guardar = async () => {
    if (!cfg) return
    setAGuardar(true); setErro(null); setGuardado(false)
    try {
      const r = await api.put<Config>('/config', cfg)
      setCfg(r.data); setGuardado(true)
      setTimeout(() => setGuardado(false), 2500)
    } catch (e) { setErro(tratarErroAPI(e)) }
    finally { setAGuardar(false) }
  }

  const campo = (label: string, chave: keyof Config, placeholder: string, area = false) => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--color-text-secondary)' }}>{label}</label>
      {area ? (
        <textarea
          rows={3} value={cfg?.[chave] ?? ''} placeholder={placeholder}
          onChange={e => cfg && setCfg({ ...cfg, [chave]: e.target.value })}
          style={{ border: '0.5px solid var(--color-border-secondary)', borderRadius: 'var(--border-radius-md)', padding: '8px 10px', fontSize: 13.5, fontFamily: 'inherit', resize: 'vertical', lineHeight: 1.5 }}
        />
      ) : (
        <input
          type="text" value={cfg?.[chave] ?? ''} placeholder={placeholder}
          onChange={e => cfg && setCfg({ ...cfg, [chave]: e.target.value })}
          style={{ border: '0.5px solid var(--color-border-secondary)', borderRadius: 'var(--border-radius-md)', padding: '8px 10px', fontSize: 13.5, fontFamily: 'inherit' }}
        />
      )}
    </div>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: 640 }}>
      <div>
        <h1 style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 22, fontWeight: 500 }}>
          Configuração do sistema
        </h1>
        <small style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>
          Contactos institucionais mostrados aos utilizadores que precisem de apoio.
          Editável sem alterar o código.
        </small>
      </div>

      {erro && <div style={{ background: 'var(--color-background-primary)', border: '0.5px solid var(--color-border-tertiary)', borderLeft: '3px solid var(--color-text-danger)', borderRadius: 'var(--border-radius-lg)', padding: '12px 14px', fontSize: 13 }}>{erro}</div>}

      {cfg && (
        <div style={{ background: 'var(--color-background-primary)', border: '0.5px solid var(--color-border-tertiary)', borderRadius: 'var(--border-radius-lg)', padding: '18px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          {campo('Email de suporte', 'email_suporte', 'ex.: apoio@snaji.gov.pt')}
          {campo('Telefone de suporte', 'telefone_suporte', 'ex.: 213 000 000')}
          {campo('Horário de atendimento', 'horario', 'ex.: dias úteis, 9h–17h')}
          {campo('Mensagem para casos extensos', 'mensagem_casos_extensos',
            'Texto mostrado quando um processo excede a análise automática', true)}

          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <button onClick={guardar} disabled={aGuardar}
              style={{ padding: '9px 18px', background: '#0a2342', color: '#fff', border: 'none', borderRadius: 'var(--border-radius-md)', fontSize: 13, fontWeight: 500, cursor: 'pointer', fontFamily: 'inherit' }}>
              {aGuardar ? 'A guardar…' : 'Guardar configuração'}
            </button>
            {guardado && <span style={{ fontSize: 13, color: 'var(--color-text-success)' }}>✓ Guardado</span>}
          </div>
        </div>
      )}
    </div>
  )
}
