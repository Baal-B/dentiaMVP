import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from './AuthProvider'

export default function ProtectedRoute() {
  const { session, loading } = useAuth()
  const { pathname } = useLocation()
  if (loading) return <p style={{ padding: 24 }}>Loading…</p>
  // logged-out visitors on the home page see the patient directory; any other private URL still asks for login
  return session ? <Outlet /> : <Navigate to={pathname === '/' ? '/cabinets' : '/login'} replace />
}