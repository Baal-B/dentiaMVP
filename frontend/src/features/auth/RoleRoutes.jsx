import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from './AuthProvider'

export function DoctorOnly() {
  const { profile } = useAuth()
  if (!profile) return <div className="clinic-loading">Chargement…</div>
  return profile.role === 'secretary' ? <Navigate to="/secretary" replace /> : <Outlet />
}

export function SecretaryOnly() {
  const { profile } = useAuth()
  if (!profile) return <div className="clinic-loading">Chargement…</div>
  return profile.role === 'secretary' ? <Outlet /> : <Navigate to="/" replace />
}