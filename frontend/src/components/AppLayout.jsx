import { NavLink, Outlet } from 'react-router-dom'
import {
  LayoutDashboard, Users, Scan, CalendarDays,
  MessageSquare, FileText, Bell, LogOut,
} from 'lucide-react'
import { useAuth } from '../features/auth/AuthProvider'
import '../styles/clinic.css'

const nav = [
  { to: '/', label: 'Tableau de bord', icon: LayoutDashboard, end: true },
  { to: '/patients', label: 'Patients', icon: Users },
  { to: '/analysis', label: 'Nouvelle analyse', icon: Scan },
  { to: '/appointments', label: 'Rendez-vous', icon: CalendarDays },
]

const soon = [
  { label: 'Assistant clinique', icon: MessageSquare },
  { label: 'Rapports', icon: FileText },
  { label: 'Notifications', icon: Bell },
]

export default function AppLayout() {
  const { user, profile, signOut } = useAuth()

  const initials = (profile?.full_name || user?.email || '?')
    .split(/\s|@/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0].toUpperCase())
    .join('')

  return (
    <div className="clinic-shell">
      <aside className="clinic-sidebar">
        <div className="clinic-brand" style={{ marginBottom: 8 }}>
          <div className="clinic-brand-mark">D</div>
          <div className="clinic-brand-name">DentIA</div>
        </div>

        <nav className="clinic-nav">
          {nav.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => 'clinic-nav-link' + (isActive ? ' active' : '')}
            >
              <Icon size={20} />
              <span className="clinic-nav-label">{label}</span>
            </NavLink>
          ))}

          <div className="clinic-nav-section">Bientôt</div>
          {soon.map(({ label, icon: Icon }) => (
            <span key={label} className="clinic-nav-link disabled" title="Pas encore disponible">
              <Icon size={20} />
              <span className="clinic-nav-label">{label}</span>
            </span>
          ))}
        </nav>

        <div className="clinic-sidebar-user">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div className="clinic-avatar">{initials}</div>
            <div className="clinic-user-meta" style={{ lineHeight: 1.25, minWidth: 0 }}>
              <div style={{ fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {profile?.full_name || user?.email}
              </div>
              <span className="clinic-role-pill">{profile?.role ?? 'praticien'}</span>
            </div>
          </div>
          <button onClick={signOut} className="clinic-btn clinic-btn-ghost clinic-btn-block">
            <LogOut size={18} />
            <span className="clinic-nav-label">Déconnexion</span>
          </button>
        </div>
      </aside>

      <div className="clinic-content">
        <main className="clinic-main">
          <Outlet />
        </main>
      </div>
    </div>
  )
}