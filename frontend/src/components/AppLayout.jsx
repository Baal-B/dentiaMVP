import { NavLink, Outlet } from 'react-router-dom'

import { useAuth } from '../features/auth/AuthProvider'
import '../styles/clinic.css'

import logo from '../assets/logo.png'

import {
  LayoutDashboard, Users, Scan, CalendarDays,
  MessageSquare, FileText, Bell, Settings as SettingsIcon, LogOut,
} from 'lucide-react'
import { useUnread } from '../features/notifications/useUnread'

const nav = [
  { to: '/', label: 'Tableau de bord', icon: LayoutDashboard, end: true },
  { to: '/patients', label: 'Patients', icon: Users },
  { to: '/analysis', label: 'Nouvelle analyse', icon: Scan },
  { to: '/appointments', label: 'Rendez-vous', icon: CalendarDays },
  { to: '/reports', label: 'Rapports', icon: FileText },
  { to: '/notifications', label: 'Notifications', icon: Bell, badge: true },
{ to: '/settings', label: 'Paramètres', icon: SettingsIcon },
]

const soon = [
  { label: 'Assistant clinique', icon: MessageSquare },
  
 
]

export default function AppLayout() {
  const { user, profile, signOut } = useAuth()
  const unread = useUnread()


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
  <img src={logo} alt="DentIA" className="clinic-brand-mark" />
 
</div>

        <nav className="clinic-nav">
          {nav.map(({ to, label, icon: Icon, end, badge }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => 'clinic-nav-link' + (isActive ? ' active' : '')}
            >
              <Icon size={20} />
              <span className="clinic-nav-label">{label}</span>
               {badge && unread > 0 && <span className="clinic-badge">{unread}</span>}
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