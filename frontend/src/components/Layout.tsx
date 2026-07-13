import { useEffect, useState } from 'react'
import { Outlet, useNavigate, useLocation, Link } from 'react-router-dom'
import { useAuthStore, useRole } from '../auth/session'
import { api } from '../services/api'

const NAV_POR_ROLE = {
  cidadao: [
    { path: '/dashboard', icon: 'ti-home', label: 'Início' },
    { path: '/instrutor', icon: 'ti-list-search', label: 'Descrever o meu caso' },
    { path: '/casos', icon: 'ti-folder', label: 'Os meus casos' },
    { path: '/processos', icon: 'ti-eye', label: 'Acompanhar processos' },
    { path: '/consulta', icon: 'ti-message-question', label: 'Tirar uma dúvida' },
    { path: '/contactos', icon: 'ti-lifebuoy', label: 'Contactos' },
  ],
  advogado: [
    { path: '/dashboard', icon: 'ti-home', label: 'Dashboard' },
    { path: '/pecas', icon: 'ti-file-search', label: 'Análise de peças' },
    { path: '/dossie', icon: 'ti-folders', label: 'Compilar dossiê' },
    { path: '/observatorio', icon: 'ti-chart-dots', label: 'Observatório' },
    { path: '/jurisprudencia', icon: 'ti-gavel', label: 'Jurisprudência' },
    { path: '/casos', icon: 'ti-folder', label: 'Os meus casos' },
    { path: '/consulta', icon: 'ti-message-question', label: 'Consulta jurídica' },
    { path: '/instrutor', icon: 'ti-list-search', label: 'Instrução do caso' },
    { path: '/cenarios', icon: 'ti-scale', label: 'Cenários de resolução' },
    { path: '/processos', icon: 'ti-briefcase', label: 'Carteira de processos' },
    { path: '/audiencias', icon: 'ti-gavel', label: 'Audiências' },
    { path: '/documentos', icon: 'ti-file-invoice', label: 'Geração de peças' },
    { path: '/auditoria', icon: 'ti-shield-check', label: 'Auditoria' },
    { path: '/contactos', icon: 'ti-lifebuoy', label: 'Contactos' },
  ],
  magistrado: [
    { path: '/dashboard', icon: 'ti-home', label: 'Dashboard' },
    { path: '/pecas', icon: 'ti-file-search', label: 'Análise de peças' },
    { path: '/dossie', icon: 'ti-folders', label: 'Compilar dossiê' },
    { path: '/cenarios', icon: 'ti-scale', label: 'Cenários de resolução' },
    { path: '/jurisprudencia', icon: 'ti-gavel', label: 'Jurisprudência' },
    { path: '/observatorio', icon: 'ti-chart-dots', label: 'Observatório' },
    { path: '/processos', icon: 'ti-scale', label: 'Processos em carteira' },
    { path: '/audiencias', icon: 'ti-gavel', label: 'Audiências' },
    { path: '/consulta', icon: 'ti-search', label: 'Pesquisa jurídica' },
    { path: '/auditoria', icon: 'ti-shield-lock', label: 'Auditoria forense' },
    { path: '/contactos', icon: 'ti-lifebuoy', label: 'Contactos' },
  ],
  analista: [
    { path: '/dashboard', icon: 'ti-home', label: 'Dashboard' },
    { path: '/observatorio', icon: 'ti-chart-dots', label: 'Observatório' },
    { path: '/auditoria', icon: 'ti-chart-bar', label: 'Métricas' },
    { path: '/contactos', icon: 'ti-lifebuoy', label: 'Contactos' },
  ],
  admin: [
    { path: '/dashboard', icon: 'ti-home', label: 'Dashboard' },
    { path: '/utilizadores', icon: 'ti-users', label: 'Utilizadores' },
    { path: '/observatorio', icon: 'ti-chart-dots', label: 'Observatório' },
    { path: '/auditoria', icon: 'ti-shield', label: 'Auditoria' },
    { path: '/contactos', icon: 'ti-lifebuoy', label: 'Contactos' },
  ],
}

export default function Layout() {
  const { utilizador, logout, restaurarSessao } = useAuthStore()
  const [contactos, setContactos] = useState<{ email_suporte?: string; telefone_suporte?: string; horario?: string } | null>(null)
  const role = useRole()
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    if (!utilizador) return
    api.get('/config')
      .then(r => {
        setContactos(r.data)
        sessionStorage.setItem('snaji_contactos', JSON.stringify(r.data))
      })
      .catch(() => {})
  }, [utilizador])

  useEffect(() => {
    if (!utilizador) restaurarSessao()
  }, [])

  useEffect(() => {
    if (!utilizador && !useAuthStore.getState().carregando) {
      navigate('/login')
    }
  }, [utilizador])

  if (!utilizador) return null

  const navItems = NAV_POR_ROLE[role ?? 'cidadao'] ?? NAV_POR_ROLE.cidadao
  const iniciais = utilizador.nome.split(' ').slice(0, 2).map(w => w[0]).join('')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>

      {/* Topbar institucional */}
      <header style={{
        background: '#0a2342',
        borderBottom: '2px solid #c4960a',
        padding: '0 1.5rem',
        display: 'flex',
        alignItems: 'center',
        gap: '1rem',
        minHeight: 52,
        position: 'sticky',
        top: 0,
        zIndex: 100,
      }}>
        <div style={{
          fontFamily: "'Cormorant Garamond', serif",
          fontSize: 20, fontWeight: 600,
          color: '#fff', letterSpacing: '0.04em',
          flexShrink: 0,
        }}>
          SNA<span style={{ color: '#e8b820' }}>JI</span>
        </div>
        <div style={{
          fontSize: 10, color: 'rgba(255,255,255,0.4)',
          textTransform: 'uppercase', letterSpacing: '0.1em',
          flex: 1,
        }}>
          Sistema Nacional de Assistência Jurídica Inteligente · República Portuguesa
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            fontSize: 11, color: 'rgba(255,255,255,0.6)',
            textAlign: 'right',
          }}>
            <div style={{ color: '#fff', fontWeight: 500 }}>{utilizador.nome.split(' ')[0]}</div>
            <div style={{ textTransform: 'uppercase', letterSpacing: '0.06em' }}>{role}</div>
          </div>
          <button
            onClick={() => { if (window.confirm('Terminar a sessão?')) { logout(); navigate('/login') } }}
            style={{
              background: 'rgba(255,255,255,0.1)',
              border: '0.5px solid rgba(255,255,255,0.2)',
              borderRadius: 'var(--border-radius-md)',
              color: 'rgba(255,255,255,0.7)',
              fontSize: 11, padding: '5px 10px',
              cursor: 'pointer', fontFamily: 'inherit',
            }}
          >
            <i className="ti ti-logout" aria-hidden="true" />
          </button>
        </div>
      </header>

      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>

        {/* Sidebar */}
        <nav style={{
          width: 220,
          flexShrink: 0,
          borderRight: '0.5px solid var(--color-border-tertiary)',
          background: 'var(--color-background-secondary)',
          padding: '0.75rem 0',
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
          position: 'sticky',
          top: 52,
          height: 'calc(100vh - 52px)',
          overflowY: 'auto',
        }}>
          {/* Avatar */}
          <div style={{
            padding: '0.5rem 1rem 0.75rem',
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <div style={{
              width: 32, height: 32, borderRadius: '50%',
              background: '#0a2342',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 11, fontWeight: 500, color: '#fff', flexShrink: 0,
            }}>
              {iniciais}
            </div>
            <div>
              <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--color-text-primary)' }}>
                {utilizador.nome.split(' ').slice(0, 2).join(' ')}
              </div>
              <div style={{ fontSize: 10, color: 'var(--color-text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                {role}
              </div>
            </div>
          </div>

          <div style={{ height: '0.5px', background: 'var(--color-border-tertiary)', margin: '0 0 6px' }} />

          <div style={{
            fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.1em',
            color: 'var(--color-text-tertiary)', padding: '0 1rem 4px',
            fontWeight: 500,
          }}>
            Navegação
          </div>

          {navItems.map(item => {
            const activo = location.pathname === item.path
            return (
              <Link
                key={item.path}
                to={item.path}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '7px 1rem',
                  fontSize: 13,
                  color: activo ? '#0a2342' : 'var(--color-text-secondary)',
                  fontWeight: activo ? 500 : 400,
                  borderLeft: activo ? '2px solid #c4960a' : '2px solid transparent',
                  background: activo ? 'var(--color-background-primary)' : 'transparent',
                  textDecoration: 'none',
                  transition: 'all 0.15s',
                }}
              >
                <i className={`ti ${item.icon}`} aria-hidden="true" style={{ fontSize: 15, opacity: 0.7 }} />
                <span>{item.label}</span>
              </Link>
            )
          })}
          {contactos && (contactos.email_suporte || contactos.telefone_suporte) && (
            <div style={{
              marginTop: 'auto', padding: '10px 12px',
              borderTop: '0.5px solid var(--color-border-tertiary)',
              fontSize: 11, lineHeight: 1.6, color: 'var(--color-text-tertiary)',
            }}>
              <div style={{ fontWeight: 600, marginBottom: 2 }}>Apoio SNAJI</div>
              {contactos.email_suporte && <div>{contactos.email_suporte}</div>}
              {contactos.telefone_suporte && <div>{contactos.telefone_suporte}</div>}
              {contactos.horario && <div>{contactos.horario}</div>}
            </div>
          )}
        </nav>

        {/* Conteúdo principal */}
        <main style={{
          flex: 1,
          padding: '1.25rem',
          overflowY: 'auto',
          background: 'var(--color-background-tertiary)',
        }}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
