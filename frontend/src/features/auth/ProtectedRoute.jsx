import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from './AuthProvider'

export default function ProtectedRoute() {
  const { session, loading } = useAuth()
  if (loading) return <p style={{ padding: 24 }}>Loading…</p>
  return session ? <Outlet /> : <Navigate to="/login" replace />
}