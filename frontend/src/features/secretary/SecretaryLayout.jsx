import { NavLink, Outlet } from 'react-router-dom'
import { LogOut } from 'lucide-react'
import { useAuth } from '../auth/AuthProvider'
import logo from '../../assets/logo.png'

export default function SecretaryLayout() {
  const { profile, signOut } = useAuth()
  const cls = ({ isActive }) => 'sec-link' + (isActive ? ' active' : '')
  return (
    <div className="sec-shell">
      <header className="sec-bar">
        <div className="sec-brand">
  <img src={logo} alt="DentIA" className="sec-logo" />
  <span className="sec-brand-text">Secrétariat</span>
</div>
        <nav className="sec-nav">
          <NavLink to="/secretary" end className={cls}>Demandes</NavLink>
          <NavLink to="/secretary/agenda" className={cls}>Agenda</NavLink>
          <NavLink to="/secretary/patients" className={cls}>Patients</NavLink>
        </nav>
        <div className="sec-user">
          <span>{profile?.full_name} <span className="clinic-role-pill">secrétaire</span></span>
          <button className="clinic-btn clinic-btn-ghost" onClick={signOut}><LogOut size={18} /> Déconnexion</button>
        </div>
      </header>
      <main className="sec-main"><Outlet /></main>
    </div>
  )
}