/**
 * Utilizadores — SNAJI (administrador técnico)
 *
 * Lista das contas do sistema com o respetivo perfil e a data do último acesso.
 * É a visão de gestão do admin: quem existe, quem tem entrado. O admin gere
 * contas — nunca conteúdo processual.
 */

import { useEffect, useState } from 'react'
import { api, tratarErroAPI } from '../services/api'

interface Utilizador {
  nome: string
  email: string
  role: string
  activo: boolean
  ultimo_login: string | null
}

const NOME_PERFIL: Record<string, string> = {
  cidadao: 'Cidadão', advogado: 'Advogado', magistrado: 'Magistrado',
  analista: 'Analista', admin: 'Administrador',
}

export default function PaginaUtilizadores() {
  const [lista, setLista] = useState<Utilizador[]>([])
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(true)

  useEffect(() => {
    api.get<{ utilizadores: Utilizador[] }>('/admin/utilizadores')
      .then(r => setLista(r.data.utilizadores))
      .catch(e => setErro(tratarErroAPI(e)))
      .finally(() => setCarregando(false))
  }, [])

  const fmtData = (iso: string | null) => {
    if (!iso) return 'nunca'
    const d = new Date(iso)
    return d.toLocaleDateString('pt-PT', { day: 'numeric', month: 'short', year: 'numeric' }) +
      ' ' + d.toLocaleTimeString('pt-PT', { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: 760 }}>
      <div>
        <h1 style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 22, fontWeight: 500 }}>
          Utilizadores
        </h1>
        <small style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>
          Contas do sistema e último acesso. Gestão técnica — o administrador não
          acede a conteúdo processual.
        </small>
      </div>

      {erro && <div style={{ background: 'var(--color-background-primary)', border: '0.5px solid var(--color-border-tertiary)', borderLeft: '3px solid var(--color-text-danger)', borderRadius: 'var(--border-radius-lg)', padding: '12px 14px', fontSize: 13 }}>{erro}</div>}

      {carregando ? (
        <div style={{ fontSize: 13, color: 'var(--color-text-tertiary)' }}>A carregar…</div>
      ) : (
        <div style={{ background: 'var(--color-background-primary)', border: '0.5px solid var(--color-border-tertiary)', borderRadius: 'var(--border-radius-lg)', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: 'var(--color-background-secondary)', textAlign: 'left' }}>
                <th style={{ padding: '9px 12px', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--color-text-tertiary)' }}>Nome</th>
                <th style={{ padding: '9px 12px', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--color-text-tertiary)' }}>Perfil</th>
                <th style={{ padding: '9px 12px', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--color-text-tertiary)' }}>Último acesso</th>
                <th style={{ padding: '9px 12px', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--color-text-tertiary)' }}>Estado</th>
              </tr>
            </thead>
            <tbody>
              {lista.map((u, i) => (
                <tr key={i} style={{ borderTop: '0.5px solid var(--color-border-tertiary)' }}>
                  <td style={{ padding: '9px 12px' }}>
                    <div style={{ fontWeight: 500 }}>{u.nome}</div>
                    <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)' }}>{u.email}</div>
                  </td>
                  <td style={{ padding: '9px 12px', color: 'var(--color-text-secondary)' }}>{NOME_PERFIL[u.role] ?? u.role}</td>
                  <td style={{ padding: '9px 12px', color: u.ultimo_login ? 'var(--color-text-secondary)' : 'var(--color-text-tertiary)' }}>{fmtData(u.ultimo_login)}</td>
                  <td style={{ padding: '9px 12px' }}>
                    <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 10, background: u.activo ? 'var(--color-background-success)' : 'var(--color-background-secondary)', color: u.activo ? 'var(--color-text-success)' : 'var(--color-text-tertiary)' }}>
                      {u.activo ? 'ativo' : 'inativo'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
